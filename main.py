"""Entry point for the Base trading agent."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Base blockchain trading agent using Uniswap V3"
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        default=os.getenv("TESTNET", "false").lower() == "true",
        help="Use Base Sepolia testnet (default: mainnet)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.getenv("DRY_RUN", "true").lower() == "true",
        help="Simulate trades without sending transactions (default: true)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("TRADE_TOKEN", "USDC"),
        help="Token symbol to trade against ETH (default: USDC)",
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=float(os.getenv("TRADE_AMOUNT_ETH", "0.01")),
        help="ETH amount per trade (default: 0.01)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("POLLING_INTERVAL_SECONDS", "60")),
        help="Polling interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=float(os.getenv("MAX_SLIPPAGE_PERCENT", "0.5")),
        help="Max slippage percent (default: 0.5)",
    )
    parser.add_argument(
        "--strategy",
        choices=["sma", "rsi", "combined"],
        default=os.getenv("STRATEGY", "combined"),
        help="Trading strategy to use (default: combined)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("main")

    private_key = os.getenv("PRIVATE_KEY", "")
    if not private_key:
        logger.error(
            "PRIVATE_KEY environment variable is not set. "
            "Copy .env.example to .env and fill in your key."
        )
        sys.exit(1)

    # Import here so dotenv is loaded first
    from agent.config import Config, PoolFee  # noqa: PLC0415
    from agent.agent import TradingAgent       # noqa: PLC0415
    from agent.strategy import (               # noqa: PLC0415
        CombinedStrategy,
        RSIStrategy,
        SMACrossoverStrategy,
    )

    config = Config(
        testnet=args.testnet,
        dry_run=args.dry_run,
        private_key=private_key,
        trade_token_symbol=args.token,
        trade_amount_eth=args.amount,
        polling_interval=args.interval,
        max_slippage_percent=args.slippage,
    )

    logger.info(
        "Starting Base Trading Agent | network=%s | token=%s | dry_run=%s",
        "Sepolia" if config.testnet else "Mainnet",
        config.trade_token_symbol,
        config.dry_run,
    )

    agent = TradingAgent(config)

    # Override strategy if specified
    if args.strategy == "sma":
        from agent.strategy import SMACrossoverStrategy  # noqa: PLC0415
        agent.strategy = SMACrossoverStrategy(
            short_window=config.sma_short_window,
            long_window=config.sma_long_window,
        )
    elif args.strategy == "rsi":
        from agent.strategy import RSIStrategy  # noqa: PLC0415
        agent.strategy = RSIStrategy(
            period=config.rsi_period,
            overbought=config.rsi_overbought,
            oversold=config.rsi_oversold,
        )

    agent.run()


if __name__ == "__main__":
    main()
