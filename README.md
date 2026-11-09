# Taiwan NVIDIA Supply Chain Stock Tracker & Technical Dashboard

A modular Python data engineering and visualization application that retrieves historical OHLCV market data for 16 key **Taiwan NVIDIA supply chain stocks** (TWSE / TPEx), calculates technical indicators, and generates an interactive multi-panel **Plotly HTML dashboard** (`nvidia_tw_supply_chain.html`).

---

## Tracked Stock Universe

| Sector | Ticker | Company | Exchange |
| :--- | :--- | :--- | :--- |
| **Foundry & Advanced Packaging** | `2330.TW` | TSMC | TWSE |
| **Foundry & Advanced Packaging** | `3711.TW` | ASE Technology | TWSE |
| **Foundry & Advanced Packaging** | `2449.TW` | KYEC | TWSE |
| **AI Server ODMs** | `2317.TW` | Hon Hai (Foxconn) | TWSE |
| **AI Server ODMs** | `2382.TW` | Quanta Computer | TWSE |
| **AI Server ODMs** | `6669.TW` | Wiwynn | TWSE |
| **AI Server ODMs** | `3231.TW` | Wistron | TWSE |
| **AI Server ODMs** | `2376.TW` | Gigabyte | TWSE |
| **Liquid Cooling & Thermal** | `3017.TW` | Asia Vital Components (CCI) | TWSE |
| **Liquid Cooling & Thermal** | `3324.TW` / `3324.TWO` | Auras Technology | TPEx / TWSE |
| **Liquid Cooling & Thermal** | `3653.TW` | Jentech Precision | TWSE |
| **Power & Infrastructure** | `2308.TW` | Delta Electronics | TWSE |
| **Power & Infrastructure** | `2059.TW` | King Slide Works | TWSE |
| **Power & Infrastructure** | `3665.TW` | BizLink-KY | TWSE |
| **PCB & CCL** | `2383.TW` | Elite Material (EMC) | TWSE |
| **PCB & CCL** | `3037.TW` | Unimicron Technology | TWSE |

---

## Project Architecture

```text
NVDA_supply_chain_stocks/
├── main.py                      # Pipeline CLI entry point
├── fetcher.py                   # Primary yfinance data retrieval, cleaning & date alignment
├── scraper.py                   # Fallback TWSE/TPEx HTML scraper (requests + BeautifulSoup)
├── indicators.py                # Technical indicators (SMA 20/60, RSI 14, MACD, returns)
├── visualizer.py                # Interactive multi-panel Plotly HTML dashboard builder
├── requirements.txt             # Python package dependencies
├── follow_stock_prompt.md       # Project specification prompt
└── nvidia_tw_supply_chain.html  # Generated interactive dashboard output
```

### Module Breakdown

1. **Data Retrieval (`fetcher.py` & `scraper.py`)**
   - **Primary Method (`fetcher.py`):** Uses `yfinance` to fetch daily OHLCV (`Open`, `High`, `Low`, `Close`, `Volume`) data and automatically resolves `.TW` vs `.TWO` suffixes for TPEx-listed stocks.
   - **Fallback Scraper (`scraper.py`):** Uses `requests` + `BeautifulSoup` to parse monthly historical trading tables directly from TWSE (`STOCK_DAY`) and TPEx (`st43_print.php`) with browser `User-Agent` headers and rate-limiting (`time.sleep`) to prevent IP blocks.
   - **Data Hygiene:** Strips weekends and phantom holidays, sanitizes missing/zero volumes, and aligns all stocks onto a unified trading calendar.

2. **Technical Indicators (`indicators.py`)**
   - **Simple Moving Averages:** `SMA_20` (20-day) and `SMA_60` (60-day)
   - **Relative Strength Index:** `RSI_14` (14-day Wilder's smoothing)
   - **MACD (12, 26, 9):** `MACD` line, `MACD_Signal` line, and `MACD_Hist` histogram
   - **Performance Metrics:** Daily percentage change (`Daily_Return_Pct`) and start-date normalized cumulative return (`Cumulative_Return_Pct`)

3. **Interactive Visualization (`visualizer.py`)**
   - **Panel 1 — Sector Comparison:** Normalized multi-line chart comparing the cumulative percentage performance of all 16 stocks over time, grouped by supply chain sector with an interactive **Sector Filter** dropdown.
   - **Panel 2 — Detailed Stock Inspection:** Synchronized 4-row technical view controlled by an interactive **Stock Selector** dropdown:
     - **Candlestick (OHLC)** chart overlaid with **SMA 20** and **SMA 60**
     - **Trading Volume** bar chart color-coded green/red (`Close >= Open` vs `Close < Open`)
     - **RSI (14)** oscillator with 30/70 oversold/overbought guide lines
     - **MACD (12, 26, 9)** line, signal line, and color-coded histogram
   - **Interactive UX:** Includes quick date range buttons (`1M`, `3M`, `6M`, `YTD`, `1Y`, `ALL`), bottom range sliders, legend group toggling, and unified hover tooltips displaying **Date**, **Close Price**, **Daily % Change**, and **Cumulative % Return**.

---

## Installation

### Option 1: Using `uv` (Recommended)

```bash
uv venv .venv
uv pip install -r requirements.txt
```

### Option 2: Using standard `venv` + `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

Run the default pipeline (fetches 1 year of daily data, prints a terminal summary table, and writes `nvidia_tw_supply_chain.html`):

```bash
.venv/bin/python main.py
```

### Command-Line Options

```bash
.venv/bin/python main.py --help
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--period {6mo,1y,2y,ytd}` | `1y` | Lookback period for historical market data |
| `--default-stock TICKER` | `2330.TW` | Initial stock displayed in Panel 2 detailed view |
| `--output PATH` | `nvidia_tw_supply_chain.html` | Output file path for the generated HTML dashboard |
| `--fallback` | `False` | Force direct TWSE/TPEx scraping via `requests` + `BeautifulSoup` |
| `--open-browser` | `False` | Automatically open the generated HTML file in the default browser |

### Examples

```bash
# Fetch 6 months of data, set Quanta (2382.TW) as default in Panel 2, and open in browser
.venv/bin/python main.py --period 6mo --default-stock 2382.TW --open-browser

# Run using the fallback BeautifulSoup scraper
.venv/bin/python main.py --fallback
```
