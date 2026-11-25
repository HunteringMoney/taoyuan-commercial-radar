# 桃園商業區土地獵人

手機網頁：[docs/index.html](docs/index.html)

## 目前狀態

- ✅ 手機版靜態介面、個人勘查筆記與 Google Maps 定位
- ✅ 僅顯示 `district=桃園區`、`zone=商業區` 且 `official_zoning_verified=true` 的正式候選資料
- ⏳ 官方商業區資料來源尚未串接並驗證，因此 `docs/targets.json` 目前是空名單
- ⏳ 須在 GitHub 儲存庫 Settings → Pages 設定 `Deploy from a branch`、`main`、`/docs`，才能公開手機網址
- ⏳ 每日自動掃描須先確認官方資料授權、可用性及分區判定準確率

**注意：** 此版本不是已完成的 AI 自動找地系統。個人筆記僅存於目前裝置的瀏覽器，不會跨裝置同步，建議使用匯出備份。請勿輸入地主個資。

[桃園市都市計畫地理資訊服務網](https://urplanning.tycg.gov.tw/gisMap/)

## 每日新目標通知（2026-11-25 新增）

工作流程：[`.github/workflows/notify-verified-targets.yml`](.github/workflows/notify-verified-targets.yml)，每天 **08:17 台灣時間**檢查一次（GitHub 排程可能延遲），也支援 Actions 頁面的 `Run workflow` 手動執行。

通知方式：有首次出現、且完成資料核對及人工審核的目標，才建立一個 GitHub Issue。同一目標 ID 不會重複建立通知。沒有合格目標，不建立 Issue。

**目前官方圖資仍未接通**，`docs/targets.json` 狀態為 `official_zoning_data_not_connected`，因此排程只會安全跳過通知，不會製造假的目標。正式輸入須經由官方 GIS 核對桃園區商業區，再填入 `verification_status: official_zoning_verified` 及目標的來源與審核欄位；單靠網站地址文字、OpenStreetMap 商業標籤或自行設定欄位，不等於核對完成。

要收到通知：於 GitHub 儲存庫右上角 **Watch → Custom → Issues**，並在 GitHub 帳號 Notifications 設定啟用 Web / Email 通知。GitHub 手機 App 可顯示支援的推播通知。

目前沒有真實目標候選名單，也尚未驗證排程執行成功；第一次排程執行後，可在 Actions 查看結果。儲存庫是 Public，Issue 內的地址和分析結果都將公開，勿寫地主個資。
