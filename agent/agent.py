"""Main trading agent orchestrator."""

import logging
import time
from typing import Optional

from web3 import Web3

from .config import Config
from .executor import TradeExecutor
from .market import MarketData
from .strategy import CombinedStrategy, RSIStrategy, SMACrossoverStrategy, Signal
from .wallet import Wallet

logger = logging.getLogger(__name__)


class TradingAgent:
    """Autonomous trading agent for Base (Ethereum L2).

    Polling loop:
    1. Fetch current price from Uniswap V3 Quoter.
    2. Append price to history.
    3. Evaluate strategy.
    4. Execute trade if signal is BUY or SELL (subject to risk checks).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {config.rpc_url}")
        logger.info(
            "Connected to Base %s (chain %d)",
            "Sepolia" if config.testnet else "Mainnet",
            self.w3.eth.chain_id,
        )

        self.wallet = Wallet(self.w3, config)
        self.market = MarketData(self.w3, config)
        self.executor = TradeExecutor(self.w3, config, self.wallet)
        self.strategy = CombinedStrategy(
            sma=SMACrossoverStrategy(
                short_window=config.sma_short_window,
                long_window=config.sma_long_window,
            ),
            rsi=RSIStrategy(
                period=config.rsi_period,
                overbought=config.rsi_overbought,
                oversold=config.rsi_oversold,
            ),
        )

        # Risk tracking
        self._entry_price: Optional[float] = None
        self._position_eth: float = 0.0  # ETH value currently deployed

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the polling loop. Runs until interrupted."""
        mode = "DRY-RUN" if self.config.dry_run else "LIVE"
        logger.info(
            "Agent starting [%s] | token=%s | interval=%ds",
            mode,
            self.config.trade_token_symbol,
            self.config.polling_interval,
        )
        try:
            while True:
                self._tick()
                time.sleep(self.config.polling_interval)
        except KeyboardInterrupt:
            logger.info("Agent stopped by user.")

    def _tick(self) -> None:
        """Single iteration of the trading loop."""
        # 1. Update price history
        price = self.market.update_price_history()
        if price is None:
            logger.warning("Could not fetch price – skipping tick.")
            return

        eth_balance = self.wallet.eth_balance()
        logger.info(
            "Tick | price=%.4f %s/WETH | ETH balance=%.6f",
            price,
            self.config.trade_token_symbol,
            eth_balance,
        )

        # 2. Risk management: check stop-loss / take-profit
        if self._entry_price and self._position_eth > 0:
            pnl_pct = (price - self._entry_price) / self._entry_price * 100
            if pnl_pct <= -self.config.stop_loss_percent:
                logger.warning(
                    "STOP-LOSS triggered (PnL=%.2f%%) – closing position.", pnl_pct
                )
                self._execute_sell(price)
                return
            if pnl_pct >= self.config.take_profit_percent:
                logger.info(
                    "TAKE-PROFIT triggered (PnL=%.2f%%) – closing position.", pnl_pct
                )
                self._execute_sell(price)
                return

        # 3. Evaluate strategy
        result = self.strategy.evaluate(self.market)
        logger.info(
            "Strategy → %s (conf=%.2f) | %s",
            result.signal.value,
            result.confidence,
            result.reason,
        )

        # 4. Execute
        if result.signal == Signal.BUY:
            self._execute_buy(price, eth_balance)
        elif result.signal == Signal.SELL:
            self._execute_sell(price)

    # ── Trade execution with risk guards ──────────────────────────────────────

    def _execute_buy(self, price: float, eth_balance: float) -> None:
        """Execute a BUY after risk checks."""
        if self._position_eth >= self.config.max_position_eth:
            logger.info("Max position reached – skipping BUY.")
            return
        if eth_balance < self.config.trade_amount_eth:
            logger.warning(
                "Insufficient ETH balance (%.6f < %.6f) – skipping BUY.",
                eth_balance,
                self.config.trade_amount_eth,
            )
            return

        receipt = self.executor.buy()
        if receipt or self.config.dry_run:
            self._entry_price = price
            self._position_eth += self.config.trade_amount_eth
            logger.info(
                "BUY executed | entry_price=%.4f | position_eth=%.6f",
                price,
                self._position_eth,
            )

    def _execute_sell(self, price: float) -> None:
        """Execute a SELL and reset position tracking."""
        if self._position_eth == 0:
            logger.info("No open position – skipping SELL.")
            return

        receipt = self.executor.sell()
        if receipt or self.config.dry_run:
            if self._entry_price:
                pnl = (price - self._entry_price) / self._entry_price * 100
                logger.info(
                    "SELL executed | exit_price=%.4f | PnL=%.2f%%",
                    price,
                    pnl,
                )
            self._entry_price = None
            self._position_eth = 0.0
