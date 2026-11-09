"""
Market data retrieval and preprocessing module (fetcher.py).

Handles fetching daily OHLCV market data for Taiwan NVIDIA supply chain stocks
primarily via `yfinance`, with automatic fallback to `scraper.py` (`requests` +
`BeautifulSoup`) and edge-case handling for non-trading days, missing volume,
and cross-stock date alignment.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from scraper import extract_stock_code, fetch_stock_fallback_scraper

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StockInfo:
    """Metadata for a tracked Taiwan NVIDIA supply chain stock."""

    ticker: str
    name: str
    sector: str
    sector_short: str

    @property
    def code(self) -> str:
        """Numeric stock code (e.g., '2330')."""
        return extract_stock_code(self.ticker)

    @property
    def label(self) -> str:
        """Human-readable label (e.g., '2330.TW (TSMC)')."""
        return f"{self.ticker} ({self.name})"


# Target Stock List defined in prompt specification
TARGET_STOCKS: List[StockInfo] = [
    # Foundry & Advanced Packaging
    StockInfo("2330.TW", "TSMC", "Foundry & Advanced Packaging", "Foundry"),
    StockInfo("3711.TW", "ASE Technology", "Foundry & Advanced Packaging", "Foundry"),
    StockInfo("2449.TW", "KYEC", "Foundry & Advanced Packaging", "Foundry"),
    # AI Server ODMs
    StockInfo("2317.TW", "Hon Hai", "AI Server ODMs", "ODM"),
    StockInfo("2382.TW", "Quanta", "AI Server ODMs", "ODM"),
    StockInfo("6669.TW", "Wiwynn", "AI Server ODMs", "ODM"),
    StockInfo("3231.TW", "Wistron", "AI Server ODMs", "ODM"),
    StockInfo("2376.TW", "Gigabyte", "AI Server ODMs", "ODM"),
    # Liquid Cooling & Thermal
    StockInfo("3017.TW", "CCI", "Liquid Cooling & Thermal", "Cooling"),
    StockInfo("3324.TW", "Auras", "Liquid Cooling & Thermal", "Cooling"),
    StockInfo("3653.TW", "Jentech", "Liquid Cooling & Thermal", "Cooling"),
    # Power & Infrastructure
    StockInfo("2308.TW", "Delta Electronics", "Power & Infrastructure", "Power/Components"),
    StockInfo("2059.TW", "King Slide", "Power & Infrastructure", "Power/Components"),
    StockInfo("3665.TW", "BizLink-KY", "Power & Infrastructure", "Power/Components"),
    # PCB & CCL
    StockInfo("2383.TW", "Elite Material", "PCB & CCL", "PCB & CCL"),
    StockInfo("3037.TW", "Unimicron", "PCB & CCL", "PCB & CCL"),
]

OHLCV_COLUMNS: List[str] = ["Open", "High", "Low", "Close", "Volume"]


def _normalize_yfinance_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw yfinance DataFrame into standard single-level OHLCV columns."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    missing = [col for col in OHLCV_COLUMNS if col not in out.columns]
    if missing:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = out[OHLCV_COLUMNS].copy()
    out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.index = out.index.normalize()
    out.index.name = "Date"
    return out.sort_index()


def clean_ohlcv_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw OHLCV DataFrame and handle market data edge cases:
    - Drop non-trading days (weekends, rows with NaN Close or all-zero OHLC).
    - Sanitize missing or negative Volume values.
    - Fill missing Open/High/Low on valid trading days using Close price.
    - Deduplicate and sort DatetimeIndex chronologically.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    cleaned = df.copy()
    cleaned.index = pd.to_datetime(cleaned.index)
    if cleaned.index.tz is not None:
        cleaned.index = cleaned.index.tz_localize(None)
    cleaned.index = cleaned.index.normalize()
    cleaned.index.name = "Date"

    # Remove duplicate dates, keeping the most recent record
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()

    # Coerce columns to numeric
    for col in OHLCV_COLUMNS:
        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    # Drop weekends (Saturday=5, Sunday=6) and rows missing Close price
    cleaned = cleaned[cleaned.index.dayofweek < 5]
    cleaned = cleaned.dropna(subset=["Close"])
    cleaned = cleaned[cleaned["Close"] > 0]

    # Handle missing Volume: replace NaN or negative volume with 0,
    # and drop phantom non-trading holiday entries where Volume == 0 and O==H==L==C unchanged
    cleaned["Volume"] = cleaned["Volume"].fillna(0.0).clip(lower=0.0)
    price_unchanged = (
        (cleaned["Open"] == cleaned["Close"])
        & (cleaned["High"] == cleaned["Close"])
        & (cleaned["Low"] == cleaned["Close"])
        & (cleaned["Close"].diff() == 0)
    )
    phantom_holiday = (cleaned["Volume"] == 0) & price_unchanged
    cleaned = cleaned[~phantom_holiday]

    # Fill missing Open, High, Low with Close if partially missing on a valid trading day
    for price_col in ["Open", "High", "Low"]:
        cleaned[price_col] = cleaned[price_col].fillna(cleaned["Close"])

    # Ensure High >= max(Open, Close) and Low <= min(Open, Close)
    cleaned["High"] = cleaned[["Open", "High", "Low", "Close"]].max(axis=1)
    cleaned["Low"] = cleaned[["Open", "High", "Low", "Close"]].min(axis=1)

    return cleaned[OHLCV_COLUMNS]


def fetch_stock_yfinance(
    ticker: str,
    period: str = "1y",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a Taiwan stock using `yfinance`.

    Automatically attempts alternate exchange suffix (`.TWO` vs `.TW`) if the
    initial ticker returns no data (e.g., TPEx-listed stocks such as 3324 Auras).

    Args:
        ticker: Stock ticker symbol (e.g., '2330.TW' or '3324.TW').
        period: Lookback period for yfinance (default '1y' for 12 months).
        start: Optional start date string ('YYYY-MM-DD').
        end: Optional end date string ('YYYY-MM-DD').

    Returns:
        Cleaned OHLCV DataFrame indexed by Date.
    """
    code = extract_stock_code(ticker)
    candidate_tickers = [ticker]
    if ticker.upper().endswith(".TW"):
        candidate_tickers.append(f"{code}.TWO")
    elif ticker.upper().endswith(".TWO"):
        candidate_tickers.append(f"{code}.TW")
    else:
        candidate_tickers.extend([f"{code}.TW", f"{code}.TWO"])

    yf_logger = logging.getLogger("yfinance")
    prev_level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)
    try:
        for candidate in candidate_tickers:
            try:
                yf_ticker = yf.Ticker(candidate)
                if start or end:
                    raw_df = yf_ticker.history(start=start, end=end, interval="1d", auto_adjust=False)
                else:
                    raw_df = yf_ticker.history(period=period, interval="1d", auto_adjust=False)

                norm_df = _normalize_yfinance_df(raw_df)
                cleaned_df = clean_ohlcv_dataframe(norm_df)
                if not cleaned_df.empty:
                    if candidate != ticker:
                        logger.info("Resolved %s -> %s (TPEx/TWSE suffix)", ticker, candidate)
                    return cleaned_df
            except Exception as exc:
                logger.debug("yfinance candidate %s failed: %s", candidate, exc)
    finally:
        yf_logger.setLevel(prev_level)

    return pd.DataFrame(columns=OHLCV_COLUMNS)


def fetch_stock_data(
    ticker: str,
    period: str = "1y",
    use_fallback_only: bool = False,
    fallback_months: int = 6,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a stock using `yfinance` primary method and
    `requests` + `BeautifulSoup` fallback scraper if primary retrieval fails.
    """
    if not use_fallback_only:
        df = fetch_stock_yfinance(ticker=ticker, period=period)
        if not df.empty:
            return df
        logger.warning("Primary yfinance fetch empty for %s; invoking fallback scraper...", ticker)

    raw_fallback = fetch_stock_fallback_scraper(ticker=ticker, months=fallback_months)
    return clean_ohlcv_dataframe(raw_fallback)


def align_stock_dataframes(
    stock_frames: Dict[str, pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    """
    Align dates across all retrieved stock DataFrames to a common trading calendar.

    Uses the union of valid trading dates where at least half of the tracked stocks
    traded (eliminating isolated erroneous dates), and forward-fills occasional
    single-stock trading halts with zero volume on halted days.
    """
    non_empty = {k: v for k, v in stock_frames.items() if v is not None and not v.empty}
    if not non_empty:
        return {}

    # Count how many stocks have data on each date to build the canonical trading calendar
    combined_dates = pd.concat(
        [pd.Series(1, index=df.index) for df in non_empty.values()]
    )
    date_counts = combined_dates.groupby(level=0).sum()

    min_stocks_threshold = max(1, len(non_empty) // 2)
    common_dates = date_counts[date_counts >= min_stocks_threshold].index.sort_values()

    aligned: Dict[str, pd.DataFrame] = {}
    for ticker, df in non_empty.items():
        reindexed = df.reindex(common_dates)
        # Forward-fill then back-fill leading price gaps if a stock started trading slightly later
        reindexed["Close"] = reindexed["Close"].ffill().bfill()
        for col in ["Open", "High", "Low"]:
            reindexed[col] = reindexed[col].fillna(reindexed["Close"])
        reindexed["Volume"] = reindexed["Volume"].fillna(0.0)
        reindexed.index.name = "Date"
        aligned[ticker] = reindexed[OHLCV_COLUMNS]

    return aligned


def fetch_all_stocks(
    stocks: Optional[List[StockInfo]] = None,
    period: str = "1y",
    use_fallback_only: bool = False,
    align_dates: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch and clean historical OHLCV data for all target NVIDIA supply chain stocks.

    Args:
        stocks: List of StockInfo objects (defaults to TARGET_STOCKS).
        period: Historical period string for yfinance (e.g., '6mo', '1y').
        use_fallback_only: Force usage of BeautifulSoup fallback scraper.
        align_dates: Whether to align all stocks to a canonical trading calendar.

    Returns:
        Dictionary mapping canonical ticker (e.g., '2330.TW') to cleaned DataFrame.
    """
    target_list = stocks or TARGET_STOCKS
    results: Dict[str, pd.DataFrame] = {}

    for stock in target_list:
        logger.info("Fetching market data for %s (%s)...", stock.ticker, stock.name)
        df = fetch_stock_data(
            ticker=stock.ticker,
            period=period,
            use_fallback_only=use_fallback_only,
        )
        if df.empty:
            logger.error("Failed to retrieve data for %s (%s)", stock.ticker, stock.name)
            continue
        results[stock.ticker] = df

    if align_dates and results:
        results = align_stock_dataframes(results)

    return results
