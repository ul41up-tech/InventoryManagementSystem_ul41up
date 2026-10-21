import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import AuditLogs from './pages/AuditLogs.jsx'
import ChangePassword from './pages/ChangePassword.jsx'
import Login from './pages/Login.jsx'
import MasterData from './pages/MasterData.jsx'
import Receiving from './pages/Receiving.jsx'
import StockQuery from './pages/StockQuery.jsx'
import { api } from './api.js'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="container muted">載入中…</div>
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }
  // 首次登入必須先改密，否則不得進入其他頁面
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  return children
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    api
      .me()
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  // Session 過期時導回登入頁
  useEffect(() => {
    const handler = () => {
      setUser(null)
      if (location.pathname !== '/login') {
        navigate('/login', { replace: true })
      }
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [navigate, location.pathname])

  const value = {
    user,
    setUser,
    logout: async () => {
      await api.logout().catch(() => {})
      setUser(null)
    },
  }

  return (
    <AuthContext.Provider value={value}>
      <ErrorBoundary>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="stock" element={<StockQuery />} />
            <Route path="receiving" element={<Receiving />} />
            <Route path="master" element={<MasterData />} />
            <Route path="audit" element={<AuditLogs />} />
            <Route path="change-password" element={<ChangePassword />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </AuthContext.Provider>
  )
}
