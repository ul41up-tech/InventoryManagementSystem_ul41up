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
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>庫存管理系統</h1>
        <p className="sub">請以公司帳號登入</p>

        <label htmlFor="username">帳號</label>
        <input
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
        />

        <label htmlFor="password">密碼</label>
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
      </form>
    </div>
  )
}
