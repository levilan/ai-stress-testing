# 🚀 API 雲端分散式壓測工具 (Cloud API Stress Testing)

這是一個專為大語言模型 (LLM) API 設計的高併發、分散式壓力測試工具。支援透過自動化腳本在 AWS EC2 上快速建立分散式叢集進行大規模壓測，也支援在本地端透過 Web UI 或 CLI 單機運行。

## ✨ 核心特色

- **☁️ AWS 一鍵部署與銷毀**：自動建立 EC2 實例（預設 3 台 t3.medium）、設定 Security Group、自動傳輸腳本，壓測完畢後一鍵回收資源，避免產生額外費用。
- **🌊 混合模式壓測**：支援流式 (SSE, Stream) 與非流式 (Non-stream) 混合請求，並可自訂兩者的比例。
- **📊 視覺化報告**：壓測結束後自動收集各節點數據，並生成基於 Tailwind CSS 的精美 HTML 報表 (`merged_report.html`)。
- **🌐 Web UI 介面**：提供單機版的 Web 圖形化介面，方便快速配置參數並啟動測試。
- **⚡ 高效能非同步**：基於 Python `asyncio` 和 `aiohttp` 實作，單機即可產生極高併發。

## 📁 專案結構

- `aws_deploy.sh`: 自動在 AWS 上開機並部署環境。
- `aws_run_test.sh`: 觸發所有 EC2 節點同時進行壓測，並於結束後下載數據、合併 HTML 報告。
- `aws_destroy.sh`: 一鍵銷毀所有 EC2 資源與安全組。
- `load_test.py`: 核心壓測邏輯，基於 `asyncio` 的高效能發包腳本。
- `server.py`: 提供 Web 視覺化操作介面的後端伺服器 (Port 8080)。
- `generate_report.py`: 彙總各節點 JSON 數據並生成視覺化 HTML 報告的工具。

## 🛠️ 環境與前置作業

1. **Python 環境**: Python 3.8+，並安裝依賴套件。
   ```bash
   pip install aiohttp
   ```
2. **AWS CLI (針對分散式壓測)**: 需安裝 AWS CLI 並配置好權限。
   ```bash
   aws configure
   ```

---

## 🚀 使用方式

### 方案 A：AWS 分散式壓測 (推薦用於大規模測試)

利用 3 台獨立的 EC2 進行分散式打流，以繞過單機頻寬與連線數限制。

1. **部署環境 (開機)**
   ```bash
   ./aws_deploy.sh
   ```
   *等待腳本自動建立金鑰、Security Group 及 3 台 EC2 實例。*

2. **執行壓測**
   ```bash
   ./aws_run_test.sh <API_URL> <API_KEY>
   ```
   *腳本會自動讓三台機器同時啟動測試，測試完成後會將結果下載回本地，並生成 `merged_report.html`。你可以直接在瀏覽器中打開此 HTML 查看結果。*

3. **清理資源 (⚠️ 極度重要)**
   ```bash
   ./aws_destroy.sh
   ```
   *測試完畢後，請務必執行此腳本來終止 EC2 實例，避免持續計費！*

### 方案 B：本地端 Web UI 測試

如果您只需要做簡單的測試，可以啟動本地的圖形化介面：

1. 啟動伺服器：
   ```bash
   python server.py
   ```
2. 打開瀏覽器訪問 `http://localhost:8080`。
3. 在網頁中填入 API URL、API Key、請求速率 (RPM) 與持續時間等參數，點擊「開始壓測」。

### 方案 C：本地端 CLI 測試

也可以直接使用終端機指令在本地執行壓測腳本：

```bash
python load_test.py \
  --url "https://your-api-endpoint.com" \
  --key "sk-xxxxxx" \
  --rpm 100 \
  --duration 60 \
  --mode mixed \
  --stream-ratio 0.5 \
  --output-json result.json
```

**參數說明:**
- `--url`: API 基礎路徑
- `--key`: 認證用的 API Key
- `--model`: 模型名稱 (預設: gemini-3.1-pro-preview)
- `--rpm`: 每分鐘請求數
- `--duration`: 測試總時長 (秒)
- `--mode`: `stream`, `non-stream`, 或 `mixed` (混合模式)
- `--stream-ratio`: 當選擇 mixed 時，流式請求所佔的比例 (0.0 ~ 1.0)
- `--workers`: 協程併發數量 (預設: 50)

## ⚠️ 注意事項

1. **AWS 費用**：部署腳本預設開啟 3 台 `t3.medium` 實例，若忘記銷毀會產生持續的 AWS 帳單。請務必在測試後執行 `./aws_destroy.sh`。
2. **安全防護**：本專案的 `.gitignore` 已設定攔截 `*.pem`, `*.env` 等敏感檔案。請勿手動將 AWS 私鑰或 API Key 加入 Git 追蹤。
3. **API 額度**：高併發測試會在短時間內消耗大量的 API 額度 (Tokens)，請確保您的帳戶有足夠的餘額與 Rate Limit 權限。
