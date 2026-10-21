- source_spec: `_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`
  summary: 前端測試（Vitest + React Testing Library）尚未建立，AC-9 的瀏覽器行為無自動化驗證。
  evidence: 切片 1 刻意不引入 JS 測試執行器；後端以 API 行為驗證 AC-9。審查（verification-gap）確認前端無任何自動化測試，屬已知缺口，應於後續切片或課程收尾時處理。
- source_spec: `_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`
  summary: 缺少 CSRF token 機制，session cookie 僅靠 SameSite=Lax 防護跨站寫入。
  evidence: 審查指出 POST 端點無 CSRF token。PRD §4.9 僅要求防注入與防 XSS，未列 CSRF；v1 為純內部工具且 SameSite=Lax 已阻擋大部分跨站 POST，故列為後續項而非本切片缺陷。
- source_spec: `_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`
  summary: 未提供正式 WSGI 伺服器（如 waitress／gunicorn）與容器化（Dockerfile／compose）部署路徑。
  evidence: 審查指出 README 僅以 `flask run` 開發伺服器為部署路徑；PRD 屬課程專案，部署環境未定（PRD §8 Q5），待環境確認後再定。
- source_spec: `_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`
  summary: 未配置 CI（GitHub Actions）自動執行測試與前端建置。
  evidence: 審查指出無 CI 工作流。目前以本機 `pytest` 與 `npm run build` 為驗證訊號；課程專案若要提交作品集，建議後續加入 CI。
- source_spec: `_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`
  summary: `stock_balances` 快取與 `stock_ledger` 之間的一致性由應用層維護，尚無強制對帳機制。
  evidence: 目前只有查詢 API 回傳 `balance_diff` 供人工檢查，寫入路徑（切片 2 的入庫、切片 3 的領用與調貨）尚未實作。PRD FR-31 與 SM-3 要求全域防護，將於切片 2 以服務層（單一寫入入口 + 列鎖）落實。
