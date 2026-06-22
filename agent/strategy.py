"""Trading strategies for the Base trading agent."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .market import MarketData

logger = logging.getLogger(__name__)


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    signal: Signal
    confidence: float  # 0.0 – 1.0
    reason: str
    current_price: Optional[float] = None
    sma_short: Optional[float] = None
    sma_long: Optional[float] = None
    rsi: Optional[float] = None


class SMACrossoverStrategy:
    """Simple Moving Average crossover strategy.

    Generates a BUY signal when the short SMA crosses above the long SMA,
    a SELL signal when it crosses below, and HOLD otherwise.
    """

    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        self.short_window = short_window
        self.long_window = long_window
        self._prev_short: Optional[float] = None
        self._prev_long: Optional[float] = None

    def evaluate(self, market: MarketData) -> StrategyResult:
        short = market.sma(self.short_window)
        long_ = market.sma(self.long_window)
        price = market.prices[-1] if market.prices else None

        if short is None or long_ is None:
            needed = max(self.short_window, self.long_window)
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reason=f"Warming up – need {needed} data points, have {len(market.prices)}",
                current_price=price,
            )

        signal = Signal.HOLD
        confidence = 0.0
        reason = "No crossover detected"

        if self._prev_short is not None and self._prev_long is not None:
            was_below = self._prev_short <= self._prev_long
            is_above = short > long_
            was_above = self._prev_short >= self._prev_long
            is_below = short < long_

            if was_below and is_above:
                signal = Signal.BUY
                spread = (short - long_) / long_
                confidence = min(spread * 20, 1.0)  # scale spread to confidence
                reason = f"Short SMA ({short:.4f}) crossed above Long SMA ({long_:.4f})"
            elif was_above and is_below:
                signal = Signal.SELL
                spread = (long_ - short) / long_
                confidence = min(spread * 20, 1.0)
                reason = f"Short SMA ({short:.4f}) crossed below Long SMA ({long_:.4f})"

        self._prev_short = short
        self._prev_long = long_

        logger.info(
            "[SMA] price=%.4f short=%.4f long=%.4f → %s (conf=%.2f)",
            price or 0,
            short,
            long_,
            signal.value,
            confidence,
        )
        return StrategyResult(
            signal=signal,
            confidence=confidence,
            reason=reason,
            current_price=price,
            sma_short=short,
            sma_long=long_,
        )


class RSIStrategy:
    """RSI-based mean-reversion strategy.

    Generates BUY when RSI < oversold threshold, SELL when RSI > overbought.
    """

    def __init__(
        self,
        period: int = 14,
        overbought: float = 70.0,
        oversold: float = 30.0,
    ) -> None:
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def evaluate(self, market: MarketData) -> StrategyResult:
        rsi_val = market.rsi(self.period)
        price = market.prices[-1] if market.prices else None

        if rsi_val is None:
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reason=f"Warming up – need {self.period + 1} data points",
                current_price=price,
            )

        if rsi_val < self.oversold:
            confidence = (self.oversold - rsi_val) / self.oversold
            return StrategyResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reason=f"RSI {rsi_val:.1f} below oversold threshold {self.oversold}",
                current_price=price,
                rsi=rsi_val,
            )
        if rsi_val > self.overbought:
            confidence = (rsi_val - self.overbought) / (100 - self.overbought)
            return StrategyResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reason=f"RSI {rsi_val:.1f} above overbought threshold {self.overbought}",
                current_price=price,
                rsi=rsi_val,
            )

        logger.info("[RSI] %.1f → HOLD", rsi_val)
        return StrategyResult(
            signal=Signal.HOLD,
            confidence=0.0,
            reason=f"RSI {rsi_val:.1f} in neutral zone",
            current_price=price,
            rsi=rsi_val,
        )


class CombinedStrategy:
    """Combines SMA crossover and RSI; requires both to agree before trading."""

    def __init__(self, sma: SMACrossoverStrategy, rsi: RSIStrategy) -> None:
        self.sma = sma
        self.rsi = rsi

    def evaluate(self, market: MarketData) -> StrategyResult:
        sma_result = self.sma.evaluate(market)
        rsi_result = self.rsi.evaluate(market)

        if sma_result.signal == rsi_result.signal and sma_result.signal != Signal.HOLD:
            combined_confidence = (sma_result.confidence + rsi_result.confidence) / 2
            return StrategyResult(
                signal=sma_result.signal,
                confidence=combined_confidence,
                reason=f"SMA+RSI agree: {sma_result.reason}; {rsi_result.reason}",
                current_price=sma_result.current_price,
                sma_short=sma_result.sma_short,
                sma_long=sma_result.sma_long,
                rsi=rsi_result.rsi,
            )

        return StrategyResult(
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"Strategies disagree: SMA={sma_result.signal.value}, "
                f"RSI={rsi_result.signal.value}"
            ),
            current_price=sma_result.current_price,
            sma_short=sma_result.sma_short,
            sma_long=sma_result.sma_long,
            rsi=rsi_result.rsi,
        )
