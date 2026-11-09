"""
Direct scraping and fallback market data retrieval module (scraper.py).

Provides fallback data retrieval for Taiwan stocks (TWSE / TPEx) using
`requests` and `BeautifulSoup` with proper User-Agent headers and rate
limiting (`time.sleep`) to prevent IP bans when `yfinance` is unavailable.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "Connection": "keep-alive",
}


def extract_stock_code(ticker: str) -> str:
    """Extract numeric Taiwan stock code from Yahoo Finance ticker (e.g., '2330.TW' -> '2330')."""
    return ticker.split(".")[0].strip()


def _parse_roc_date(roc_date_str: str) -> Optional[pd.Timestamp]:
    """Convert Taiwan ROC calendar date string (e.g., '113/05/20') to pd.Timestamp."""
    cleaned = roc_date_str.strip().replace("-", "/")
    parts = cleaned.split("/")
    if len(parts) != 3:
        return None
    try:
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return pd.Timestamp(year=year, month=month, day=day)
    except ValueError:
        return None


def _clean_numeric(val: str) -> Optional[float]:
    """Parse numeric string with commas or '--' placeholders into float."""
    cleaned = val.strip().replace(",", "").replace("X", "").replace("+", "")
    if not cleaned or cleaned in {"--", "---", "N/A", "null"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def scrape_twse_month_html(
    stock_code: str,
    year: int,
    month: int,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """
    Scrape a single month of daily OHLCV data from TWSE HTML report using BeautifulSoup.

    Args:
        stock_code: 4-digit Taiwan stock code (e.g., '2330').
        year: Gregorian year (e.g., 2026).
        month: Month number (1-12).
        session: Optional requests.Session instance.

    Returns:
        DataFrame with DatetimeIndex and columns ['Open', 'High', 'Low', 'Close', 'Volume'].
    """
    req_session = session or requests.Session()
    date_param = f"{year:04d}{month:02d}01"
    url = (
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        f"?response=html&date={date_param}&stockNo={stock_code}"
    )

    resp = req_session.get(url, headers=DEFAULT_HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()

    rows: List[Dict[str, object]] = []
    tbody = table.find("tbody")
    tr_elements = tbody.find_all("tr") if tbody else table.find_all("tr")

    for tr in tr_elements:
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        # TWSE STOCK_DAY columns:
        # 0: Date, 1: Trade Volume (Shares), 2: Trade Value, 3: Opening Price,
        # 4: Highest Price, 5: Lowest Price, 6: Closing Price, 7: Change, 8: Transaction
        if len(cols) < 7:
            continue
        parsed_date = _parse_roc_date(cols[0])
        if parsed_date is None:
            continue

        volume = _clean_numeric(cols[1])
        open_p = _clean_numeric(cols[3])
        high_p = _clean_numeric(cols[4])
        low_p = _clean_numeric(cols[5])
        close_p = _clean_numeric(cols[6])

        if close_p is None:
            continue

        rows.append(
            {
                "Date": parsed_date,
                "Open": open_p if open_p is not None else close_p,
                "High": high_p if high_p is not None else close_p,
                "Low": low_p if low_p is not None else close_p,
                "Close": close_p,
                "Volume": volume if volume is not None else 0.0,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("Date").sort_index()
    return df


def scrape_tpex_month_html(
    stock_code: str,
    year: int,
    month: int,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """
    Scrape a single month of daily OHLCV data for TPEx (OTC) stocks.

    Uses TPEx web report / JSON-HTML endpoint parsed with BeautifulSoup / JSON fallback.
    """
    req_session = session or requests.Session()
    roc_year = year - 1911
    date_param = f"{roc_year}/{month:02d}"
    url = (
        "https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/"
        f"st43_print.php?l=zh-tw&d={date_param}&stkno={stock_code}&s=0,asc,0"
    )

    resp = req_session.get(url, headers=DEFAULT_HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()

    rows: List[Dict[str, object]] = []
    for tr in table.find_all("tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        # TPEx st43 columns:
        # 0: Date, 1: Volume (1,000 shares), 2: Turnover, 3: Open, 4: High, 5: Low, 6: Close
        if len(cols) < 7:
            continue
        parsed_date = _parse_roc_date(cols[0])
        if parsed_date is None:
            continue

        vol_lots = _clean_numeric(cols[1])
        open_p = _clean_numeric(cols[3])
        high_p = _clean_numeric(cols[4])
        low_p = _clean_numeric(cols[5])
        close_p = _clean_numeric(cols[6])

        if close_p is None:
            continue

        rows.append(
            {
                "Date": parsed_date,
                "Open": open_p if open_p is not None else close_p,
                "High": high_p if high_p is not None else close_p,
                "Low": low_p if low_p is not None else close_p,
                "Close": close_p,
                "Volume": (vol_lots * 1000.0) if vol_lots is not None else 0.0,
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("Date").sort_index()


def _iter_recent_year_months(months: int, end_date: Optional[dt.date] = None) -> List[Tuple[int, int]]:
    """Generate list of (year, month) tuples covering the past `months` months."""
    ref = end_date or dt.date.today()
    year, month = ref.year, ref.month
    result: List[Tuple[int, int]] = []
    for _ in range(months):
        result.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    result.reverse()
    return result


def fetch_stock_fallback_scraper(
    ticker: str,
    months: int = 6,
    rate_limit_seconds: float = 1.5,
) -> pd.DataFrame:
    """
    Fallback scraper fetching daily OHLCV data via requests + BeautifulSoup.

    Applies proper User-Agent headers and rate-limiting (`time.sleep`) between
    HTTP requests to avoid IP bans on TWSE / TPEx servers.

    Args:
        ticker: Stock symbol (e.g., '2330.TW' or '3324.TWO').
        months: Number of months of historical data to retrieve (6 to 12).
        rate_limit_seconds: Delay in seconds between consecutive HTTP requests.

    Returns:
        Cleaned OHLCV DataFrame indexed by Date.
    """
    stock_code = extract_stock_code(ticker)
    is_tpex = ticker.upper().endswith(".TWO")
    year_months = _iter_recent_year_months(months=months)
    monthly_frames: List[pd.DataFrame] = []

    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)
        for idx, (year, month) in enumerate(year_months):
            try:
                if not is_tpex:
                    df_month = scrape_twse_month_html(stock_code, year, month, session=session)
                    if df_month.empty:
                        df_month = scrape_tpex_month_html(stock_code, year, month, session=session)
                else:
                    df_month = scrape_tpex_month_html(stock_code, year, month, session=session)
                    if df_month.empty:
                        df_month = scrape_twse_month_html(stock_code, year, month, session=session)

                if not df_month.empty:
                    monthly_frames.append(df_month)
            except requests.RequestException as exc:
                logger.warning(
                    "Fallback scraper request failed for %s (%04d-%02d): %s",
                    ticker,
                    year,
                    month,
                    exc,
                )

            if idx < len(year_months) - 1 and rate_limit_seconds > 0:
                time.sleep(rate_limit_seconds)

    if not monthly_frames:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    combined = pd.concat(monthly_frames, axis=0)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined
