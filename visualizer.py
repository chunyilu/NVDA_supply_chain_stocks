"""
Interactive visualization dashboard generator (visualizer.py).

Uses Plotly (`plotly.graph_objects` and `plotly.subplots`) to construct a
multi-panel technical analysis HTML dashboard (`nvidia_tw_supply_chain.html`)
for Taiwan NVIDIA supply chain stocks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from fetcher import TARGET_STOCKS, StockInfo

logger = logging.getLogger(__name__)

# Color palette grouped by sector for clear visual distinction in Panel 1
SECTOR_COLOR_PALETTES: Dict[str, List[str]] = {
    "Foundry & Advanced Packaging": ["#00E5FF", "#00B0FF", "#40C4FF"],
    "AI Server ODMs": ["#76FF03", "#64DD17", "#B2FF59", "#00E676", "#1DE9B6"],
    "Liquid Cooling & Thermal": ["#FF9100", "#FF6D00", "#FFD740"],
    "Power & Infrastructure": ["#EA80FC", "#E040FB", "#B388FF"],
    "PCB & CCL": ["#FF5252", "#FF8A80"],
}

RANGE_SELECTOR_BUTTONS: List[Dict[str, object]] = [
    {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
    {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
    {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
    {"count": 1, "label": "YTD", "step": "year", "stepmode": "todate"},
    {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
    {"step": "all", "label": "ALL"},
]


def _get_stock_color(stock: StockInfo, sector_counters: Dict[str, int]) -> str:
    """Assign a distinct color to each stock based on its supply chain sector."""
    palette = SECTOR_COLOR_PALETTES.get(stock.sector, ["#90CAF9", "#CE93D8", "#80CBC4"])
    idx = sector_counters.get(stock.sector, 0)
    sector_counters[stock.sector] = idx + 1
    return palette[idx % len(palette)]


def build_dashboard_figure(
    processed_data: Dict[str, pd.DataFrame],
    stocks: Optional[List[StockInfo]] = None,
    default_ticker: str = "2330.TW",
) -> go.Figure:
    """
    Create the multi-panel interactive Plotly figure combining:
    - Panel 1 (Row 1): Sector Comparison — normalized cumulative % performance
      of all tracked supply chain stocks grouped by sector.
    - Panel 2 (Rows 2-5): Detailed Stock Inspection — interactive Candlestick (OHLC)
      with SMA 20 / SMA 60 overlays, color-coded Volume bars, RSI (14), and MACD (12, 26, 9).

    Args:
        processed_data: Dict mapping ticker to indicator-enriched DataFrame.
        stocks: List of StockInfo metadata objects.
        default_ticker: Ticker symbol displayed initially in Panel 2.

    Returns:
        Configured `plotly.graph_objects.Figure` instance.
    """
    stock_list = [s for s in (stocks or TARGET_STOCKS) if s.ticker in processed_data]
    if not stock_list:
        raise ValueError("No valid processed stock data available to visualize.")

    available_tickers = [s.ticker for s in stock_list]
    if default_ticker not in available_tickers:
        default_ticker = available_tickers[0]

    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.045,
        row_heights=[0.32, 0.30, 0.12, 0.13, 0.13],
        subplot_titles=(
            "Panel 1: Sector Comparison — Normalized Cumulative Return (%) Over Time",
            "Panel 2: Detailed Stock Inspection — Price (OHLC) & Moving Averages (SMA 20 / SMA 60)",
            "Trading Volume (Shares)",
            "Relative Strength Index (RSI 14)",
            "MACD (12, 26, 9)",
        ),
    )

    # -------------------------------------------------------------------------
    # PANEL 1: Normalized Sector Comparison Multi-Line Chart (Row 1)
    # -------------------------------------------------------------------------
    panel1_trace_indices: List[int] = []
    panel1_sectors: List[str] = []
    panel1_sector_shorts: List[str] = []
    sector_counters: Dict[str, int] = {}

    for stock in stock_list:
        df = processed_data[stock.ticker]
        color = _get_stock_color(stock, sector_counters)
        customdata = np.column_stack(
            [
                df["Close"].to_numpy(),
                df["Daily_Return_Pct"].to_numpy(),
            ]
        )

        trace_idx = len(fig.data)
        panel1_trace_indices.append(trace_idx)
        panel1_sectors.append(stock.sector)
        panel1_sector_shorts.append(stock.sector_short)

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Cumulative_Return_Pct"],
                mode="lines",
                name=f"{stock.ticker} ({stock.name})",
                legendgroup=stock.sector,
                legendgrouptitle_text=f"{stock.sector} ({stock.sector_short})",
                line={"color": color, "width": 2.0},
                customdata=customdata,
                hovertemplate=(
                    f"<b>{stock.ticker} - {stock.name}</b> ({stock.sector_short})<br>"
                    "Date: %{x|%Y-%m-%d}<br>"
                    "Close Price: NT$%{customdata[0]:,.2f}<br>"
                    "Daily % Change: %{customdata[1]:+.2f}%<br>"
                    "Cumulative Return: <b>%{y:+.2f}%</b>"
                    "<extra></extra>"
                ),
                visible=True,
            ),
            row=1,
            col=1,
        )

    # Add 0% baseline reference line on Panel 1
    fig.add_hline(
        y=0.0,
        line_dash="dash",
        line_color="rgba(255, 255, 255, 0.35)",
        line_width=1,
        row=1,
        col=1,
    )

    # -------------------------------------------------------------------------
    # PANEL 2: Detailed Stock Inspection (Rows 2, 3, 4, 5)
    # -------------------------------------------------------------------------
    # Each stock contributes 8 traces to Panel 2:
    # 0: Candlestick (OHLC)
    # 1: Hover Price/Change helper trace (for unified Date, Close Price, % Change tooltip)
    # 2: SMA 20
    # 3: SMA 60
    # 4: Volume bar (Red/Green)
    # 5: RSI 14
    # 6: MACD Line
    # 7: MACD Signal
    # 8: MACD Histogram
    traces_per_stock = 9
    panel2_trace_indices: List[int] = []
    stock_trace_groups: Dict[str, List[int]] = {}

    for stock in stock_list:
        df = processed_data[stock.ticker]
        is_default = stock.ticker == default_ticker
        group_indices: List[int] = []

        # Color-code volume & candlesticks: Green if Close >= Open else Red
        is_up = df["Close"] >= df["Open"]
        vol_colors = np.where(is_up, "#26a69a", "#ef5350")
        macd_colors = np.where(df["MACD_Hist"] >= 0, "#26a69a", "#ef5350")

        customdata_ohlc = np.column_stack(
            [
                df["Open"].to_numpy(),
                df["High"].to_numpy(),
                df["Low"].to_numpy(),
                df["Close"].to_numpy(),
                df["Daily_Return_Pct"].to_numpy(),
                df["Cumulative_Return_Pct"].to_numpy(),
            ]
        )

        # 1. Candlestick trace (Row 2)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name=f"{stock.ticker} OHLC",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
                showlegend=False,
                visible=is_default,
            ),
            row=2,
            col=1,
        )

        # 2. Transparent Close marker line for rich tooltip with Date, Close Price, % Change (Row 2)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name=f"{stock.ticker} Close",
                line={"color": "rgba(255,255,255,0)", "width": 0.1},
                customdata=customdata_ohlc,
                hovertemplate=(
                    f"<b>{stock.ticker} ({stock.name})</b><br>"
                    "Date: %{x|%Y-%m-%d}<br>"
                    "Close Price: <b>NT$%{customdata[3]:,.2f}</b><br>"
                    "Daily % Change: <b>%{customdata[4]:+.2f}%</b><br>"
                    "Open: NT$%{customdata[0]:,.2f} | High: NT$%{customdata[1]:,.2f} | Low: NT$%{customdata[2]:,.2f}<br>"
                    "Cumulative Return: %{customdata[5]:+.2f}%"
                    "<extra></extra>"
                ),
                showlegend=False,
                visible=is_default,
            ),
            row=2,
            col=1,
        )

        # 3. SMA 20 Overlay (Row 2)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_20"],
                mode="lines",
                name=f"{stock.ticker} SMA 20",
                line={"color": "#FFD54F", "width": 1.8},
                hovertemplate=(
                    "Date: %{x|%Y-%m-%d}<br>"
                    "SMA 20: NT$%{y:,.2f}<extra></extra>"
                ),
                showlegend=False,
                visible=is_default,
            ),
            row=2,
            col=1,
        )

        # 4. SMA 60 Overlay (Row 2)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["SMA_60"],
                mode="lines",
                name=f"{stock.ticker} SMA 60",
                line={"color": "#BA68C8", "width": 1.8},
                hovertemplate=(
                    "Date: %{x|%Y-%m-%d}<br>"
                    "SMA 60: NT$%{y:,.2f}<extra></extra>"
                ),
                showlegend=False,
                visible=is_default,
            ),
            row=2,
            col=1,
        )

        # 5. Trading Volume Bars (Row 3)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name=f"{stock.ticker} Volume",
                marker_color=vol_colors,
                customdata=customdata_ohlc,
                hovertemplate=(
                    f"<b>{stock.ticker} Volume</b><br>"
                    "Date: %{x|%Y-%m-%d}<br>"
                    "Volume: %{y:,.0f} shares<br>"
                    "Close Price: NT$%{customdata[3]:,.2f} (%{customdata[4]:+.2f}%)"
                    "<extra></extra>"
                ),
                showlegend=False,
                visible=is_default,
            ),
            row=3,
            col=1,
        )

        # 6. RSI 14 (Row 4)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["RSI_14"],
                mode="lines",
                name=f"{stock.ticker} RSI 14",
                line={"color": "#4FC3F7", "width": 1.8},
                customdata=customdata_ohlc,
                hovertemplate=(
                    "Date: %{x|%Y-%m-%d}<br>"
                    "RSI (14): <b>%{y:.2f}</b><br>"
                    "Close Price: NT$%{customdata[3]:,.2f} (%{customdata[4]:+.2f}%)"
                    "<extra></extra>"
                ),
                showlegend=False,
                visible=is_default,
            ),
            row=4,
            col=1,
        )

        # 7. MACD Line (Row 5)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MACD"],
                mode="lines",
                name=f"{stock.ticker} MACD",
                line={"color": "#29B6F6", "width": 1.6},
                hovertemplate="Date: %{x|%Y-%m-%d}<br>MACD: %{y:.2f}<extra></extra>",
                showlegend=False,
                visible=is_default,
            ),
            row=5,
            col=1,
        )

        # 8. MACD Signal Line (Row 5)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MACD_Signal"],
                mode="lines",
                name=f"{stock.ticker} Signal",
                line={"color": "#FFA726", "width": 1.6},
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Signal: %{y:.2f}<extra></extra>",
                showlegend=False,
                visible=is_default,
            ),
            row=5,
            col=1,
        )

        # 9. MACD Histogram (Row 5)
        group_indices.append(len(fig.data))
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["MACD_Hist"],
                name=f"{stock.ticker} MACD Hist",
                marker_color=macd_colors,
                hovertemplate="Date: %{x|%Y-%m-%d}<br>MACD Hist: %{y:.2f}<extra></extra>",
                showlegend=False,
                visible=is_default,
            ),
            row=5,
            col=1,
        )

        assert len(group_indices) == traces_per_stock
        stock_trace_groups[stock.ticker] = group_indices
        panel2_trace_indices.extend(group_indices)

    # RSI Overbought (70) & Oversold (30) threshold lines on Row 4
    fig.add_hline(
        y=70.0,
        line_dash="dot",
        line_color="rgba(239, 83, 80, 0.6)",
        line_width=1,
        row=4,
        col=1,
    )
    fig.add_hline(
        y=30.0,
        line_dash="dot",
        line_color="rgba(38, 166, 154, 0.6)",
        line_width=1,
        row=4,
        col=1,
    )

    # -------------------------------------------------------------------------
    # INTERACTIVE CONTROLS: Sector Filter (Panel 1) & Stock Selector (Panel 2)
    # -------------------------------------------------------------------------
    sector_filter_buttons: List[Dict[str, object]] = [
        {
            "label": "All Sectors",
            "method": "restyle",
            "args": [{"visible": [True] * len(panel1_trace_indices)}, panel1_trace_indices],
        }
    ]

    unique_sectors: List[str] = []
    for s in stock_list:
        if s.sector not in unique_sectors:
            unique_sectors.append(s.sector)

    for sec in unique_sectors:
        vis_mask = [s == sec for s in panel1_sectors]
        sector_filter_buttons.append(
            {
                "label": sec,
                "method": "restyle",
                "args": [{"visible": vis_mask}, panel1_trace_indices],
            }
        )

    stock_selector_buttons: List[Dict[str, object]] = []
    for stock in stock_list:
        vis_panel2: List[bool] = []
        for candidate in stock_list:
            vis_panel2.extend([candidate.ticker == stock.ticker] * traces_per_stock)

        stock_selector_buttons.append(
            {
                "label": f"{stock.ticker} - {stock.name} ({stock.sector_short})",
                "method": "restyle",
                "args": [{"visible": vis_panel2}, panel2_trace_indices],
            }
        )

    # -------------------------------------------------------------------------
    # AXES, RANGE SELECTORS, RANGE SLIDERS & THEME CONFIGURATION
    # -------------------------------------------------------------------------
    # Panel 1 X-Axis: Date Range Selector Buttons + Range Slider
    fig.update_xaxes(
        rangeselector={
            "buttons": RANGE_SELECTOR_BUTTONS,
            "bgcolor": "#1E293B",
            "activecolor": "#38BDF8",
            "font": {"color": "#F8FAFC", "size": 11},
            "x": 0.0,
            "y": 1.12,
        },
        rangeslider={"visible": True, "thickness": 0.025, "bgcolor": "#0F172A"},
        type="date",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text="Cumulative Return (%)",
        ticksuffix="%",
        gridcolor="rgba(148, 163, 184, 0.15)",
        zeroline=True,
        zerolinecolor="rgba(255, 255, 255, 0.3)",
        row=1,
        col=1,
    )

    # Link Panel 2 X-Axes (Rows 2, 3, 4, 5) so zooming/sliding syncs all Panel 2 subplots
    fig.update_xaxes(
        rangeselector={
            "buttons": RANGE_SELECTOR_BUTTONS,
            "bgcolor": "#1E293B",
            "activecolor": "#38BDF8",
            "font": {"color": "#F8FAFC", "size": 11},
            "x": 0.0,
            "y": 1.12,
        },
        rangeslider={"visible": False},
        type="date",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=2,
        col=1,
    )
    for r in (3, 4):
        fig.update_xaxes(
            matches="x2",
            type="date",
            gridcolor="rgba(148, 163, 184, 0.15)",
            row=r,
            col=1,
        )

    # Bottom axis of Panel 2 (Row 5) carries the interactive Range Slider for Panel 2
    fig.update_xaxes(
        matches="x2",
        rangeslider={"visible": True, "thickness": 0.025, "bgcolor": "#0F172A"},
        type="date",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=5,
        col=1,
    )

    fig.update_yaxes(
        title_text="Price (NT$)",
        tickprefix="NT$",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=2,
        col=1,
    )
    fig.update_yaxes(
        title_text="Volume",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=3,
        col=1,
    )
    fig.update_yaxes(
        title_text="RSI (14)",
        range=[0, 100],
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=4,
        col=1,
    )
    fig.update_yaxes(
        title_text="MACD",
        gridcolor="rgba(148, 163, 184, 0.15)",
        row=5,
        col=1,
    )

    fig.update_layout(
        title={
            "text": (
                "<b>Taiwan NVIDIA Supply Chain — Technical & Sector Performance Dashboard</b><br>"
                "<span style='font-size:13px;color:#94A3B8;'>"
                "Panel 1: Normalized Sector Comparison (%) | "
                "Panel 2: Interactive Candlestick (OHLC), SMA 20/60, Volume, RSI 14 & MACD (12, 26, 9)"
                "</span>"
            ),
            "x": 0.01,
            "xanchor": "left",
            "font": {"size": 20, "color": "#F8FAFC"},
        },
        template="plotly_dark",
        paper_bgcolor="#0B1120",
        plot_bgcolor="#111827",
        font={"family": "Inter, system-ui, -apple-system, sans-serif", "color": "#E2E8F0"},
        height=1650,
        margin={"t": 130, "b": 60, "l": 75, "r": 260},
        hovermode="x unified",
        legend={
            "title": {"text": "<b>Supply Chain Sectors</b>"},
            "orientation": "v",
            "x": 1.01,
            "y": 1.0,
            "xanchor": "left",
            "bgcolor": "rgba(17, 24, 39, 0.85)",
            "bordercolor": "rgba(148, 163, 184, 0.25)",
            "borderwidth": 1,
            "groupclick": "togglegroup",
        },
        updatemenus=[
            {
                "buttons": sector_filter_buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.42,
                "xanchor": "left",
                "y": 1.045,
                "yanchor": "top",
                "bgcolor": "#1E293B",
                "bordercolor": "#38BDF8",
                "font": {"color": "#F8FAFC", "size": 12},
            },
            {
                "buttons": stock_selector_buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.68,
                "xanchor": "left",
                "y": 1.045,
                "yanchor": "top",
                "bgcolor": "#1E293B",
                "bordercolor": "#A855F7",
                "font": {"color": "#F8FAFC", "size": 12},
            },
        ],
    )

    # Add labels next to the dropdown menus
    fig.add_annotation(
        text="<b>Panel 1 Sector Filter:</b>",
        x=0.415,
        y=1.04,
        xref="paper",
        yref="paper",
        xanchor="right",
        showarrow=False,
        font={"size": 12, "color": "#38BDF8"},
    )
    fig.add_annotation(
        text="<b>Panel 2 Inspect Stock:</b>",
        x=0.675,
        y=1.04,
        xref="paper",
        yref="paper",
        xanchor="right",
        showarrow=False,
        font={"size": 12, "color": "#C084FC"},
    )

    return fig


def export_dashboard_html(
    processed_data: Dict[str, pd.DataFrame],
    output_path: str | Path = "nvidia_tw_supply_chain.html",
    stocks: Optional[List[StockInfo]] = None,
    default_ticker: str = "2330.TW",
) -> Path:
    """
    Build the interactive Plotly dashboard and save it as a standalone HTML file.

    Args:
        processed_data: Dict mapping ticker to indicator-enriched DataFrame.
        output_path: Destination HTML file path (default: 'nvidia_tw_supply_chain.html').
        stocks: Optional list of StockInfo objects.
        default_ticker: Default stock symbol inspected in Panel 2.

    Returns:
        Resolved Path to the generated HTML dashboard.
    """
    fig = build_dashboard_figure(
        processed_data=processed_data,
        stocks=stocks,
        default_ticker=default_ticker,
    )
    resolved_path = Path(output_path).resolve()
    fig.write_html(
        str(resolved_path),
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": True,
        },
    )
    logger.info("Interactive dashboard exported to %s", resolved_path)
    return resolved_path
