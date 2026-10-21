import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'
import { api } from '../api.js'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api.login(username.trim(), password)
      setUser(data.user)
      navigate(location.state?.from || '/stock', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <section className="login-hero">
        <div className="eyebrow">AILearn Inventory</div>
        <h1>
          讓庫存、單據、
          <br />
          成本與毛利
          <br />
          對得上
        </h1>
        <p>
          多倉庫進銷存系統。商品 → 單據 → 餘額 → 成本 → 毛利，
          每一個數字都追得回來源、查得出是誰動的。
        </p>
        <ul>
          <li>多倉庫、多庫存位置，批次與效期完整追蹤</li>
          <li>五種角色權限，操作紀錄不可刪除</li>
          <li>入庫、調貨、銷貨、采购、盤點一條主線</li>
        </ul>
      </section>

      <section className="login-side">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>登入</h1>
          <p className="sub">請以公司帳號登入系統</p>

          <label htmlFor="username">帳號</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
          />

          <label htmlFor="password" style={{ marginTop: 14 }}>
            密碼
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />

          <button type="submit" disabled={busy}>
            {busy ? '登入中…' : '登入'}
          </button>

          {error && <div className="alert error">{error}</div>}

          <div className="login-hint">
            示範帳號：<code>admin</code> <code>warehouse</code> <code>purchasing</code>{' '}
            <code>sales</code> <code>accounting</code>
            <br />
            初始密碼見 <code>backend/.env</code> 的 SEED_PASSWORD；首次登入會要求更改密碼。
          </div>
        </form>
      </section>
    </div>
  )
}
