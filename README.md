# Base Trading Agent

An autonomous trading agent for the [Base](https://base.org) blockchain (Ethereum L2 by Coinbase), written in Python. It fetches live prices from **Uniswap V3** on Base and executes trades based on configurable strategies.

> **⚠️ Risk Warning:** Automated trading involves significant financial risk. Always start with `DRY_RUN=true` and test on Base Sepolia before using real funds. Never risk more than you can afford to lose.

## Features

- **Live price feeds** via Uniswap V3 QuoterV2 on Base Mainnet / Sepolia
- **Three strategies**: SMA Crossover, RSI mean-reversion, or Combined (both must agree)
- **Risk management**: stop-loss, take-profit, max position size
- **Dry-run mode** (default): simulates trades with gas estimation, no real transactions
- **Fully configurable** via CLI flags or `.env` file

## Architecture

```
agent/
├── config.py      # Network constants, contract addresses, token list
├── wallet.py      # ETH/ERC-20 balance queries, tx signing, approvals
├── market.py      # Uniswap V3 price quotes, SMA & RSI indicators
├── strategy.py    # SMA crossover, RSI, and combined strategy
├── executor.py    # exactInputSingle swap builder & sender
└── agent.py       # Polling loop, risk management, orchestration
main.py            # CLI entry point
```

## Quick Start

### 1. Clone & install

```bash
git clone https://gitlab.com/abirodroid-1/base-trading-agent.git
cd base-trading-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env – set PRIVATE_KEY and review all settings
```

### 3. Run on testnet (Base Sepolia) in dry-run mode

```bash
python main.py --testnet --dry-run --token USDC --interval 30
```

### 4. Run on mainnet (when ready)

```bash
# Edit .env: set DRY_RUN=false, TESTNET=false
python main.py --token USDC --amount 0.01 --strategy combined
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--testnet` | `false` | Use Base Sepolia testnet |
| `--dry-run` | `true` | Simulate without sending transactions |
| `--token` | `USDC` | Token to trade against ETH |
| `--amount` | `0.01` | ETH amount per trade |
| `--interval` | `60` | Polling interval in seconds |
| `--slippage` | `0.5` | Max slippage percent |
| `--strategy` | `combined` | `sma` \| `rsi` \| `combined` |
| `--log-level` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

## Strategies

**SMA Crossover** – Buys when the short-window SMA crosses above the long-window SMA (bullish momentum), sells on the reverse crossover.

**RSI** – Buys when RSI < 30 (oversold), sells when RSI > 70 (overbought).

**Combined** (default) – Both SMA and RSI must agree on the same signal before a trade is placed, reducing false positives.

## Supported Tokens (Base Mainnet)

| Symbol | Address |
|--------|---------|
| WETH | `0x4200000000000000000000000000000000000006` |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| DAI | `0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb` |
| cbETH | `0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22` |

## Running Tests

```bash
pytest tests/ -v
```

## Security

- **Never commit your `.env` file** – it is in `.gitignore`
- Use a **dedicated trading wallet** with only the funds you intend to trade
- Consider using a **private RPC endpoint** (Alchemy, QuickNode, Coinbase Developer Platform) for reliability and privacy
- Review and audit the code before enabling live trading

## License

MIT
