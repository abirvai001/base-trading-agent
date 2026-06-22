"""Tests for MarketData indicators."""

from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from agent.market import MarketData


def make_market_data(prices: list) -> MarketData:
    """Create a MarketData instance with pre-populated history."""
    config = MagicMock()
    config.contracts = {"quoter": "0x" + "0" * 40}
    config.tokens = {"WETH": "0x" + "1" * 40, "USDC": "0x" + "2" * 40}
    config.trade_token_symbol = "USDC"
    config.pool_fee = 3000

    w3 = MagicMock()
    w3.to_checksum_address.side_effect = lambda x: x
    w3.eth.contract.return_value = MagicMock()

    md = MarketData(w3, config, max_history=200)
    md._history = deque(prices, maxlen=200)
    return md


class TestSMA:
    def test_returns_none_when_insufficient_data(self):
        md = make_market_data([1.0, 2.0])
        assert md.sma(5) is None

    def test_correct_sma(self):
        md = make_market_data([1.0, 2.0, 3.0, 4.0, 5.0])
        assert md.sma(5) == pytest.approx(3.0)

    def test_sma_uses_last_n_prices(self):
        md = make_market_data([1.0, 2.0, 3.0, 10.0, 10.0])
        assert md.sma(2) == pytest.approx(10.0)


class TestRSI:
    def test_returns_none_when_insufficient_data(self):
        md = make_market_data([1.0] * 5)
        assert md.rsi(14) is None

    def test_rsi_100_when_only_gains(self):
        prices = list(range(1, 17))  # 16 prices, 15 deltas
        md = make_market_data(prices)
        assert md.rsi(14) == pytest.approx(100.0)

    def test_rsi_0_when_only_losses(self):
        prices = list(range(16, 0, -1))  # 16 prices, all declining
        md = make_market_data(prices)
        rsi = md.rsi(14)
        assert rsi is not None
        assert rsi < 10  # should be very low
