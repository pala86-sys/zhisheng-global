# 智勝全球 · 雲端部署指南

本專案為 FastAPI 後端 + 靜態官網/回測前端，建議用 **Render**（免費方案可跑）或任何支援 Docker 的平台。

## 部署前準備

1. 註冊 [GitHub](https://github.com) 帳號
2. 註冊 [Render](https://render.com) 帳號（可用 GitHub 登入）
3. （建議）到 [FinMind](https://finmindtrade.com/) 申請 API Token，籌碼資料較穩定

---

## 方法一：Render（推薦）

### 1. 上傳程式碼到 GitHub

在專案資料夾開啟終端機：

```bash
git init
git add .
git commit -m "Initial deploy: 智勝全球策略回測"
git branch -M main
git remote add origin https://github.com/你的帳號/zhisheng-global.git
git push -u origin main
```

> 先在 GitHub 建立一個空的 repository（不要勾 README）。

### 2. 在 Render 建立服務

1. 登入 Render → **New** → **Web Service**
2. 連結你的 GitHub repo
3. 設定：
   - **Language**：Docker
   - **Instance Type**：Free（或 Paid 較快、較不易逾時）
   - **Health Check Path**：`/api/health`
4. **Environment Variables**（選填）：
   - `FINMIND_TOKEN` = 你的 FinMind Token
   - `SEED_ADMIN_TOKEN` = 查詢種子名單用的密鑰（自訂一串密碼）
   - `SEED_WEBHOOK_URL` = （建議）Make.com / Zapier / Discord Webhook，把報名同步出去
   - `SEED_LIST_PATH` = （建議雲端）持久化磁碟路徑，例如 `/var/data/seed_emails.json`

> **重要**：Render 免費版重新部署會清空容器內檔案。若要名單不丟，請掛 **Persistent Disk** 並設 `SEED_LIST_PATH`，或設 `SEED_WEBHOOK_URL` 同步到 Google Sheet。

5. 按 **Create Web Service**，等待建置完成

查詢名單（瀏覽器或 curl）：
`https://你的網域/api/seed-list?token=你的SEED_ADMIN_TOKEN`

### 3. 取得網址

部署成功後會得到類似：

`https://zhisheng-global.onrender.com`

- 官網首頁：`/`
- 回測工具：`/backtest`

### 4. 自訂網域（選填）

Render 後台 → 你的服務 → **Settings** → **Custom Domain**，依指示設定 DNS。

---

## 方法二：本機 Docker 測試

```bash
docker build -t zhisheng-global .
docker run -p 8765:8765 -e FINMIND_TOKEN=你的token zhisheng-global
```

瀏覽器開啟 http://127.0.0.1:8765

---

## 方法三：Railway / Fly.io

兩者都支援直接讀取 `Dockerfile`：

1. 連結 GitHub repo
2. 選 **Deploy from Dockerfile**
3. 設定環境變數 `FINMIND_TOKEN`（選填）
4. 平台會自動注入 `PORT`

---

## 注意事項

| 項目 | 說明 |
|------|------|
| 免費方案冷啟動 | Render 免費版閒置約 15 分鐘會休眠，第一次開啟需等 30～60 秒 |
| 最佳化耗時 | 「最佳化」掃描約 10～20 秒，免費方案若逾時可改選付費方案或只做單次回測 |
| 籌碼資料 | 未設定 `FINMIND_TOKEN` 時仍可用 Yahoo 股價，籌碼可能較慢或受限 |
| 資料來源 | 雲端 IP 與本機不同，FinMind 免費額度可能較快用完，建議申請 Token |

---

## 更新部署

程式改動後：

```bash
git add .
git commit -m "更新說明"
git push
```

Render 會自動重新建置（Auto-Deploy 預設開啟）。
