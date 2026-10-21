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
    { to: '/transfers', label: '調貨' },
    { to: '/master', label: '主檔瀏覽' },
    { to: '/audit', label: '操作紀錄' },
  ],
  warehouse: [
    { to: '/stock', label: '庫存查詢' },
    { to: '/receiving', label: '入庫' },
    { to: '/transfers', label: '調貨' },
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

const PAGE_TITLE = {
  '/stock': '庫存查詢',
  '/receiving': '入庫作業',
  '/transfers': '移轉與調貨',
  '/master': '主檔瀏覽',
  '/audit': '操作紀錄',
  '/change-password': '更改密碼',
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
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo">庫</div>
          <div>
            <div className="title">庫存管理系統</div>
            <div className="subtitle">AILearn INVENTORY</div>
          </div>
        </div>

        <nav>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              <span className="dot" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-user">
          <div className="who">
            <strong>{user?.name}</strong>
            {ROLE_LABEL[user?.role] || user?.role}
          </div>
          <div className="sidebar-actions">
            <button className="ghost sm" onClick={() => navigate('/change-password')}>
              更改密碼
            </button>
            <button className="ghost sm" onClick={handleLogout}>
              登出
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <h1>{PAGE_TITLE[window.location.pathname] || '庫存管理系統'}</h1>
          <span className="crumb">多倉進銷存管理</span>
          <span className="spacer" />
          <span className="crumb">
            {user?.name}（{ROLE_LABEL[user?.role] || user?.role}）
          </span>
        </header>
        <main className="container">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
