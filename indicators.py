"""
Technical indicators and return normalization module (indicators.py).

Computes standard technical metrics for each stock using `pandas`:
- Moving Averages: SMA 20, SMA 60
- Relative Strength Index: RSI (14)
- Moving Average Convergence Divergence: MACD (12, 26, 9)
- Daily % change and Cumulative performance (% return normalized from start date)
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def calculate_sma(
    df: pd.DataFrame,
    windows: Tuple[int, ...] = (20, 60),
    price_col: str = "Close",
) -> pd.DataFrame:
    """
    Calculate Simple Moving Averages (SMA) for the given window lengths.

    Args:
        df: Input OHLCV DataFrame containing `price_col`.
        windows: Tuple of rolling window lengths (default: 20, 60).
        price_col: Column name on which to compute SMA.

    Returns:
        DataFrame with added `SMA_<window>` columns.
    """
    out = df.copy()
    for window in windows:
        out[f"SMA_{window}"] = out[price_col].rolling(window=window, min_periods=1).mean()
    return out


def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
    price_col: str = "Close",
) -> pd.DataFrame:
    """
    Calculate Relative Strength Index (RSI) using Wilder's smoothing method.

    Args:
        df: Input OHLCV DataFrame containing `price_col`.
        period: Lookback window for RSI (default: 14).
        price_col: Column name on which to compute RSI.

    Returns:
        DataFrame with added `RSI_<period>` column (bounded 0 to 100).
    """
    out = df.copy()
    delta = out[price_col].diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's exponential moving average (alpha = 1 / period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Where avg_loss == 0 and avg_gain > 0, RSI is 100; where both are 0, RSI is 50
    rsi = np.where((avg_loss == 0) & (avg_gain > 0), 100.0, rsi)
    rsi = np.where((avg_loss == 0) & (avg_gain == 0), 50.0, rsi)

    out[f"RSI_{period}"] = pd.Series(rsi, index=out.index).bfill().fillna(50.0)
    return out


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    price_col: str = "Close",
) -> pd.DataFrame:
    """
    Calculate MACD (Moving Average Convergence Divergence) line, signal line, and histogram.

    Args:
        df: Input OHLCV DataFrame containing `price_col`.
        fast: Fast EMA span (default: 12).
        slow: Slow EMA span (default: 26).
        signal: Signal EMA span (default: 9).
        price_col: Column name on which to compute MACD.

    Returns:
        DataFrame with added `MACD`, `MACD_Signal`, and `MACD_Hist` columns.
    """
    out = df.copy()
    ema_fast = out[price_col].ewm(span=fast, adjust=False).mean()
    ema_slow = out[price_col].ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line

    out["MACD"] = macd_line
    out["MACD_Signal"] = signal_line
    out["MACD_Hist"] = macd_hist
    return out


def calculate_cumulative_performance(
    df: pd.DataFrame,
    price_col: str = "Close",
) -> pd.DataFrame:
    """
    Calculate daily percentage change and cumulative percentage return normalized
    from the start date (`0.0%` baseline at the first valid close price).

    Args:
        df: Input OHLCV DataFrame containing `price_col`.
        price_col: Column name on which to compute returns.

    Returns:
        DataFrame with added `Daily_Return_Pct` and `Cumulative_Return_Pct` columns.
    """
    out = df.copy()
    out["Daily_Return_Pct"] = out[price_col].pct_change().fillna(0.0) * 100.0

    valid_prices = out[price_col].dropna()
    if valid_prices.empty or valid_prices.iloc[0] == 0:
        out["Cumulative_Return_Pct"] = 0.0
    else:
        baseline_price = float(valid_prices.iloc[0])
        out["Cumulative_Return_Pct"] = ((out[price_col] / baseline_price) - 1.0) * 100.0

    return out


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run the complete indicator calculation pipeline on a single stock DataFrame:
    - SMA 20 & SMA 60
    - RSI 14
    - MACD (12, 26, 9)
    - Daily % Change & Cumulative % Performance from start date
    """
    if df is None or df.empty:
        return pd.DataFrame()

    enriched = calculate_sma(df, windows=(20, 60))
    enriched = calculate_rsi(enriched, period=14)
    enriched = calculate_macd(enriched, fast=12, slow=26, signal=9)
    enriched = calculate_cumulative_performance(enriched)
    return enriched


def process_all_stocks(
    stock_frames: Dict[str, pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    """
    Compute technical indicators and cumulative performance for all stocks.

    Args:
        stock_frames: Dictionary mapping ticker symbol to cleaned OHLCV DataFrame.

    Returns:
        Dictionary mapping ticker symbol to indicator-enriched DataFrame.
    """
    processed: Dict[str, pd.DataFrame] = {}
    for ticker, df in stock_frames.items():
        if df is not None and not df.empty:
            processed[ticker] = compute_all_indicators(df)
    return processed


def build_sector_comparison_matrix(
    processed_frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Construct a wide DataFrame of normalized Cumulative_Return_Pct across all stocks
    indexed by Date for cross-sector comparison.
    """
    series_map = {
        ticker: df["Cumulative_Return_Pct"]
        for ticker, df in processed_frames.items()
        if "Cumulative_Return_Pct" in df.columns
    }
    if not series_map:
        return pd.DataFrame()
    return pd.DataFrame(series_map).sort_index()
