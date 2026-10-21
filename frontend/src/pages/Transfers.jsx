import { useEffect, useState } from 'react'
import { api } from '../api.js'

const STATUS_LABEL = {
  draft: { text: '草稿', cls: '' },
  in_transit: { text: '在途', cls: 'transit' },
  received: { text: '已收貨', cls: 'ok' },
}

export default function Transfers() {
  const [orders, setOrders] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [locations, setLocations] = useState([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)

  // 建立調貨單
  const [form, setForm] = useState({ from_warehouse_id: '', to_warehouse_id: '', demand_source: '' })
  const [lines, setLines] = useState([{ item_id: '', batch_id: '', quantity: '' }])
  const [items, setItems] = useState([])
  const [batches, setBatches] = useState([]) // 目前選取商品的批次清單

  // 收貨
  const [receiveOrder, setReceiveOrder] = useState(null)
  const [receipts, setReceipts] = useState({})

  useEffect(() => {
    reload()
    api.warehouses().then((d) => setWarehouses(d.data)).catch(() => {})
    api.locations().then((d) => setLocations(d.data)).catch(() => {})
    api.items().then((d) => setItems(d.data)).catch(() => {})
  }, [])

  async function reload() {
    try {
      const d = await api.transferOrders()
      setOrders(d.data)
    } catch (e) {
      setError(e.message)
    }
  }

  function updateLine(index, patch) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)))
  }

  async function loadBatches(itemId) {
    if (!itemId) {
      setBatches([])
      return
    }
    try {
      const d = await api.itemBatches(itemId)
      setBatches(d.data)
    } catch {
      setBatches([])
    }
  }

  async function createOrder() {
    setError('')
    setOk('')
    if (!form.from_warehouse_id || !form.to_warehouse_id) {
      setError('請選擇來源倉庫與目的倉庫')
      return
    }
    const payload = {
      from_warehouse_id: Number(form.from_warehouse_id),
      to_warehouse_id: Number(form.to_warehouse_id),
      demand_source: form.demand_source,
      lines: lines
        .filter((l) => l.batch_id && l.quantity)
        .map((l) => {
          const batch = batches.find((b) => String(b.batch_id) === String(l.batch_id))
          return {
            batch_id: Number(l.batch_id),
            from_location_id: batch ? batch.location_id : null,
            quantity: Number(l.quantity),
          }
        }),
    }
    if (payload.lines.length === 0) {
      setError('請至少填寫一筆明細')
      return
    }
    setBusy(true)
    try {
      const res = await api.createTransferOrder(payload)
      setOk(`調貨單 ${res.code} 已建立`)
      setLines([{ item_id: '', batch_id: '', quantity: '' }])
      setForm({ from_warehouse_id: '', to_warehouse_id: '', demand_source: '' })
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function ship(order) {
    setError('')
    setOk('')
    setBusy(true)
    try {
      const res = await api.shipTransfer(order.id)
      setOk(`調貨單 ${res.code} 已出庫，數量轉為在途`)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function receive(order) {
    setError('')
    setOk('')
    const payload = {
      receipts: order.lines.map((line) => ({
        line_id: line.id,
        quantity: receipts[line.id] ?? line.quantity,
        location_id: Number(receipts[`${line.id}-loc`] ?? 0),
      })),
    }
    if (payload.receipts.some((r) => !r.location_id)) {
      setError('請為每筆明細選擇收貨的庫存位置')
      return
    }
    setBusy(true)
    try {
      const res = await api.receiveTransfer(order.id, payload)
      setOk(`調貨單 ${res.code} 已收貨`)
      setReceiveOrder(null)
      setReceipts({})
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const locationsOf = (whCode) => locations.filter((l) => l.warehouse_code === whCode)

  return (
    <>
      {error && <div className="alert error">{error}</div>}
      {ok && <div className="alert ok">{ok}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="section-title">建立調貨單</div>
        <div className="toolbar">
          <div>
            <label htmlFor="from-wh">來源倉庫</label>
            <select
              id="from-wh"
              value={form.from_warehouse_id}
              onChange={(e) => setForm((f) => ({ ...f, from_warehouse_id: e.target.value }))}
            >
              <option value="">— 選擇 —</option>
              {warehouses
                .filter((w) => !w.is_virtual)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} {w.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label htmlFor="to-wh">目的倉庫</label>
            <select
              id="to-wh"
              value={form.to_warehouse_id}
              onChange={(e) => setForm((f) => ({ ...f, to_warehouse_id: e.target.value }))}
            >
              <option value="">— 選擇 —</option>
              {warehouses
                .filter((w) => !w.is_virtual)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} {w.name}
                  </option>
                ))}
            </select>
          </div>
          <div className="grow">
            <label htmlFor="demand">需求來源（選填）</label>
            <input
              id="demand"
              value={form.demand_source}
              placeholder="例如：南港倉缺貨"
              onChange={(e) => setForm((f) => ({ ...f, demand_source: e.target.value }))}
            />
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>商品</th>
                <th>批次（來源庫位）</th>
                <th className="num">數量</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={index}>
                  <td>
                    <select
                      value={line.item_id}
                      onChange={(e) => {
                        updateLine(index, { item_id: e.target.value, batch_id: '' })
                        loadBatches(e.target.value)
                      }}
                    >
                      <option value="">— 商品 —</option>
                      {items.map((it) => (
                        <option key={it.id} value={it.id}>
                          {it.code} {it.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={line.batch_id}
                      onChange={(e) => updateLine(index, { batch_id: e.target.value })}
                    >
                      <option value="">— 批次 —</option>
                      {batches
                        .filter(
                          (b) =>
                            !b.is_virtual &&
                            b.on_hand > 0 &&
                            (!form.from_warehouse_id ||
                              b.warehouse_id === Number(form.from_warehouse_id)),
                        )
                        .map((b) => (
                          <option key={b.batch_id} value={b.batch_id}>
                            {b.batch_code}（{b.warehouse_code}/{b.location_code}，可用 {b.on_hand}）
                          </option>
                        ))}
                    </select>
                  </td>
                  <td className="num">
                    <input
                      type="number"
                      min="0"
                      step="1"
                      style={{ width: 110, textAlign: 'right' }}
                      value={line.quantity}
                      onChange={(e) => updateLine(index, { quantity: e.target.value })}
                    />
                  </td>
                  <td>
                    {lines.length > 1 && (
                      <button
                        className="ghost sm"
                        onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}
                      >
                        移除
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="toolbar" style={{ marginTop: 12 }}>
          <button
            className="secondary"
            onClick={() =>
              setLines((prev) => [...prev, { item_id: '', batch_id: '', quantity: '' }])
            }
          >
            新增明細
          </button>
          <button onClick={createOrder} disabled={busy}>
            {busy ? '處理中…' : '建立調貨單'}
          </button>
        </div>
        <p className="hint">
          調出數量不得超過來源庫位可用量；批次沿用原批次，不另建批次。出庫後數量顯示為「在途」，收貨後才進入目的倉。
        </p>
      </div>

      <div className="section-title">調貨單</div>
      <div className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>調貨單</th>
                <th>方向</th>
                <th>狀態</th>
                <th>明細</th>
                <th className="num">數量</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="empty">尚無調貨單</div>
                  </td>
                </tr>
              )}
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>
                    {order.code}
                    {order.demand_source && (
                      <div className="muted small">{order.demand_source}</div>
                    )}
                  </td>
                  <td className="small">
                    {order.from_warehouse_code} → {order.to_warehouse_code}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_LABEL[order.status]?.cls || ''}`}>
                      {STATUS_LABEL[order.status]?.text || order.status}
                    </span>
                  </td>
                  <td className="small">
                    {order.lines.map((l) => (
                      <div key={l.id}>
                        {l.item_code} / {l.batch_code}
                        {l.shortage > 0 && (
                          <span className="badge danger" style={{ marginLeft: 6 }}>
                            短缺 {l.shortage}
                          </span>
                        )}
                      </div>
                    ))}
                  </td>
                  <td className="num">
                    {order.lines.reduce((s, l) => s + l.quantity, 0)}
                    {order.lines.some((l) => l.received_quantity !== null) && (
                      <div className="muted small">
                        實收 {order.lines.reduce((s, l) => s + (l.received_quantity || 0), 0)}
                      </div>
                    )}
                  </td>
                  <td>
                    {order.status === 'draft' && (
                      <button className="sm" onClick={() => ship(order)} disabled={busy}>
                        出庫
                      </button>
                    )}
                    {order.status === 'in_transit' && (
                      <button
                        className="sm"
                        onClick={() => {
                          setReceiveOrder(order)
                          const init = {}
                          for (const line of order.lines) {
                            init[line.id] = line.quantity
                            init[`${line.id}-loc`] = ''
                          }
                          setReceipts(init)
                        }}
                      >
                        收貨
                      </button>
                    )}
                    {order.status === 'received' && <span className="muted small">已完成</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {receiveOrder && (
        <div className="card" style={{ marginTop: 18 }}>
          <div className="section-title">收貨：{receiveOrder.code}</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>商品 / 批次</th>
                  <th className="num">調出數量</th>
                  <th className="num">實收數量</th>
                  <th>收貨庫位</th>
                </tr>
              </thead>
              <tbody>
                {receiveOrder.lines.map((line) => (
                  <tr key={line.id}>
                    <td>
                      {line.item_code} / {line.batch_code}
                      <div className="muted small">來源 {line.from_location_code}</div>
                    </td>
                    <td className="num">{line.quantity}</td>
                    <td className="num">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        style={{ width: 110, textAlign: 'right' }}
                        value={receipts[line.id] ?? ''}
                        onChange={(e) =>
                          setReceipts((r) => ({ ...r, [line.id]: e.target.value }))
                        }
                      />
                    </td>
                    <td>
                      <select
                        value={receipts[`${line.id}-loc`] ?? ''}
                        onChange={(e) =>
                          setReceipts((r) => ({ ...r, [`${line.id}-loc`]: e.target.value }))
                        }
                      >
                        <option value="">— 庫位 —</option>
                        {locationsOf(receiveOrder.to_warehouse_code).map((l) => (
                          <option key={l.id} value={l.id}>
                            {l.code} {l.name}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button onClick={() => receive(receiveOrder)} disabled={busy}>
              確認收貨
            </button>
            <button className="secondary" onClick={() => setReceiveOrder(null)}>
              取消
            </button>
          </div>
          <p className="hint">實收少於調出數量時，短缺數量會留在在途位置並標記，實際認列（調整單）於後續切片處理。</p>
        </div>
      )}
    </>
  )
}
