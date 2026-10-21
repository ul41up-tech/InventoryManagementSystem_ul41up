import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import MasterData from './pages/MasterData.jsx'
import StockQuery from './pages/StockQuery.jsx'
import { api } from './api.js'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="container muted">載入中…</div>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return children
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .me()
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

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
          <Route path="master" element={<MasterData />} />
        </Route>
      </Routes>
    </AuthContext.Provider>
  )
}
