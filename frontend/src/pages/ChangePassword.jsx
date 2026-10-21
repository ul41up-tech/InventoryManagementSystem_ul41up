import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'
import { api } from '../api.js'

export default function ChangePassword() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)
  const { user, setUser } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setOk('')
    if (newPassword !== confirm) {
      setError('兩次輸入的新密碼不一致')
      return
    }
    setBusy(true)
    try {
      await api.changePassword(oldPassword, newPassword)
      setUser((prev) => ({ ...prev, must_change_password: false }))
      setOk('密碼已更新，正在返回…')
      setTimeout(() => navigate('/stock', { replace: true }), 800)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container" style={{ maxWidth: 460 }}>
      <form className="login-card" onSubmit={handleSubmit} style={{ maxWidth: '100%' }}>
        <h1>更改密碼</h1>
        <p className="sub">
          {user?.must_change_password
            ? '這是首次登入，請先設定新密碼。'
            : '請輸入舊密碼與新密碼。'}
        </p>

        <label htmlFor="old">舊密碼</label>
        <input
          id="old"
          type="password"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          autoComplete="current-password"
        />

        <label htmlFor="new">新密碼（至少 8 個字元）</label>
        <input
          id="new"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          autoComplete="new-password"
        />

        <label htmlFor="confirm">確認新密碼</label>
        <input
          id="confirm"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
        />

        <button type="submit" disabled={busy}>
          {busy ? '更新中…' : '更新密碼'}
        </button>
        {error && <div className="alert error">{error}</div>}
        {ok && <div className="alert ok">{ok}</div>}
      </form>
    </div>
  )
}
