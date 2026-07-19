import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, authEvents } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api('/api/auth/me')
      .then((me) => !cancelled && setUser(me))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false))
    const onRequired = () => setUser(null)
    authEvents.addEventListener('auth:required', onRequired)
    return () => {
      cancelled = true
      authEvents.removeEventListener('auth:required', onRequired)
    }
  }, [])

  // Keep the account's timezone current (used for docs/UX only — all times
  // are stored UTC and rendered locally).
  useEffect(() => {
    if (!user) return
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (tz && user.timezone !== tz) {
      api('/api/auth/me', { method: 'PATCH', body: { timezone: tz } }).catch(() => {})
    }
  }, [user?.id])

  const login = useCallback(async (email, password) => {
    const me = await api('/api/auth/login', { method: 'POST', body: { email, password } })
    setUser(me)
    return me
  }, [])

  const signup = useCallback(async (email, password, displayName) => {
    const me = await api('/api/auth/signup', {
      method: 'POST',
      body: { email, password, display_name: displayName },
    })
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    await api('/api/auth/logout', { method: 'POST' }).catch(() => {})
    setUser(null)
  }, [])

  const update = useCallback(async (fields) => {
    const me = await api('/api/auth/me', { method: 'PATCH', body: fields })
    setUser(me)
    return me
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, update }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <div className="splash">Todo</div>
  }
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children
}
