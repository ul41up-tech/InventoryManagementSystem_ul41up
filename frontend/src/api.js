// API 呼叫封裝：自動帶 session cookie、逾時控制、401 導回登入頁。
const BASE = ''
const TIMEOUT_MS = 15000

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', body } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  let res
  try {
    res = await fetch(BASE + path, {
      method,
      credentials: 'include',
      signal: controller.signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    clearTimeout(timer)
    if (err.name === 'AbortError') {
      throw new ApiError('請求逾時，請稍後再試', 0)
    }
    throw new ApiError('無法連線到伺服器，請確認後端已啟動', 0)
  } finally {
    clearTimeout(timer)
  }

  let payload = null
  try {
    payload = await res.json()
  } catch {
    payload = null
  }

  if (!res.ok) {
    // Session 過期或未登入 → 導回登入頁（避免畫面停在舊資料上）
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    const message =
      payload?.error ||
      (res.status === 403
        ? '權限不足，無法執行此操作'
        : res.status === 404
          ? '找不到資料'
          : `請求失敗（${res.status}）`)
    throw new ApiError(message, res.status)
  }
  return payload
}

export const api = {
  login: (username, password) => request('/api/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  changePassword: (oldPassword, newPassword) =>
    request('/api/auth/change-password', {
      method: 'POST',
      body: { old_password: oldPassword, new_password: newPassword },
    }),
  stockQuery: (q) => request(`/api/stock/query?q=${encodeURIComponent(q || '')}`),
  itemBatches: (id) => request(`/api/stock/items/${id}/batches`),
  items: (q) => request(`/api/items?q=${encodeURIComponent(q || '')}`),
  suppliers: () => request('/api/suppliers'),
  customers: () => request('/api/customers'),
  warehouses: () => request('/api/warehouses'),
  locations: () => request('/api/locations'),
  auditLogs: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`/api/audit-logs${query ? `?${query}` : ''}`)
  },
  createItem: (payload) => request('/api/items', { method: 'POST', body: payload }),
}
