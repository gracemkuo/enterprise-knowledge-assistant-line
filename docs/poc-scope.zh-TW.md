# POC 範圍

## 這一版要驗證什麼

這個 POC 只回答一個問題：

> 使用者是否能透過熟悉的 LINE 介面，有效查到已核准文件中的既有知識？

成功條件：

1. 指定測試者能從 LINE 提問。
2. Bot 只根據指定的私有 Cloud Storage 測試資料回答。
3. 回答會附上可追溯的來源文件。
4. 找不到足夠資料時不勉強作答。
5. GitHub 公開版本不包含任何真實公司內容或識別資訊。

## 這一版不做

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
- Cloud Storage 文件更新要採手動、定時或事件驅動同步
- 非同步工作佇列及重試
- 錄音轉錄
- Solution Library
- 是否真的需要自建向量資料庫
