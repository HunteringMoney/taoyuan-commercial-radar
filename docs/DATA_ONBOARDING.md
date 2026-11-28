# 桃園區商業區土地獵人｜資料接入與首批候選目標操作手冊

更新：2026-11-28

## 2026-11-28 試驗資料已接入

55-1 地號已由市府地籍圖層定位，市府都市計畫圖層在地號與首筆待查建物群中心均回傳商業區。使用者截圖已用七個分布控制點配準，產生 `docs/pilot_red_draft.geojson`；OSM 建物輪廓加入官方圖形與紅色草稿雙重篩選，`docs/pilot_scout_candidates.json` 有 **1 個真實座標的待查建物群**。具體證據與限制見 `docs/PILOT_GIS_2026-11-28.md`。

此處完成的是**可重現的試驗流程**。七點使用同一市府圖層，需要獨立複核絕對定位；最新生效計畫、圖層再利用條件、候選地籍與現場條件仍待核對。GitHub Actions 於 11/28 再次對市府服務逾時，尚未形成雲端每日自動取得圖資的流程。以下既有步驟供正式資料取得與驗證時使用；`docs/targets.json` 不因試驗結果而開放。

## 目標與現狀

本專案**只尋找桃園市桃園區的法定都市計畫商業區**。住宅區、分區不明、跨界未核對的區塊均不發布。
目前 docs/targets.json 尚無正式候選基地。排程成功代表「檢查程序成功」，**不是找到土地**。
已新增 scripts/candidate_discovery.py：官方商業區邊界驗證完成後，能套疊合法取得的建物輪廓，輸出「待現場勘查」的建物群，與正式地籍基地不同。

## 正式候選前仍需完成的外部資料工作

向**桃園市政府都市發展局**確認是否可依授權取得：
1. 桃園區適用之**最新公告**各都市計畫商業區向量範圍（GeoJSON、SHP、GeoPackage 皆可），包括計畫名稱、圖層欄位定義、公告生效日期、坐標系統；
2. 桃園區行政區界向量來源與版本；
3. 是否允許程式化查詢、衍生分析、網站公開呈現和資料再利用；
4. 若無法提供向量資料，是否有官方可用服務及授權介接方式。

人工查看入口：
- https://urplanning.tycg.gov.tw/gisMap/
- https://urdb.tycg.gov.tw/News_Content.aspx?n=15598&s=1090647

**不能**用地圖紅色截圖、OpenStreetMap 的 commercial 標籤、低樓層外觀或未知的 AA 代碼，直接認定法定商業區。
公開的「桃園市都市計畫土地使用面積」只有統計表，不能取代具地理座標的邊界。

## 資料到手後的操作（皆用 EPSG:4326 GeoJSON）

建立本地 input/ 資料夾（不要把未授權或機密資料上傳 public 儲存庫）：

- `input/commercial.geojson`：官方使用分區面狀資料，屬性 `使用分區` 必須是可查核的明確名稱。
- `input/district.geojson`：獨立來源的桃園區官方行政界，必須有 `COUNTY=桃園市`、`TOWN=桃園區`。
- `input/source_metadata.json`：完整來源、版本與授權說明。參考 `scripts/validate_official_commercial_boundary.py` 必要欄位。
- `input/buildings.geojson`：經確認可合法利用的建物輪廓。不得把輪廓當地籍、不得猜屋齡。

執行：

```bash
python -m pip install 'shapely>=2,<3'
cd scripts
python -m unittest test_boundary.py test_candidate_discovery.py -v
cd ..
python scripts/validate_official_commercial_boundary.py \
  --zoning input/commercial.geojson \
  --district input/district.geojson \
  --metadata input/source_metadata.json \
  --output input/verified_commercial.geojson \
  --report input/official_zoning_review.json

python scripts/candidate_discovery.py \
  --commercial input/verified_commercial.geojson \
  --buildings input/buildings.geojson \
  --output input/scout_candidates.json
```

## 品質門檻：不得省略

1. 驗證官方分區檔、圖例與有效版本；不能只靠 metadata 人工填 true。原始資料及核對過程應留查核紀錄。
2. 至少十個人工控制點（商業區及住宅區均須包含）；邊界橫跨不同分區者不列入。
3. 校對法定桃園區行政界與各不同都市計畫適用區域，避免只跑舊城測試矩形。
4. 每個候選群附可重現的座標、建物來源、分區版本、影像／現場查證狀態；禁止把粗略輪廓分群評分視為建築可行性。
5. 初版 scout_candidates.json 只能當**現勘線索**，不得直接轉成 docs/targets.json，亦不產生「已驗證基地」GitHub Issues。
6. 不在 public 儲存庫刊登地主姓名、聯絡方式、談判紀錄。

## 下一輪應做的程式任務（順序不可顛倒）

- [ ] 取得官方商業區向量資料和合法授權，並保留原始來源的雜湊與有效公告日期。
- [ ] 擴充驗證器：檢查十個已知分區點，將結果納入可讀的機器驗收報告。
- [ ] 取得可使用的建物輪廓與來源日期，測試不跨越住宅區邊界。
- [ ] 用實際資料跑出第一批待現勘群，手動抽樣至少五處，記錄誤判原因。
- [ ] 再加入道路寬度、面寬與地籍面積的可合法取得欄位；缺漏者不得補猜。
- [ ] 通過分區、來源與人工審核後才產出正式 targets.json 並在手機網頁發布。
- [ ] 建立真正的資料更新排程；目前排程主要做連線診斷與新目標通知，尚未建立每日有效候選資料產製作業。

### 明確驗收

**第一關**：有通過官方來源比對的桃園區商業區 GeoJSON。
**第二關**：真實資料產生可定位的待勘查建物群（不虛報地號或屋齡）。
**第三關**：至少 10 個人工核對過的實際候選街廓，並完成 5 處抽樣；無法取得足量合格目標就如實報告數量。
**第四關**：手機端可以檢視有來源與驗證狀態的名單；排程自動更新，有問題時顯示明確的失敗／待資料狀態。

> 目前「正式驗證開發基地」仍為 **0**，這不是程式故障，而是尚未取得可靠官方邊界與真實建物資料的客觀現況。
