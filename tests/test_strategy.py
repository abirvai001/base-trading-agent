"""Tests for trading strategies."""

from collections import deque
from unittest.mock import MagicMock

import pytest

from agent.strategy import (
    CombinedStrategy,
    RSIStrategy,
    Signal,
    SMACrossoverStrategy,
)


def make_market(prices: list) -> MagicMock:
    """Create a mock MarketData with a fixed price history."""
    market = MagicMock()
    market.prices = prices
    market._history = deque(prices)

    def sma(window):
        if len(prices) < window:
            return None
        return sum(prices[-window:]) / window

    def rsi(period=14):
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

    market.sma.side_effect = sma
    market.rsi.side_effect = rsi
    return market


class TestSMACrossoverStrategy:
    def test_hold_during_warmup(self):
        strategy = SMACrossoverStrategy(short_window=5, long_window=20)
        market = make_market([100.0] * 10)  # fewer than long_window
        result = strategy.evaluate(market)
        assert result.signal == Signal.HOLD

    def test_buy_signal_on_crossover(self):
        strategy = SMACrossoverStrategy(short_window=3, long_window=5)
        # First call: short < long (bearish)
        market1 = make_market([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
        strategy.evaluate(market1)
        # Second call: short > long (bullish crossover)
        market2 = make_market([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = strategy.evaluate(market2)
        assert result.signal == Signal.BUY

    def test_sell_signal_on_crossover(self):
        strategy = SMACrossoverStrategy(short_window=3, long_window=5)
        # First call: short > long (bullish)
        market1 = make_market([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        strategy.evaluate(market1)
        # Second call: short < long (bearish crossover)
        market2 = make_market([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
        result = strategy.evaluate(market2)
        assert result.signal == Signal.SELL


class TestRSIStrategy:
    def test_hold_during_warmup(self):
        strategy = RSIStrategy(period=14)
        market = make_market([100.0] * 5)
        result = strategy.evaluate(market)
        assert result.signal == Signal.HOLD

    def test_buy_when_oversold(self):
        strategy = RSIStrategy(period=5, oversold=30.0)
        # Strongly declining prices → low RSI
        prices = [100, 90, 80, 70, 60, 50]
        market = make_market(prices)
        result = strategy.evaluate(market)
        assert result.signal == Signal.BUY

    def test_sell_when_overbought(self):
        strategy = RSIStrategy(period=5, overbought=70.0)
        # Strongly rising prices → high RSI
        prices = [50, 60, 70, 80, 90, 100]
        market = make_market(prices)
        result = strategy.evaluate(market)
        assert result.signal == Signal.SELL


class TestCombinedStrategy:
    def test_hold_when_strategies_disagree(self):
        sma = SMACrossoverStrategy(short_window=3, long_window=5)
        rsi = RSIStrategy(period=5)
        combined = CombinedStrategy(sma, rsi)
        market = make_market([100.0] * 20)
        result = combined.evaluate(market)
        assert result.signal == Signal.HOLD
