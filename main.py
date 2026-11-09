"""
Main entry point for the Taiwan NVIDIA Supply Chain Stock Tracker (main.py).

Orchestrates:
1. Historical OHLCV market data retrieval (`fetcher.py` / `scraper.py`)
2. Technical indicator calculation & cumulative return normalization (`indicators.py`)
3. Interactive multi-panel Plotly HTML dashboard generation (`visualizer.py`)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import webbrowser

from fetcher import TARGET_STOCKS, fetch_all_stocks
from indicators import build_sector_comparison_matrix, process_all_stocks
from visualizer import export_dashboard_html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options for the supply chain dashboard pipeline."""
    parser = argparse.ArgumentParser(
        description="Fetch Taiwan NVIDIA supply chain stock data and generate an interactive Plotly dashboard."
    )
    parser.add_argument(
        "--period",
        type=str,
        default="1y",
        choices=["6mo", "1y", "2y", "ytd"],
        help="Historical lookback period for yfinance (default: '1y').",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="nvidia_tw_supply_chain.html",
        help="Output HTML file path (default: 'nvidia_tw_supply_chain.html').",
    )
    parser.add_argument(
        "--default-stock",
        type=str,
        default="2330.TW",
        help="Default ticker shown in Panel 2 detailed view (default: '2330.TW').",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Force usage of direct requests + BeautifulSoup fallback scraper instead of yfinance.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Automatically open the generated HTML dashboard in the default web browser.",
    )
    return parser.parse_args(argv)


def print_summary_table(processed_data: dict) -> None:
    """Print a concise terminal summary of latest prices, indicators, and cumulative returns."""
    print("\n" + "=" * 95)
    print(
        f"{'Ticker':<10} {'Company':<20} {'Sector':<18} "
        f"{'Close (NT$)':>12} {'1D %':>8} {'Cumul %':>10} {'RSI(14)':>9}"
    )
    print("-" * 95)
    for stock in TARGET_STOCKS:
        df = processed_data.get(stock.ticker)
        if df is None or df.empty:
            continue
        latest = df.iloc[-1]
        print(
            f"{stock.ticker:<10} {stock.name:<20} {stock.sector_short:<18} "
            f"{latest['Close']:>12,.2f} {latest['Daily_Return_Pct']:>+7.2f}% "
            f"{latest['Cumulative_Return_Pct']:>+9.2f}% {latest['RSI_14']:>9.2f}"
        )
    print("=" * 95 + "\n")


def run_pipeline(
    period: str = "1y",
    output_file: str | Path = "nvidia_tw_supply_chain.html",
    default_stock: str = "2330.TW",
    use_fallback: bool = False,
    open_browser: bool = False,
) -> Path:
    """Execute the end-to-end data retrieval, indicator calculation, and visualization pipeline."""
    logging.info("Starting Taiwan NVIDIA Supply Chain analysis pipeline (period=%s)...", period)

    raw_data = fetch_all_stocks(
        stocks=TARGET_STOCKS,
        period=period,
        use_fallback_only=use_fallback,
        align_dates=True,
    )
    if not raw_data:
        raise RuntimeError("No market data could be retrieved for the target stock list.")

    logging.info("Computing technical indicators (SMA 20/60, RSI 14, MACD 12/26/9, Cumulative Return)...")
    processed_data = process_all_stocks(raw_data)

    comparison_df = build_sector_comparison_matrix(processed_data)
    logging.info(
        "Aligned %d stocks across %d trading days (%s to %s).",
        comparison_df.shape[1],
        comparison_df.shape[0],
        comparison_df.index.min().strftime("%Y-%m-%d"),
        comparison_df.index.max().strftime("%Y-%m-%d"),
    )

    print_summary_table(processed_data)

    output_path = export_dashboard_html(
        processed_data=processed_data,
        output_path=output_file,
        stocks=TARGET_STOCKS,
        default_ticker=default_stock,
    )

    if open_browser:
        webbrowser.open(output_path.as_uri())

    return output_path


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    try:
        output_path = run_pipeline(
            period=args.period,
            output_file=args.output,
            default_stock=args.default_stock,
            use_fallback=args.fallback,
            open_browser=args.open_browser,
        )
        print(f"Dashboard successfully generated: {output_path}")
        return 0
    except Exception as exc:
        logging.exception("Pipeline execution failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
