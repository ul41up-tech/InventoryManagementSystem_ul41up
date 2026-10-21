import { Fragment, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

export default function StockQuery() {
  const [keyword, setKeyword] = useState('')
  const [rows, setRows] = useState([])
  const [expanded, setExpanded] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const searchSeq = useRef(0)

  async function search(q = keyword) {
    const seq = ++searchSeq.current
    setLoading(true)
    setError('')
    try {
      const data = await api.stockQuery(q)
      if (seq !== searchSeq.current) return // 捨棄過期的回應
      setRows(data.data)
      setSearched(true)
    } catch (err) {
      if (seq !== searchSeq.current) return
      setError(err.message)
      setRows([])
    } finally {
      if (seq === searchSeq.current) setLoading(false)
    }
  }

  useEffect(() => {
    search('')
  }, [])

  function toggle(item) {
    setExpanded(expanded === item.id ? null : item.id)
  }

  function clearAll() {
    setKeyword('')
    setExpanded(null)
    search('')
  }

  return (
    <>
      <div className="toolbar">
        <div className="grow">
          <label htmlFor="q">商品名稱或商品編號</label>
          <input
            id="q"
            value={keyword}
            placeholder="例如：螺絲"
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') search()
            }}
          />
        </div>
        <button onClick={() => search()} disabled={loading}>
          {loading ? '查詢中…' : '查詢'}
        </button>
        <button className="secondary" onClick={clearAll}>
          清除
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}
      {searched && !loading && (
        <p className="hint">
          共 {rows.length} 筆。點擊列可展開各庫存位置明細。在手量含在途；可用量 = 在手量 − 已配置數量。
        </p>
      )}

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>商品編號</th>
              <th>商品名稱</th>
              <th className="num">在手量</th>
              <th className="num">可用量</th>
              <th className="num">在途量</th>
              <th className="num">實體倉合計</th>
              <th className="num">建議售價</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && searched && !loading && (
              <tr>
                <td colSpan={7} className="muted">
                  查無符合的商品
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  onClick={() => toggle(row)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      toggle(row)
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  aria-expanded={expanded === row.id}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{row.code}</td>
                  <td>{row.name}</td>
                  <td className="num">{row.on_hand}</td>
                  <td className="num">{row.available}</td>
                  <td className="num">
                    {row.in_transit > 0 ? <span className="badge transit">{row.in_transit}</span> : 0}
                  </td>
                  <td className="num">{row.real_on_hand}</td>
                  <td className="num">{row.suggested_price}</td>
                </tr>
                {expanded === row.id && (
                  <tr>
                    <td colSpan={7} style={{ background: '#fafbfc' }}>
                      <table>
                        <thead>
                          <tr>
                            <th>倉庫</th>
                            <th>庫存位置</th>
                            <th>批次</th>
                            <th>效期</th>
                            <th className="num">在手量</th>
                            <th className="num">已配置</th>
                            <th className="num">可用量</th>
                          </tr>
                        </thead>
                        <tbody>
                          {row.locations.map((loc, index) => (
                            <tr key={`${loc.batch_code}-${loc.location_code}-${index}`}>
                              <td>
                                {loc.warehouse_name}
                                {loc.is_virtual && <span className="badge transit"> 在途</span>}
                              </td>
                              <td>{loc.location_code}</td>
                              <td>{loc.batch_code}</td>
                              <td className="muted">{loc.expiry_date || '—'}</td>
                              <td className="num">{loc.on_hand}</td>
                              <td className="num">{loc.allocated}</td>
                              <td className="num">{loc.available}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
