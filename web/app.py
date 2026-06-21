"""Flask web server for the Base Trading Agent dashboard."""

import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "base-trading-agent-secret")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory state (updated by the agent thread)
# ---------------------------------------------------------------------------
state: Dict[str, Any] = {
    "running": False,
    "dry_run": True,
    "testnet": True,
    "token": "USDC",
    "strategy": "combined",
    "trade_amount_eth": 0.01,
    "polling_interval": 60,
    "max_slippage": 0.5,
    "eth_balance": 0.0,
    "token_balance": 0.0,
    "current_price": None,
    "entry_price": None,
    "position_eth": 0.0,
    "pnl_pct": None,
    "last_signal": "HOLD",
    "last_signal_reason": "",
    "last_signal_confidence": 0.0,
    "trade_count": 0,
    "price_history": [],   # list of {t, price}
    "trade_log": [],       # list of {time, action, price, amount}
    "log_lines": deque(maxlen=200),
    "sma_short": None,
    "sma_long": None,
    "rsi": None,
    "error": None,
}

_agent_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


# ---------------------------------------------------------------------------
# Logging handler that pushes lines to state and via SocketIO
# ---------------------------------------------------------------------------
class UILogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        state["log_lines"].append(line)
        try:
            socketio.emit("log", {"line": line})
        except Exception:  # noqa: BLE001
            pass


def setup_ui_logging() -> None:
    handler = UILogHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                          datefmt="%H:%M:%S")
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Agent thread
# ---------------------------------------------------------------------------
def _agent_loop(config) -> None:  # type: ignore[no-untyped-def]
    """Run the trading agent in a background thread, pushing state updates."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from web3 import Web3
    from agent.wallet import Wallet
    from agent.market import MarketData
    from agent.executor import TradeExecutor
    from agent.strategy import (
        CombinedStrategy, SMACrossoverStrategy, RSIStrategy, Signal
    )
    from agent.config import TOKEN_DECIMALS

    try:
        w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        if not w3.is_connected():
            state["error"] = f"Cannot connect to RPC: {config.rpc_url}"
            state["running"] = False
            socketio.emit("state", _safe_state())
            return

        wallet = Wallet(w3, config)
        market = MarketData(w3, config)
        executor = TradeExecutor(w3, config, wallet)

        sma_strat = SMACrossoverStrategy(
            short_window=config.sma_short_window,
            long_window=config.sma_long_window,
        )
        rsi_strat = RSIStrategy(
            period=config.rsi_period,
            overbought=config.rsi_overbought,
            oversold=config.rsi_oversold,
        )
        strategy_map = {
            "sma": sma_strat,
            "rsi": rsi_strat,
            "combined": CombinedStrategy(sma_strat, rsi_strat),
        }
        strategy = strategy_map.get(state["strategy"], strategy_map["combined"])

        entry_price: Optional[float] = None
        position_eth: float = 0.0

        while not _stop_event.is_set():
            # 1. Balances
            try:
                state["eth_balance"] = wallet.eth_balance()
                token_addr = config.tokens.get(config.trade_token_symbol)
                if token_addr:
                    dec = TOKEN_DECIMALS.get(config.trade_token_symbol, 18)
                    state["token_balance"] = wallet.token_balance(token_addr, dec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Balance fetch failed: %s", exc)

            # 2. Price
            price = market.update_price_history()
            if price is not None:
                state["current_price"] = price
                state["price_history"].append(
                    {"t": datetime.utcnow().isoformat(), "price": price}
                )
                if len(state["price_history"]) > 500:
                    state["price_history"] = state["price_history"][-500:]

            # 3. Indicators
            state["sma_short"] = market.sma(config.sma_short_window)
            state["sma_long"] = market.sma(config.sma_long_window)
            state["rsi"] = market.rsi(config.rsi_period)

            # 4. PnL
            if entry_price and position_eth > 0 and price:
                state["pnl_pct"] = (price - entry_price) / entry_price * 100
            else:
                state["pnl_pct"] = None
            state["entry_price"] = entry_price
            state["position_eth"] = position_eth

            # 5. Strategy
            if price is not None:
                result = strategy.evaluate(market)
                state["last_signal"] = result.signal.value
                state["last_signal_reason"] = result.reason
                state["last_signal_confidence"] = result.confidence

                # 6. Risk: stop-loss / take-profit
                if entry_price and position_eth > 0:
                    pnl = (price - entry_price) / entry_price * 100
                    if pnl <= -config.stop_loss_percent:
                        logger.warning("STOP-LOSS triggered (%.2f%%) - closing.", pnl)
                        executor.sell()
                        _log_trade("SELL (stop-loss)", price, position_eth)
                        entry_price = None
                        position_eth = 0.0
                    elif pnl >= config.take_profit_percent:
                        logger.info("TAKE-PROFIT triggered (%.2f%%) - closing.", pnl)
                        executor.sell()
                        _log_trade("SELL (take-profit)", price, position_eth)
                        entry_price = None
                        position_eth = 0.0

                # 7. Execute
                elif result.signal == Signal.BUY and state["eth_balance"] >= config.trade_amount_eth:
                    executor.buy()
                    entry_price = price
                    position_eth += config.trade_amount_eth
                    state["trade_count"] += 1
                    _log_trade("BUY", price, config.trade_amount_eth)
                elif result.signal == Signal.SELL and position_eth > 0:
                    executor.sell()
                    _log_trade("SELL", price, position_eth)
                    entry_price = None
                    position_eth = 0.0
                    state["trade_count"] += 1

            state["entry_price"] = entry_price
            state["position_eth"] = position_eth
            state["error"] = None

            socketio.emit("state", _safe_state())

            _stop_event.wait(config.polling_interval)

    except Exception as exc:  # noqa: BLE001
        logger.error("Agent error: %s", exc, exc_info=True)
        state["error"] = str(exc)
    finally:
        state["running"] = False
        socketio.emit("state", _safe_state())


def _log_trade(action: str, price: float, amount: float) -> None:
    state["trade_log"].append({
        "time": datetime.utcnow().strftime("%H:%M:%S"),
        "action": action,
        "price": round(price, 4),
        "amount": round(amount, 6),
    })
    if len(state["trade_log"]) > 100:
        state["trade_log"] = state["trade_log"][-100:]


def _safe_state() -> Dict[str, Any]:
    """Return a JSON-serialisable snapshot of state."""
    return {
        k: list(v) if isinstance(v, deque) else v
        for k, v in state.items()
        if k != "log_lines"
    }


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(_safe_state())


@app.route("/api/logs")
def api_logs():
    return jsonify({"lines": list(state["log_lines"])})


@app.route("/api/start", methods=["POST"])
def api_start():
    global _agent_thread, _stop_event

    if state["running"]:
        return jsonify({"error": "Agent already running"}), 400

    data = request.get_json(force=True)
    private_key = os.getenv("PRIVATE_KEY", data.get("private_key", ""))
    if not private_key:
        return jsonify({"error": "PRIVATE_KEY not set"}), 400

    # Update state from request
    state.update({
        "dry_run": data.get("dry_run", True),
        "testnet": data.get("testnet", True),
        "token": data.get("token", "USDC"),
        "strategy": data.get("strategy", "combined"),
        "trade_amount_eth": float(data.get("trade_amount_eth", 0.01)),
        "polling_interval": int(data.get("polling_interval", 60)),
        "max_slippage": float(data.get("max_slippage", 0.5)),
        "running": True,
        "error": None,
        "trade_count": 0,
        "price_history": [],
        "trade_log": [],
    })

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from agent.config import Config

    config = Config(
        testnet=state["testnet"],
        dry_run=state["dry_run"],
        private_key=private_key,
        trade_token_symbol=state["token"],
        trade_amount_eth=state["trade_amount_eth"],
        polling_interval=state["polling_interval"],
        max_slippage_percent=state["max_slippage"],
    )

    _stop_event = threading.Event()
    _agent_thread = threading.Thread(
        target=_agent_loop, args=(config,), daemon=True
    )
    _agent_thread.start()
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not state["running"]:
        return jsonify({"error": "Agent not running"}), 400
    _stop_event.set()
    return jsonify({"status": "stopping"})


@app.route("/api/price")
def api_price():
    return jsonify({
        "price": state["current_price"],
        "history": state["price_history"][-100:],
    })


# ---------------------------------------------------------------------------
# SocketIO events
# ---------------------------------------------------------------------------
@socketio.on("connect")
def on_connect():
    emit("state", _safe_state())
    emit("logs", {"lines": list(state["log_lines"])})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    setup_ui_logging()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting web dashboard on http://localhost:%d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
