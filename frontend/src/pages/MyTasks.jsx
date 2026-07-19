import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../api.js'
import TodoItem from '../components/TodoItem.jsx'

export default function MyTasks() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = () =>
    api('/api/me/todos')
      .then((d) => setItems(d.items))
      .catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const toggle = async (todo) => {
    try {
      await api(`/api/todos/${todo.id}/complete`, { method: 'POST' })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <header className="topbar">
        <h1>My Tasks</h1>
      </header>
      {error && <div className="error">{error}</div>}
      {items === null ? (
        <div className="empty">Loading…</div>
      ) : items.length === 0 ? (
        <div className="empty">Nothing on your plate. Enjoy it!</div>
      ) : (
        items.map((t) => (
          <TodoItem
            key={t.id}
            todo={t}
            spaceName={t.space?.name}
            onToggle={toggle}
            onOpen={() => navigate(`/spaces/${t.space_id}?todo=${t.id}`)}
          />
        ))
      )}
    </>
  )
}
