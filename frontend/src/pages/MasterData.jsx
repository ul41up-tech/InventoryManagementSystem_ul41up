import { useEffect, useState } from 'react'
import { api } from '../api.js'

const TABS = [
  { key: 'items', label: '商品', fetcher: api.items },
  { key: 'suppliers', label: '供應商', fetcher: api.suppliers },
  { key: 'customers', label: '客戶', fetcher: api.customers },
  { key: 'warehouses', label: '倉庫', fetcher: api.warehouses },
  { key: 'locations', label: '庫存位置', fetcher: api.locations },
]

export default function MasterData() {
  const [tab, setTab] = useState('items')
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    const current = TABS.find((t) => t.key === tab)
    setError('')
    current
      .fetcher()
      .then((data) => setRows(data.data))
      .catch((err) => {
        setError(err.message)
        setRows([])
      })
  }, [tab])

  return (
    <>
      <div className="toolbar">
        {TABS.map((t) => (
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
            {rows.map((row, index) => (
              <tr key={row.id ?? index}>
                {tab === 'items' && (
                  <>
                    <td>{row.code}</td>
                    <td>{row.name}</td>
                    <td>{row.unit}</td>
                    <td className="num">{row.suggested_price}</td>
                    <td className="num">
                      {row.target_margin_rate ? `${(row.target_margin_rate * 100).toFixed(0)}%` : '—'}
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
                    <td>{row.contact}</td>
                    <td>{row.phone}</td>
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
