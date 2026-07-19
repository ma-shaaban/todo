import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../api.js'
import { timeAgo } from '../format.js'
import { useLiveRefresh } from '../live.js'

const ICONS = { reminder: '⏰', assigned: '👉', completed: '✅', joined: '👋' }

export default function Notifications() {
  const [data, setData] = useState(null)
  const navigate = useNavigate()

  const load = () => api('/api/notifications').then(setData).catch(() => {})

  useEffect(() => {
    load()
  }, [])
  useLiveRefresh(load)

  const open = async (n) => {
    if (!n.read_at) {
      await api(`/api/notifications/${n.id}/read`, { method: 'POST' }).catch(() => {})
      window.dispatchEvent(new Event('notifications:changed'))
    }
    navigate(n.url || '/')
  }

  const readAll = async () => {
    await api('/api/notifications/read-all', { method: 'POST' }).catch(() => {})
    window.dispatchEvent(new Event('notifications:changed'))
    load()
  }

  return (
    <>
      <header className="topbar">
        <h1>Alerts</h1>
        {data?.unread_count > 0 && (
          <button className="linklike" onClick={readAll}>
            Mark all read
          </button>
        )}
      </header>
      {data === null ? (
        <div className="empty">Loading…</div>
      ) : data.items.length === 0 ? (
        <div className="empty">Nothing yet. Reminders and space activity land here.</div>
      ) : (
        data.items.map((n) => (
          <div
            key={n.id}
            className={`notification ${n.read_at ? '' : 'unread'}`}
            onClick={() => open(n)}
          >
            <span className="icon">{ICONS[n.type] || '🔔'}</span>
            <div className="body">
              <div className="title">{n.title}</div>
              <div className="meta">{timeAgo(n.created_at)}</div>
            </div>
          </div>
        ))
      )}
    </>
  )
}
