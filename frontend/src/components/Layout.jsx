import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const roleLabel = {
    admin: '管理員',
    warehouse: '倉管',
    purchasing: '採購',
    sales: '銷售',
    accounting: '會計',
  }[user?.role] || user?.role

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <>
      <header className="app-header">
        <h1>庫存管理系統</h1>
        <nav>
          <NavLink to="/stock" className={({ isActive }) => (isActive ? 'active' : '')}>
            庫存查詢
          </NavLink>
          <NavLink to="/master" className={({ isActive }) => (isActive ? 'active' : '')}>
            主檔瀏覽
          </NavLink>
        </nav>
        <span className="who">
          {user?.name}（{roleLabel}）
        </span>
        <button onClick={handleLogout}>登出</button>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
