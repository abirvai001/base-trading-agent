"""Wallet management for the Base trading agent."""

import logging
from typing import Optional

from web3 import Web3
from web3.types import TxReceipt

from .config import ERC20_ABI, Config

logger = logging.getLogger(__name__)


class Wallet:
    """Manages a single EOA wallet on Base."""

    def __init__(self, w3: Web3, config: Config) -> None:
        self.w3 = w3
        self.config = config
        if not config.private_key:
            raise ValueError("PRIVATE_KEY is not set in environment.")
        self.account = w3.eth.account.from_key(config.private_key)
        self.address: str = self.account.address
        logger.info("Wallet loaded: %s", self.address)

    # ── Balances ───────────────────────────────────────────────────────────────

    def eth_balance(self) -> float:
        """Return ETH balance in ether."""
        raw = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(raw, "ether"))

    def token_balance(self, token_address: str, decimals: int = 18) -> float:
        """Return ERC-20 token balance in human-readable units."""
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        raw = contract.functions.balanceOf(self.address).call()
        return raw / 10**decimals

    # ── Approvals ──────────────────────────────────────────────────────────────

    def ensure_approval(
        self,
        token_address: str,
        spender: str,
        amount: int,
    ) -> Optional[TxReceipt]:
        """Approve *spender* to spend *amount* of *token_address* if needed."""
        token = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        allowance = token.functions.allowance(
            self.address, self.w3.to_checksum_address(spender)
        ).call()

        if allowance >= amount:
            logger.debug("Allowance already sufficient (%d >= %d)", allowance, amount)
            return None

        logger.info("Approving %s to spend token %s ...", spender, token_address)
        if self.config.dry_run:
            logger.info("[DRY-RUN] Skipping approval transaction.")
            return None

        tx = token.functions.approve(
            self.w3.to_checksum_address(spender), amount
        ).build_transaction(
            {
                "from": self.address,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "chainId": self.config.chain_id,
            }
        )
        return self._sign_and_send(tx)

    # ── Transaction helpers ────────────────────────────────────────────────────

    def _sign_and_send(self, tx: dict) -> TxReceipt:
        """Sign a transaction dict and broadcast it; wait for receipt."""
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info("Transaction sent: %s", tx_hash.hex())
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
        logger.info("Transaction confirmed in block %d", receipt["blockNumber"])
        return receipt
