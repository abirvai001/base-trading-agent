"""Trade execution via Uniswap V3 on Base."""

import logging
import time
from typing import Optional

from web3 import Web3
from web3.types import TxReceipt

from .config import SWAP_ROUTER_ABI, TOKEN_DECIMALS, Config
from .wallet import Wallet

logger = logging.getLogger(__name__)

# Deadline buffer: 20 minutes from now
_DEADLINE_BUFFER = 20 * 60


class TradeExecutor:
    """Builds and submits Uniswap V3 swap transactions on Base."""

    def __init__(self, w3: Web3, config: Config, wallet: Wallet) -> None:
        self.w3 = w3
        self.config = config
        self.wallet = wallet
        self.router = w3.eth.contract(
            address=w3.to_checksum_address(config.contracts["swap_router"]),
            abi=SWAP_ROUTER_ABI,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def buy(
        self,
        token_out_symbol: Optional[str] = None,
        amount_in_wei: Optional[int] = None,
        quoted_amount_out: Optional[int] = None,
    ) -> Optional[TxReceipt]:
        """Swap ETH → *token_out_symbol* on Uniswap V3."""
        token_out_symbol = token_out_symbol or self.config.trade_token_symbol
        amount_in_wei = amount_in_wei or self.config.trade_amount_wei
        token_out_addr = self.config.tokens.get(token_out_symbol)
        weth_addr = self.config.tokens.get("WETH")

        if not token_out_addr or not weth_addr:
            logger.error("Unknown token: %s", token_out_symbol)
            return None

        amount_out_min = self._apply_slippage(quoted_amount_out) if quoted_amount_out else 0

        logger.info(
            "BUY %s: spending %.6f ETH (min out: %d raw units)",
            token_out_symbol,
            amount_in_wei / 1e18,
            amount_out_min,
        )

        return self._swap(
            token_in=weth_addr,
            token_out=token_out_addr,
            amount_in=amount_in_wei,
            amount_out_min=amount_out_min,
            value=amount_in_wei,  # send ETH with the tx
        )

    def sell(
        self,
        token_in_symbol: Optional[str] = None,
        amount_in_raw: Optional[int] = None,
        quoted_amount_out: Optional[int] = None,
    ) -> Optional[TxReceipt]:
        """Swap *token_in_symbol* → ETH on Uniswap V3."""
        token_in_symbol = token_in_symbol or self.config.trade_token_symbol
        token_in_addr = self.config.tokens.get(token_in_symbol)
        weth_addr = self.config.tokens.get("WETH")

        if not token_in_addr or not weth_addr:
            logger.error("Unknown token: %s", token_in_symbol)
            return None

        decimals = TOKEN_DECIMALS.get(token_in_symbol, 18)
        if amount_in_raw is None:
            # Default: sell the full token balance
            balance = self.wallet.token_balance(token_in_addr, decimals)
            amount_in_raw = int(balance * 10**decimals)

        if amount_in_raw == 0:
            logger.warning("Nothing to sell – zero balance of %s", token_in_symbol)
            return None

        amount_out_min = self._apply_slippage(quoted_amount_out) if quoted_amount_out else 0

        logger.info(
            "SELL %s: amount=%d raw units (min ETH out: %d wei)",
            token_in_symbol,
            amount_in_raw,
            amount_out_min,
        )

        # Approve router to spend the token
        self.wallet.ensure_approval(
            token_in_addr,
            self.config.contracts["swap_router"],
            amount_in_raw,
        )

        return self._swap(
            token_in=token_in_addr,
            token_out=weth_addr,
            amount_in=amount_in_raw,
            amount_out_min=amount_out_min,
            value=0,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        amount_out_min: int,
        value: int,
    ) -> Optional[TxReceipt]:
        """Build, optionally simulate, and send an exactInputSingle swap."""
        params = {
            "tokenIn": self.w3.to_checksum_address(token_in),
            "tokenOut": self.w3.to_checksum_address(token_out),
            "fee": int(self.config.pool_fee),
            "recipient": self.wallet.address,
            "amountIn": amount_in,
            "amountOutMinimum": amount_out_min,
            "sqrtPriceLimitX96": 0,
        }

        tx_data = self.router.functions.exactInputSingle(params)

        if self.config.dry_run:
            try:
                gas_estimate = tx_data.estimate_gas(
                    {"from": self.wallet.address, "value": value}
                )
                logger.info(
                    "[DRY-RUN] Swap simulated OK. Estimated gas: %d", gas_estimate
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[DRY-RUN] Simulation failed: %s", exc)
            return None

        tx = tx_data.build_transaction(
            {
                "from": self.wallet.address,
                "value": value,
                "nonce": self.w3.eth.get_transaction_count(self.wallet.address),
                "chainId": self.config.chain_id,
                "gas": self._estimate_gas(tx_data, value),
            }
        )
        return self.wallet._sign_and_send(tx)

    def _estimate_gas(self, tx_data, value: int) -> int:
        """Estimate gas with a 20% buffer."""
        try:
            estimate = tx_data.estimate_gas(
                {"from": self.wallet.address, "value": value}
            )
            return int(estimate * 1.2)
        except Exception:  # noqa: BLE001
            return 300_000  # fallback

    def _apply_slippage(self, amount: int) -> int:
        """Apply slippage tolerance to a quoted amount."""
        return int(amount * (10_000 - self.config.slippage_bps) // 10_000)

    @staticmethod
    def _deadline() -> int:
        return int(time.time()) + _DEADLINE_BUFFER
