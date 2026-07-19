import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { api } from '../api.js'

export default function Layout() {
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let timer
    const poll = () =>
      api('/api/notifications?unread=1&limit=1')
        .then((d) => setUnread(d.unread_count))
        .catch(() => {})
    poll()
    timer = setInterval(poll, 60000)
    const onVisible = () => document.visibilityState === 'visible' && poll()
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('notifications:changed', poll)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('notifications:changed', poll)
    }
  }, [])

  const tab = ({ isActive }) => (isActive ? 'active' : '')
  return (
    <div className="app">
      <Outlet />
      <nav className="tabbar">
        <NavLink to="/" end className={tab}>
          <span className="icon">🏠</span>Spaces
        </NavLink>
        <NavLink to="/me/todos" className={tab}>
          <span className="icon">☑️</span>My Tasks
        </NavLink>
        <NavLink to="/notifications" className={tab}>
          <span className="icon">🔔</span>Alerts
          {unread > 0 && <span className="badge">{unread > 99 ? '99+' : unread}</span>}
        </NavLink>
        <NavLink to="/settings" className={tab}>
          <span className="icon">⚙️</span>Settings
        </NavLink>
      </nav>
    </div>
  )
}
