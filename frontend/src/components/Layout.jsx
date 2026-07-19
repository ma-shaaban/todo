import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { api } from '../api.js'
import { useLiveRefresh } from '../live.js'

export default function Layout() {
  const [unread, setUnread] = useState(0)

  const poll = () =>
    api('/api/notifications?unread=1&limit=1')
      .then((d) => setUnread(d.unread_count))
      .catch(() => {})

  useEffect(() => {
    poll()
    window.addEventListener('notifications:changed', poll)
    return () => window.removeEventListener('notifications:changed', poll)
  }, [])
  useLiveRefresh(poll, 30000)

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
