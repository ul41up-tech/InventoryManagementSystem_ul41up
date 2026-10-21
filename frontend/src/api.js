// API 呼叫封裝：自動帶 session cookie，統一錯誤處理。
const BASE = ''

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  let payload = null
  try {
    payload = await res.json()
  } catch {
    payload = null
  }

  if (!res.ok) {
    const err = new Error(payload?.error || `請求失敗（${res.status}）`)
    err.status = res.status
    err.payload = payload
    throw err
  }
  return payload
}

export const api = {
  login: (username, password) => request('/api/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  stockQuery: (q) => request(`/api/stock/query?q=${encodeURIComponent(q || '')}`),
  itemBatches: (id) => request(`/api/stock/items/${id}/batches`),
  items: (q) => request(`/api/items?q=${encodeURIComponent(q || '')}`),
  suppliers: () => request('/api/suppliers'),
  customers: () => request('/api/customers'),
  warehouses: () => request('/api/warehouses'),
  locations: () => request('/api/locations'),
  createItem: (payload) => request('/api/items', { method: 'POST', body: payload }),
}
