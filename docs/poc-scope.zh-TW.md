# POC 範圍

## 這一版要驗證什麼

這個 POC 只回答一個問題：

> 使用者是否能透過熟悉的 LINE 或 WhatsApp 介面，有效查到已核准文件中的既有知識？

成功條件：

1. 指定測試者能從 LINE 或 WhatsApp 提問。
2. Bot 只根據指定的私有 Cloud Storage 測試資料回答。
3. 回答會附上可追溯的來源文件。
4. 找不到足夠資料時不勉強作答。
5. GitHub 公開版本不包含任何真實公司內容或識別資訊。

## 這一版不做

- 從 LINE 或 WhatsApp 上傳文件與自動更新索引
- Solution Library
- 定期整理與主題歸納
- 錄音或影片轉錄
- Pinecone、Qdrant、pgvector
- 自訂 embeddings、chunking、reranking
- 多部門細緻權限
- Google Workspace Drive connector 的正式 tenant 驗證
- 管理後台、報表與長期對話記憶

## 建議測試資料

先選 20～50 份品質較好的文件，涵蓋三種問題：

- 明確事實：流程、日期、負責人、決策。
- 跨文件整理：過去針對某情境討論過哪些方案。
- 應該拒答：資料中不存在或使用者無權查看的問題。

每個問題記錄：預期答案、應引用文件、實際答案、是否可接受。

## POC 通過後才重新評估

- 使用人數與部門範圍
- LINE 與 Workspace 帳號綁定
- WhatsApp Business 正式帳號、電話號碼與 Meta App 審核
- Cloud Storage 文件更新要採手動、定時或事件驅動同步
- 非同步工作佇列及重試
- 錄音轉錄
- Solution Library
- 是否真的需要自建向量資料庫

## 已確認的客戶 Phase 1 延伸方向

POC 通過後，客戶 Phase 1 必須加入「授權使用者從 LINE 上傳文件」：

1. LINE webhook 先驗證簽章、上傳 allowlist 與事件是否重複。
2. 背景工作下載檔案並保存至客戶控制的私有 Cloud Storage。
3. 檢查支援格式、容量與處理狀態後更新 Agent Search 索引。
4. 完成或失敗時由 LINE 通知上傳者。

Phase 1 同時採用「核准 Drive 資料夾背景同步」：客戶在建置時一次將
指定 Shared Drive／資料夾以 Viewer 權限分享給同步身分，Cloud Run Job
定時把文件下載或匯出至私有 Cloud Storage，再匯入既有 Agent Search
data store。LINE 查詢沿用目前已驗證的 service account，不使用 Agent
Search Google Drive Connector，也不要求使用者每次查詢重新授權 Google。

Drive 是正式文件管理位置。LINE 新檔先進 GCS quarantine 做格式與內容
去重，通過後發布至 Drive `00-LINE-Inbox`，再由上述統一同步流程索引；
不直接從 LINE raw object 建立第二份搜尋文件。同名異內容或疑似重複的
檔案進 `01-Needs-Review`，確認前不納入搜尋。

LINE 與 WhatsApp 查詢各自使用獨立 allowlist，並共用同一個 Agent Search
查詢服務；目前 WhatsApp 只支援文字問答。查詢 allowlist 與上傳 allowlist
仍分開管理。錄音／影片轉錄仍屬下一階段，不納入 Phase 1。這一節是後續
範圍說明，不代表目前 POC 已完成文件上傳能力。
