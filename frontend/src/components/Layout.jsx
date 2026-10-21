import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'

const ROLE_LABEL = {
  admin: '管理員',
  warehouse: '倉管',
  purchasing: '採購',
  sales: '銷售',
  accounting: '會計',
}

// 各角色可進入的頁籤（對應 PRD §4.1 權限矩陣）
const NAV_BY_ROLE = {
  admin: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/receiving', label: '入庫' },
    { to: '/master', label: '主檔瀏覽' },
    { to: '/audit', label: '操作紀錄' },
  ],
  warehouse: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/receiving', label: '入庫' },
  ],
  purchasing: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/master', label: '主檔瀏覽' },
  ],
  sales: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/master', label: '主檔瀏覽' },
  ],
  accounting: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/master', label: '主檔瀏覽' },
    { to: '/audit', label: '操作紀錄' },
  ],
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const nav = NAV_BY_ROLE[user?.role] || [{ to: '/stock', label: '庫存查詢' }]

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <>
      <header className="app-header">
        <h1>庫存管理系統</h1>
        <nav>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <span className="who">
          {user?.name}（{ROLE_LABEL[user?.role] || user?.role}）
        </span>
        <button onClick={() => navigate('/change-password')}>更改密碼</button>
        <button onClick={handleLogout}>登出</button>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
