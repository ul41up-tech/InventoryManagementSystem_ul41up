import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../App.jsx'

const EMPTY_LINE = { quantity: '', unit_cost: '', location_id: '' }

export default function Receiving() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [tab, setTab] = useState('po')
  const [orders, setOrders] = useState([])
  const [locations, setLocations] = useState([])
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)

  // --- 採購單入庫 ---
  const [orderId, setOrderId] = useState('')
  const [poLines, setPoLines] = useState({}) // poLineId -> {quantity, unit_cost, location_id}

  // --- 手動入庫 ---
  const [manual, setManual] = useState({
    item_id: '',
    quantity: '',
    unit_cost: '',
    location_id: '',
    reason: '',
  })

  // --- 位置入庫 ---
  const [locId, setLocId] = useState('')
  const [locItems, setLocItems] = useState([])
  const [locForm, setLocForm] = useState({ item_id: '', quantity: '', unit_cost: '' })
  const [locPoLineId, setLocPoLineId] = useState('')

  useEffect(() => {
    api.purchaseOrders().then((d) => setOrders(d.data)).catch((e) => setError(e.message))
    api.locations().then((d) => setLocations(d.data)).catch(() => {})
    api.items().then((d) => setItems(d.data)).catch(() => {})
  }, [])

  const selectedOrder = useMemo(
    () => orders.find((o) => String(o.id) === String(orderId)),
    [orders, orderId],
  )

  useEffect(() => {
    if (!selectedOrder) {
      setPoLines({})
      return
    }
    const next = {}
    for (const line of selectedOrder.lines) {
      next[line.id] = {
        quantity: '',
        unit_cost: String(line.unit_price),
        location_id: locations[0] ? String(locations[0].id) : '',
      }
    }
    setPoLines(next)
  }, [selectedOrder, locations])

  useEffect(() => {
    if (!locId) {
      setLocItems([])
      return
    }
    api
      .locationItems(locId)
      .then((d) => setLocItems(d.items))
      .catch((e) => setError(e.message))
  }, [locId])

  function setPoLine(lineId, patch) {
    setPoLines((prev) => ({ ...prev, [lineId]: { ...prev[lineId], ...patch } }))
  }

  async function submitPayload(payload, successText) {
    setBusy(true)
    setError('')
    setOk('')
    try {
      const res = await api.createGrn(payload)
      setOk(`${successText}：入庫單 ${res.code}（批次 ${res.batch_codes.join('、')}）`)
      // 重新載入採購單以更新待入庫數量
      const po = await api.purchaseOrders()
      setOrders(po.data)
      if (locId) {
        const li = await api.locationItems(locId)
        setLocItems(li.items)
      }
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setBusy(false)
    }
  }

  async function submitPoReceiving() {
    if (!selectedOrder) {
      setError('請先選擇採購單')
      return
    }
    const lines = []
    for (const line of selectedOrder.lines) {
      const input = poLines[line.id]
      if (!input || input.quantity === '' || Number(input.quantity) <= 0) continue
      lines.push({
        item_id: line.item_id,
        purchase_order_line_id: line.id,
        quantity: Number(input.quantity),
        unit_cost: input.unit_cost === '' ? 0 : Number(input.unit_cost),
        location_id: Number(input.location_id),
      })
    }
    if (lines.length === 0) {
      setError('請至少填寫一筆入庫數量')
      return
    }
    const done = await submitPayload(
      { purchase_order_id: selectedOrder.id, lines },
      '入庫完成',
    )
    if (done) {
      setPoLines(
        Object.fromEntries(
          Object.entries(poLines).map(([k, v]) => [k, { ...v, quantity: '' }]),
        ),
      )
    }
  }

  async function submitManual() {
    if (!manual.item_id || !manual.location_id || !manual.quantity) {
      setError('請填寫商品、數量與庫存位置')
      return
    }
    if (!manual.reason) {
      setError('手動入庫必須填寫原因')
      return
    }
    const done = await submitPayload(
      {
        manual: true,
        reason: manual.reason,
        lines: [
          {
            item_id: Number(manual.item_id),
            quantity: Number(manual.quantity),
            unit_cost: manual.unit_cost === '' ? 0 : Number(manual.unit_cost),
            location_id: Number(manual.location_id),
          },
        ],
      },
      '手動入庫完成',
    )
    if (done) {
      setManual({ item_id: '', quantity: '', unit_cost: '', location_id: '', reason: '' })
    }
  }

  async function submitLocationReceiving() {
    if (!locId || !locForm.item_id || !locForm.quantity) {
      setError('請選擇位置、品項並填寫數量')
      return
    }
    const payload = {
      lines: [
        {
          item_id: Number(locForm.item_id),
          quantity: Number(locForm.quantity),
          unit_cost: locForm.unit_cost === '' ? 0 : Number(locForm.unit_cost),
          location_id: Number(locId),
        },
      ],
    }
    if (isAdmin) {
      payload.manual = true
      payload.reason = '位置入口手動入庫'
    } else {
      if (!locPoLineId) {
        setError('倉管入庫需選擇對應的採購單明細')
        return
      }
      payload.purchase_order_id = Number(String(locPoLineId).split('-')[0])
      payload.lines[0].purchase_order_line_id = Number(String(locPoLineId).split('-')[1])
    }
    const done = await submitPayload(payload, '入庫完成')
    if (done) {
      setLocForm({ item_id: '', quantity: '', unit_cost: '' })
      setLocPoLineId('')
    }
  }

  // 與目前選取品項相關的採購單明細（供倉管在位置入庫時選用）
  const relatedPoLines = useMemo(() => {
    if (!locForm.item_id) return []
    const out = []
    for (const order of orders) {
      for (const line of order.lines) {
        if (String(line.item_id) === String(locForm.item_id)) {
          out.push({
            key: `${order.id}-${line.id}`,
            orderId: order.id,
            lineId: line.id,
            label: `${order.code} / ${line.item_code}（待入庫 ${line.pending_quantity}）`,
          })
        }
      }
    }
    return out
  }, [orders, locForm.item_id])

  return (
    <>
      <div className="toolbar">
        <button className={tab === 'po' ? '' : 'secondary'} onClick={() => setTab('po')}>
          採購單入庫
        </button>
        <button className={tab === 'loc' ? '' : 'secondary'} onClick={() => setTab('loc')}>
          位置入庫
        </button>
        {isAdmin && (
          <button className={tab === 'manual' ? '' : 'secondary'} onClick={() => setTab('manual')}>
            手動入庫（管理員）
          </button>
        )}
      </div>

      {error && <div className="alert error">{error}</div>}
      {ok && <div className="alert ok">{ok}</div>}

      {tab === 'po' && (
        <div className="panel" style={{ padding: 16 }}>
          <div className="toolbar">
            <div className="grow">
              <label htmlFor="po">採購單</label>
              <select
                id="po"
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
              >
                <option value="">— 選擇採購單 —</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.code}（{o.supplier_name}）— {o.lines.length} 筆
                  </option>
                ))}
              </select>
            </div>
          </div>

          {selectedOrder && (
            <table>
              <thead>
                <tr>
                  <th>商品</th>
                  <th className="num">訂購</th>
                  <th className="num">已入庫</th>
                  <th className="num">待入庫</th>
                  <th className="num">預估單價</th>
                  <th className="num">實際入庫數量</th>
                  <th className="num">實際單價</th>
                  <th>庫存位置</th>
                </tr>
              </thead>
              <tbody>
                {selectedOrder.lines.map((line) => {
                  const input = poLines[line.id] || EMPTY_LINE
                  const remaining = line.pending_quantity
                  const over = input.quantity !== '' && Number(input.quantity) > remaining
                  return (
                    <tr key={line.id}>
                      <td>
                        {line.item_code}
                        <div className="muted small">{line.item_name}</div>
                      </td>
                      <td className="num">{line.quantity}</td>
                      <td className="num">{line.received_quantity}</td>
                      <td className="num">{remaining}</td>
                      <td className="num">{line.unit_price}</td>
                      <td className="num">
                        <input
                          type="number"
                          min="0"
                          step="1"
                          style={{ width: 90, textAlign: 'right' }}
                          value={input.quantity}
                          onChange={(e) => setPoLine(line.id, { quantity: e.target.value })}
                        />
                        {over && (
                          <div className="small" style={{ color: 'var(--danger)' }}>
                            超過待入庫 {remaining}
                          </div>
                        )}
                      </td>
                      <td className="num">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          style={{ width: 100, textAlign: 'right' }}
                          value={input.unit_cost}
                          onChange={(e) => setPoLine(line.id, { unit_cost: e.target.value })}
                        />
                      </td>
                      <td>
                        <select
                          value={input.location_id}
                          onChange={(e) => setPoLine(line.id, { location_id: e.target.value })}
                        >
                          <option value="">— 位置 —</option>
                          {locations.map((loc) => (
                            <option key={loc.id} value={loc.id}>
                              {loc.warehouse_code} / {loc.code}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}

          <button onClick={submitPoReceiving} disabled={busy || !selectedOrder}>
            {busy ? '處理中…' : '確認入庫'}
          </button>
          <p className="hint">
            入庫數量不得超過待入庫數量；建立後立即過帳並建立批次，之後不可修改。
          </p>
        </div>
      )}

      {tab === 'loc' && (
        <div className="panel" style={{ padding: 16 }}>
          <div className="toolbar">
            <div className="grow">
              <label htmlFor="loc">庫存位置</label>
              <select id="loc" value={locId} onChange={(e) => setLocId(e.target.value)}>
                <option value="">— 選擇位置 —</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.warehouse_code} / {loc.code} {loc.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {locId && (
            <>
              <table>
                <thead>
                  <tr>
                    <th>商品</th>
                    <th className="num">該位置庫存</th>
                    <th className="num">本次入庫數量</th>
                    <th className="num">實際單價</th>
                    <th>採購單明細</th>
                  </tr>
                </thead>
                <tbody>
                  {locItems.length === 0 && (
                    <tr>
                      <td colSpan={5} className="muted">
                        該位置目前沒有品項
                      </td>
                    </tr>
                  )}
                  {locItems.map((item) => (
                    <tr key={item.item_id}>
                      <td>
                        {item.item_code}
                        <div className="muted small">{item.item_name}</div>
                      </td>
                      <td className="num">{item.on_hand}</td>
                      <td className="num">
                        <input
                          type="number"
                          min="0"
                          step="1"
                          style={{ width: 90, textAlign: 'right' }}
                          value={locForm.item_id === String(item.item_id) ? locForm.quantity : ''}
                          onFocus={() =>
                            setLocForm((f) => ({ ...f, item_id: String(item.item_id) }))
                          }
                          onChange={(e) =>
                            setLocForm((f) => ({
                              ...f,
                              item_id: String(item.item_id),
                              quantity: e.target.value,
                            }))
                          }
                        />
                      </td>
                      <td className="num">
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          style={{ width: 100, textAlign: 'right' }}
                          value={locForm.item_id === String(item.item_id) ? locForm.unit_cost : ''}
                          onChange={(e) =>
                            setLocForm((f) => ({ ...f, unit_cost: e.target.value }))
                          }
                        />
                      </td>
                      <td>
                        {isAdmin ? (
                          <span className="muted small">手動入庫（管理員）</span>
                        ) : relatedPoLines.length === 0 ? (
                          <span className="muted small">此商品沒有可用的採購單</span>
                        ) : (
                          <select
                            value={locPoLineId}
                            onChange={(e) => setLocPoLineId(e.target.value)}
                          >
                            <option value="">— 選擇採購單明細 —</option>
                            {relatedPoLines.map((r) => (
                              <option key={r.key} value={r.key}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <button onClick={submitLocationReceiving} disabled={busy}>
                {busy ? '處理中…' : '確認入庫'}
              </button>
            </>
          )}
        </div>
      )}

      {tab === 'manual' && isAdmin && (
        <div className="panel" style={{ padding: 16 }}>
          <div className="toolbar">
            <div className="grow">
              <label htmlFor="m-item">商品</label>
              <select
                id="m-item"
                value={manual.item_id}
                onChange={(e) => setManual((m) => ({ ...m, item_id: e.target.value }))}
              >
                <option value="">— 選擇商品 —</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="m-qty">數量</label>
              <input
                id="m-qty"
                type="number"
                min="0"
                step="1"
                style={{ width: 120 }}
                value={manual.quantity}
                onChange={(e) => setManual((m) => ({ ...m, quantity: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="m-cost">實際單價</label>
              <input
                id="m-cost"
                type="number"
                min="0"
                step="0.01"
                style={{ width: 120 }}
                value={manual.unit_cost}
                onChange={(e) => setManual((m) => ({ ...m, unit_cost: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="m-loc">庫存位置</label>
              <select
                id="m-loc"
                value={manual.location_id}
                onChange={(e) => setManual((m) => ({ ...m, location_id: e.target.value }))}
              >
                <option value="">— 位置 —</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.warehouse_code} / {loc.code}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <label htmlFor="m-reason">原因（必填）</label>
          <input
            id="m-reason"
            value={manual.reason}
            placeholder="例如：供應商補貨、盤點剩餘、樣品入庫"
            onChange={(e) => setManual((m) => ({ ...m, reason: e.target.value }))}
          />

          <button onClick={submitManual} disabled={busy}>
            {busy ? '處理中…' : '確認入庫'}
          </button>
        </div>
      )}
    </>
  )
}
