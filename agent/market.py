"""Market data and price feeds via Uniswap V3 Quoter on Base."""

import logging
from collections import deque
from typing import Deque, List, Optional

from web3 import Web3

from .config import QUOTER_ABI, TOKEN_DECIMALS, Config, PoolFee

logger = logging.getLogger(__name__)


class MarketData:
    """Fetches token prices from Uniswap V3 and maintains a price history."""

    def __init__(self, w3: Web3, config: Config, max_history: int = 200) -> None:
        self.w3 = w3
        self.config = config
        self.quoter = w3.eth.contract(
            address=w3.to_checksum_address(config.contracts["quoter"]),
            abi=QUOTER_ABI,
        )
        self._history: Deque[float] = deque(maxlen=max_history)

    # ── Price fetching ─────────────────────────────────────────────────────────

    def get_price(
        self,
        token_in_symbol: str = "WETH",
        token_out_symbol: Optional[str] = None,
        fee: Optional[PoolFee] = None,
        amount_in: Optional[int] = None,
    ) -> Optional[float]:
        """Return the price of *token_out* denominated in *token_in*.

        Returns the number of *token_out* units received for *amount_in* of
        *token_in*, expressed in human-readable (decimal-adjusted) units.
        Returns ``None`` on failure.
        """
        if token_out_symbol is None:
            token_out_symbol = self.config.trade_token_symbol
        if fee is None:
            fee = self.config.pool_fee
        if amount_in is None:
            amount_in = 10 ** TOKEN_DECIMALS.get(token_in_symbol, 18)  # 1 unit

        token_in_addr = self.config.tokens.get(token_in_symbol)
        token_out_addr = self.config.tokens.get(token_out_symbol)

        if not token_in_addr or not token_out_addr:
            logger.error(
                "Unknown token symbol(s): %s / %s", token_in_symbol, token_out_symbol
            )
            return None

        try:
            result = self.quoter.functions.quoteExactInputSingle(
                {
                    "tokenIn": self.w3.to_checksum_address(token_in_addr),
                    "tokenOut": self.w3.to_checksum_address(token_out_addr),
                    "amountIn": amount_in,
                    "fee": int(fee),
                    "sqrtPriceLimitX96": 0,
                }
            ).call()
            amount_out_raw: int = result[0]
            decimals_out = TOKEN_DECIMALS.get(token_out_symbol, 18)
            price = amount_out_raw / 10**decimals_out
            logger.debug(
                "Price %s/%s = %.6f", token_in_symbol, token_out_symbol, price
            )
            return price
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch price: %s", exc)
            return None

    def update_price_history(self) -> Optional[float]:
        """Fetch the current price and append it to the history deque."""
        price = self.get_price()
        if price is not None:
            self._history.append(price)
        return price

    # ── Technical indicators ───────────────────────────────────────────────────

    @property
    def prices(self) -> List[float]:
        """Return price history as a list (oldest first)."""
        return list(self._history)

    def sma(self, window: int) -> Optional[float]:
        """Simple moving average over the last *window* prices."""
        if len(self._history) < window:
            return None
        recent = list(self._history)[-window:]
        return sum(recent) / window

    def rsi(self, period: int = 14) -> Optional[float]:
        """Relative Strength Index over the last *period* + 1 prices."""
        prices = list(self._history)
        if len(prices) < period + 1:
            return None
        deltas = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        recent = deltas[-period:]
        gains = [d for d in recent if d > 0]
        losses = [-d for d in recent if d < 0]
        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
