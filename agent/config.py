"""Configuration and constants for the Base trading agent."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict


class Network:
    """Base network RPC endpoints and chain IDs."""

    MAINNET_RPC = "https://mainnet.base.org"
    TESTNET_RPC = "https://sepolia.base.org"
    MAINNET_CHAIN_ID = 8453
    TESTNET_CHAIN_ID = 84532


class PoolFee(IntEnum):
    """Uniswap V3 pool fee tiers (in hundredths of a bip)."""

    LOWEST = 100    # 0.01%
    LOW = 500       # 0.05%
    MEDIUM = 3000   # 0.30%
    HIGH = 10000    # 1.00%


# ── Contract addresses on Base Mainnet ────────────────────────────────────────
CONTRACTS_MAINNET: Dict[str, str] = {
    "swap_router": "0x2626664c2603336E57B271c5C0b26F421741e481",  # SwapRouter02
    "quoter": "0x3d4e44Eb1374240CE5F1B136041212501e4a098e",       # QuoterV2
    "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
}

CONTRACTS_TESTNET: Dict[str, str] = {
    "swap_router": "0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4",
    "quoter": "0xC5290058841028F1614F3A6F0F5816cAd0df5E27",
    "factory": "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24",
}

# ── Token addresses on Base Mainnet ───────────────────────────────────────────
TOKENS_MAINNET: Dict[str, str] = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "DAI":  "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "CBETH": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
    "USDBC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
}

TOKENS_TESTNET: Dict[str, str] = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
}

# ── Token decimals ─────────────────────────────────────────────────────────────
TOKEN_DECIMALS: Dict[str, int] = {
    "WETH": 18,
    "USDC": 6,
    "DAI": 18,
    "CBETH": 18,
    "USDBC": 6,
    "ETH": 18,
}

# ── Uniswap V3 ABIs (minimal, inline) ─────────────────────────────────────────
SWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IV3SwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass
class Config:
    """Runtime configuration for the trading agent."""

    # Network
    testnet: bool = False
    rpc_url: str = ""
    chain_id: int = 0

    # Wallet
    private_key: str = ""

    # Trading
    trade_token_symbol: str = "USDC"   # token to buy/sell against ETH
    trade_amount_eth: float = 0.01     # ETH amount per trade
    max_slippage_percent: float = 0.5  # 0.5%
    pool_fee: PoolFee = PoolFee.MEDIUM

    # Strategy
    sma_short_window: int = 5
    sma_long_window: int = 20
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # Risk management
    max_position_eth: float = 0.1      # max ETH value in open position
    stop_loss_percent: float = 5.0     # 5% stop loss
    take_profit_percent: float = 10.0  # 10% take profit

    # Agent
    polling_interval: int = 60         # seconds between price checks
    dry_run: bool = True               # simulate without sending txs

    # Derived (populated in __post_init__)
    contracts: Dict[str, str] = field(default_factory=dict)
    tokens: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rpc_url:
            self.rpc_url = Network.TESTNET_RPC if self.testnet else Network.MAINNET_RPC
        if not self.chain_id:
            self.chain_id = Network.TESTNET_CHAIN_ID if self.testnet else Network.MAINNET_CHAIN_ID
        if not self.contracts:
            self.contracts = CONTRACTS_TESTNET if self.testnet else CONTRACTS_MAINNET
        if not self.tokens:
            self.tokens = TOKENS_TESTNET if self.testnet else TOKENS_MAINNET

    @property
    def slippage_bps(self) -> int:
        """Slippage tolerance in basis points."""
        return int(self.max_slippage_percent * 100)

    @property
    def trade_amount_wei(self) -> int:
        """Trade amount in wei."""
        return int(self.trade_amount_eth * 10**18)
