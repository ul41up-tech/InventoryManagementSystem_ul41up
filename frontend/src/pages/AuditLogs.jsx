import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function AuditLogs() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [action, setAction] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load(nextAction = action) {
    setLoading(true)
    setError('')
    try {
      const data = await api.auditLogs({ limit: 100, action: nextAction })
      setRows(data.data)
      setTotal(data.total)
    } catch (err) {
      setError(err.message)
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('')
  }, [])

  return (
    <>
      <div className="toolbar">
        <div>
          <label htmlFor="action">動作類型</label>
          <select id="action" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">全部</option>
            <option value="LOGIN_SUCCESS">登入成功</option>
            <option value="LOGIN_FAILED">登入失敗</option>
            <option value="ACCOUNT_LOCKED">帳號鎖定</option>
            <option value="ACCOUNT_UNLOCKED">帳號解鎖</option>
            <option value="LOGOUT">登出</option>
            <option value="ACCESS_DENIED">越權存取</option>
            <option value="ITEM_CREATED">建立商品</option>
            <option value="PASSWORD_CHANGED">更改密碼</option>
            <option value="SEED_EXECUTED">種子資料</option>
          </select>
        </div>
        <button onClick={() => load()} disabled={loading}>
          {loading ? '載入中…' : '查詢'}
        </button>
        <p className="hint" style={{ marginTop: 0 }}>
          共 {total} 筆。操作紀錄僅可讀取，不可修改或刪除。
        </p>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="panel">
        <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>時間</th>
              <th>操作人</th>
              <th>動作</th>
              <th>單據</th>
              <th>數量</th>
              <th>說明</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={6}>
                  <div className="empty">{error ? '查詢失敗' : '尚無紀錄'}</div>
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="small">{row.created_at?.replace('T', ' ').slice(0, 19)}</td>
                <td>{row.operator || '—'}</td>
                <td>
                  <span className="badge">{row.action}</span>
                </td>
                <td className="small">
                  {row.doc_type ? `${row.doc_type} ${row.doc_id ?? ''}` : '—'}
                </td>
                <td className="num">{row.qty ?? '—'}</td>
                <td className="small muted">{row.detail || row.reason || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </>
  )
}
