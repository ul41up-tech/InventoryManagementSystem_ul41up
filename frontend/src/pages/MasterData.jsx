import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../App.jsx'

const ALL_TABS = [
  { key: 'items', label: '商品', fetcher: api.items, roles: ['admin', 'warehouse', 'purchasing', 'sales', 'accounting'] },
  { key: 'suppliers', label: '供應商', fetcher: api.suppliers, roles: ['admin', 'purchasing', 'sales', 'accounting'] },
  { key: 'customers', label: '客戶', fetcher: api.customers, roles: ['admin', 'purchasing', 'sales', 'accounting'] },
  { key: 'warehouses', label: '倉庫', fetcher: api.warehouses, roles: ['admin', 'accounting'] },
  { key: 'locations', label: '庫存位置', fetcher: api.locations, roles: ['admin', 'accounting'] },
]

export default function MasterData() {
  const { user } = useAuth()
  const tabs = ALL_TABS.filter((t) => t.roles.includes(user?.role))
  const [tab, setTab] = useState(tabs[0]?.key ?? 'items')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    const current = ALL_TABS.find((t) => t.key === tab)
    if (!current) return undefined
    setLoading(true)
    setError('')
    current
      .fetcher()
      .then((data) => {
        if (alive) setRows(data.data)
      })
      .catch((err) => {
        if (!alive) return
        setError(err.message)
        setRows([])
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [tab])

  // 角色可用頁籤變動時，確保目前選中的是可用的
  useEffect(() => {
    if (!tabs.some((t) => t.key === tab) && tabs.length > 0) {
      setTab(tabs[0].key)
    }
  }, [tabs, tab])

  return (
    <>
      <div className="toolbar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? '' : 'secondary'}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="panel">
        <table>
          <thead>
            <tr>
              {tab === 'items' && (
                <>
                  <th>編號</th>
                  <th>名稱</th>
                  <th>單位</th>
                  <th className="num">建議售價</th>
                  <th className="num">預估毛利率</th>
                </>
              )}
              {tab === 'suppliers' && (
                <>
                  <th>統一編號</th>
                  <th>公司名稱</th>
                  <th>聯絡人</th>
                  <th>電話</th>
                </>
              )}
              {tab === 'customers' && (
                <>
                  <th>客戶名稱</th>
                  <th>聯絡人</th>
                  <th>電話</th>
                </>
              )}
              {tab === 'warehouses' && (
                <>
                  <th>代碼</th>
                  <th>名稱</th>
                  <th>類型</th>
                </>
              )}
              {tab === 'locations' && (
                <>
                  <th>位置代碼</th>
                  <th>位置名稱</th>
                  <th>所屬倉庫</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="muted">
                  載入中…
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  {error ? '查詢失敗' : '尚無資料'}
                </td>
              </tr>
            )}
            {!loading &&
              rows.map((row, index) => (
                <tr key={row.id ?? index}>
                  {tab === 'items' && (
                    <>
                      <td>{row.code}</td>
                      <td>{row.name}</td>
                      <td>{row.unit}</td>
                      <td className="num">{row.suggested_price}</td>
                      <td className="num">
                        {row.target_margin_rate != null
                          ? `${(row.target_margin_rate * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                    </>
                  )}
                  {tab === 'suppliers' && (
                    <>
                      <td>{row.tax_id}</td>
                      <td>{row.name}</td>
                      <td>{row.contact}</td>
                      <td>{row.phone}</td>
                    </>
                  )}
                  {tab === 'customers' && (
                    <>
                      <td>{row.name}</td>
                      <td>{row.contact ?? '—'}</td>
                      <td>{row.phone ?? '—'}</td>
                    </>
                  )}
                  {tab === 'warehouses' && (
                    <>
                      <td>{row.code}</td>
                      <td>{row.name}</td>
                      <td>{row.is_virtual ? '虛擬（在途）' : '實體'}</td>
                    </>
                  )}
                  {tab === 'locations' && (
                    <>
                      <td>{row.code}</td>
                      <td>{row.name}</td>
                      <td>
                        {row.warehouse_code} {row.warehouse_name}
                      </td>
                    </>
                  )}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
