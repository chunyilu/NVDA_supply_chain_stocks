# 台灣 NVIDIA 供應鏈股票追蹤與技術分析儀表板 (Taiwan NVIDIA Supply Chain Stock Tracker & Technical Dashboard)

這是一個模組化的 Python 資料工程與視覺化應用程式，用於擷取 16 檔關鍵**台灣 NVIDIA（輝達）供應鏈概念股**（上市 TWSE / 上櫃 TPEx）的歷史日線行情資料（OHLCV），計算多項技術指標，並生成互動式的多面板 **Plotly HTML 技術分析儀表板**（`nvidia_tw_supply_chain.html`）。

---

## 追蹤股票清單 (Tracked Stock Universe)

| 產業別 (Sector) | 股票代號 (Ticker) | 公司名稱 (Company) | 交易所 (Exchange) |
| :--- | :--- | :--- | :--- |
| **晶圓代工與先進封裝 (Foundry & Advanced Packaging)** | `2330.TW` | 台積電 (TSMC) | TWSE (上市) |
| **晶圓代工與先進封裝 (Foundry & Advanced Packaging)** | `3711.TW` | 日月光投控 (ASE Technology) | TWSE (上市) |
| **晶圓代工與先進封裝 (Foundry & Advanced Packaging)** | `2449.TW` | 京元電子 (KYEC) | TWSE (上市) |
| **AI 伺服器代工 (AI Server ODMs)** | `2317.TW` | 鴻海 (Hon Hai / Foxconn) | TWSE (上市) |
| **AI 伺服器代工 (AI Server ODMs)** | `2382.TW` | 廣達 (Quanta Computer) | TWSE (上市) |
| **AI 伺服器代工 (AI Server ODMs)** | `6669.TW` | 緯穎 (Wiwynn) | TWSE (上市) |
| **AI 伺服器代工 (AI Server ODMs)** | `3231.TW` | 緯創 (Wistron) | TWSE (上市) |
| **AI 伺服器代工 (AI Server ODMs)** | `2376.TW` | 技嘉 (Gigabyte) | TWSE (上市) |
| **液冷與散熱模組 (Liquid Cooling & Thermal)** | `3017.TW` | 奇鋐 (Asia Vital Components / CCI) | TWSE (上市) |
| **液冷與散熱模組 (Liquid Cooling & Thermal)** | `3324.TW` / `3324.TWO` | 雙鴻 (Auras Technology) | TPEx (上櫃) / TWSE |
| **液冷與散熱模組 (Liquid Cooling & Thermal)** | `3653.TW` | 健策 (Jentech Precision) | TWSE (上市) |
| **電源與基礎設施 (Power & Infrastructure)** | `2308.TW` | 台達電 (Delta Electronics) | TWSE (上市) |
| **電源與基礎設施 (Power & Infrastructure)** | `2059.TW` | 川湖 (King Slide Works) | TWSE (上市) |
| **電源與基礎設施 (Power & Infrastructure)** | `3665.TW` | 貿聯-KY (BizLink-KY) | TWSE (上市) |
| **印刷電路板與銅箔基板 (PCB & CCL)** | `2383.TW` | 台光電 (Elite Material / EMC) | TWSE (上市) |
| **印刷電路板與銅箔基板 (PCB & CCL)** | `3037.TW` | 欣興 (Unimicron Technology) | TWSE (上市) |

---

## 專案架構 (Project Architecture)

```text
NVDA_supply_chain_stocks/
├── main.py                      # 資料管線 CLI 主程式入口
├── fetcher.py                   # 主要資料擷取模組（yfinance、資料清理與交易日對齊）
├── scraper.py                   # 備援 TWSE/TPEx 網頁爬蟲（requests + BeautifulSoup）
├── indicators.py                # 技術指標計算（SMA 20/60、RSI 14、MACD、報酬率）
├── visualizer.py                # 互動式多面板 Plotly HTML 儀表板建構器
├── requirements.txt             # Python 套件相依清單
├── follow_stock_prompt.md       # 專案規格提示詞文件
└── nvidia_tw_supply_chain.html  # 生成的互動式視覺化儀表板輸出檔
```

### 模組說明 (Module Breakdown)

1. **資料擷取 (`fetcher.py` & `scraper.py`)**
   - **主要方式 (`fetcher.py`)：** 使用 `yfinance` 擷取每日 OHLCV（開盤價 `Open`、最高價 `High`、最低價 `Low`、收盤價 `Close`、成交量 `Volume`）資料，並自動判斷與解析上櫃（TPEx）股票的 `.TW` 與 `.TWO` 後綴。
   - **備援爬蟲 (`scraper.py`)：** 使用 `requests` + `BeautifulSoup` 直接從台灣證券交易所 TWSE（`STOCK_DAY`）與櫃買中心 TPEx（`st43_print.php`）解析各月歷史交易表格，並附帶瀏覽器 `User-Agent` 標頭與速率限制（`time.sleep`）以防止 IP 遭封鎖。
   - **資料清理與對齊：** 自動剔除週末與無交易之國定假日、處理缺漏或為零的成交量，並將所有股票對齊至統一的交易日曆。

2. **技術指標計算 (`indicators.py`)**
   - **簡單移動平均線 (SMA)：** `SMA_20`（20 日均線）與 `SMA_60`（60 日均線）
   - **相對強弱指標 (RSI)：** `RSI_14`（14 日威爾德平滑法 Wilder's smoothing）
   - **MACD (12, 26, 9)：** `MACD` 快線、`MACD_Signal` 訊號線與 `MACD_Hist` 柱狀圖
   - **績效指標：** 單日漲跌幅百分比（`Daily_Return_Pct`）與自起始日基準化之累積報酬率百分比（`Cumulative_Return_Pct`）

3. **互動式視覺化 (`visualizer.py`)**
   - **面板 1 — 產業類股累積報酬比較 (Sector Comparison)：** 標準化多線圖，比較全部 16 檔供應鏈股票隨時間變化的累積報酬率（%），依供應鏈產業分類，並提供互動式**產業篩選器（Sector Filter）**下拉選單。
   - **面板 2 — 個股技術分析詳情 (Detailed Stock Inspection)：** 由互動式**股票選擇器（Stock Selector）**下拉選單控制的同步 4 列技術分析視圖：
     - **K 線圖 (Candlestick OHLC)** 疊加 **SMA 20** 與 **SMA 60** 均線
     - **成交量柱狀圖 (Trading Volume)**，依漲跌紅綠著色（`Close >= Open` vs `Close < Open`）
     - **RSI (14)** 震盪指標，含 30/70 超賣/超買參考線
     - **MACD (12, 26, 9)** 快慢線與紅綠柱狀圖
   - **互動式體驗 (Interactive UX)：** 包含快速時間區間按鈕（`1M`、`3M`、`6M`、`YTD`、`1Y`、`ALL`）、底部時間軸縮放滑桿（Range Slider）、圖例群組點擊切換，以及統一的懸停提示框（顯示**日期**、**收盤價**、**單日漲跌幅 %** 與 **累積報酬率 %**）。

---

## 安裝方式 (Installation)

### 方式 1：使用 `uv`（推薦）

```bash
uv venv .venv
uv pip install -r requirements.txt
```

### 方式 2：使用標準 `venv` + `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 使用方式 (Usage)

執行預設資料管線（擷取過去 1 年的日線資料、在終端機印出彙整統計表，並輸出 `nvidia_tw_supply_chain.html`）：

```bash
.venv/bin/python main.py
```

### 命令列參數 (Command-Line Options)

```bash
.venv/bin/python main.py --help
```

| 參數 (Flag) | 預設值 (Default) | 說明 (Description) |
| :--- | :--- | :--- |
| `--period {6mo,1y,2y,ytd}` | `1y` | 歷史市場資料的回溯期間 |
| `--default-stock TICKER` | `2330.TW` | 面板 2 個股詳情視圖預設顯示的股票代號 |
| `--output PATH` | `nvidia_tw_supply_chain.html` | 生成之 HTML 儀表板的輸出檔案路徑 |
| `--fallback` | `False` | 強制使用 `requests` + `BeautifulSoup` 直接從 TWSE/TPEx 爬取資料 |
| `--open-browser` | `False` | 自動在系統預設瀏覽器中開啟生成的 HTML 檔案 |

### 執行範例 (Examples)

```bash
# 擷取 6 個月資料，將廣達 (2382.TW) 設為面板 2 預設顯示個股，並自動於瀏覽器開啟
.venv/bin/python main.py --period 6mo --default-stock 2382.TW --open-browser

# 使用備援 BeautifulSoup 爬蟲執行
.venv/bin/python main.py --fallback
```
