### Role & Goal
You are an expert Python data engineer and visualization specialist. Build a modular Python application that retrieves market data for key Taiwan NVIDIA supply chain stocks and generates an interactive, multi-panel technical visualization dashboard.

---

### Target Stock List (TWSE / TPEx)
Follow these representative stocks (append `.TW` for TWSE or `.TWO` for TPEx when using Yahoo Finance):
- **Foundry & Advanced Packaging:** 2330.TW (TSMC), 3711.TW (ASE Technology), 2449.TW (KYEC)
- **AI Server ODMs:** 2317.TW (Hon Hai), 2382.TW (Quanta), 6669.TW (Wiwynn), 3231.TW (Wistron), 2376.TW (Gigabyte)
- **Liquid Cooling & Thermal:** 3017.TW (CCI), 3324.TW (Auras), 3653.TW (Jentech)
- **Power & Infrastructure:** 2308.TW (Delta Electronics), 2059.TW (King Slide), 3665.TW (BizLink-KY)
- **PCB & CCL:** 2383.TW (Elite Material), 3037.TW (Unimicron)

---

### Technical Requirements

#### 1. Data Retrieval (`scraper.py` / `fetcher.py`)
- Primary Method: Use `yfinance` to fetch daily OHLCV (Open, High, Low, Close, Volume) data for the past 6 to 12 months.
- Fallback/Direct Scraping: Provide an alternate function using `requests` + `BeautifulSoup` (or TWSE open API endpoints) with proper headers (`User-Agent`) and rate limiting (`time.sleep`) to prevent IP bans.
- Handle edge cases: non-trading days, missing volume, and date alignment.

#### 2. Data Processing & Indicators (`indicators.py`)
Calculate standard metrics for each stock using `pandas`:
- Moving Averages: SMA 20, SMA 60
- Relative Strength Index (RSI 14)
- MACD (12, 26, 9)
- Cumulative performance (% return baseline normalized from start date) to compare all stocks in the sector against each other.

#### 3. Visualization Dashboard (`visualizer.py`)
Use **Plotly** (`plotly.graph_objects` / `plotly.subplots`) to output an interactive HTML dashboard (`nvidia_tw_supply_chain.html`):
- **Panel 1 (Sector Comparison):** A normalized multi-line chart comparing the percentage performance of all tracked supply chain stocks over time, grouped by sector (Foundry, ODM, Cooling, Power/Components).
- **Panel 2 (Detailed Stock Inspection):** Interactive candlestick chart (OHLC) with 20/60 SMA overlays and a lower subplot showing Trading Volume bars (color-coded red/green).
- **UI & UX:** Include range sliders, date range selectors (1M, 3M, 6M, 1Y, YTD), and tooltips showing Date, Close Price, and % Change.

#### 4. Architecture & Deliverables
- `requirements.txt` (e.g., `yfinance`, `pandas`, `plotly`, `requests`, `beautifulsoup4`)
- Clean, PEP 8 compliant, modular code with comments and type annotations.
- `main.py` entry point that runs the pipeline and automatically opens or saves the visual dashboard.
