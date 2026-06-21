"""Tests for Wallet."""

from unittest.mock import MagicMock, patch

import pytest

from agent.wallet import Wallet


def make_wallet(dry_run: bool = True) -> tuple:
    config = MagicMock()
    config.private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # Hardhat test key
    config.chain_id = 84532
    config.dry_run = dry_run

    w3 = MagicMock()
    w3.eth.account.from_key.return_value = MagicMock(
        address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    )
    w3.to_checksum_address.side_effect = lambda x: x

    wallet = Wallet(w3, config)
    return wallet, w3, config


class TestWallet:
    def test_address_loaded(self):
        wallet, _, _ = make_wallet()
        assert wallet.address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

    def test_eth_balance(self):
        wallet, w3, _ = make_wallet()
        w3.eth.get_balance.return_value = 10**18  # 1 ETH in wei
        w3.from_wei.return_value = 1.0
        assert wallet.eth_balance() == pytest.approx(1.0)

    def test_missing_private_key_raises(self):
        config = MagicMock()
        config.private_key = ""
        w3 = MagicMock()
        with pytest.raises(ValueError, match="PRIVATE_KEY"):
            Wallet(w3, config)

    def test_ensure_approval_skips_when_sufficient(self):
        wallet, w3, config = make_wallet(dry_run=False)
        token_contract = MagicMock()
        token_contract.functions.allowance.return_value.call.return_value = 10**30
        w3.eth.contract.return_value = token_contract

        result = wallet.ensure_approval("0x" + "a" * 40, "0x" + "b" * 40, 100)
        assert result is None  # no tx needed
