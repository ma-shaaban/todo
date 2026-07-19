import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api.js'
import { useLiveRefresh } from '../live.js'

export default function Spaces() {
  const [spaces, setSpaces] = useState(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const load = (silent) =>
    api('/api/spaces')
      .then((d) => setSpaces(d.items))
      .catch((e) => !silent && setError(e.message))

  useEffect(() => {
    load()
  }, [])
  useLiveRefresh(() => load(true))

  const create = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/api/spaces', { method: 'POST', body: { name } })
      setName('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <header className="topbar">
        <h1>Spaces</h1>
      </header>
      <form className="quickadd" onSubmit={create}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New space (e.g. Family)"
        />
        <button className="btn" disabled={!name.trim()}>
          Create
        </button>
      </form>
      {error && <div className="error">{error}</div>}
      {spaces === null ? (
        <div className="empty">Loading…</div>
      ) : spaces.length === 0 ? (
        <div className="empty">
          No spaces yet. Create one above — then invite someone from inside it.
        </div>
      ) : (
        spaces.map((s) => (
          <Link key={s.id} to={`/spaces/${s.id}`} className="card">
            <h3>{s.name}</h3>
            <div className="meta">
              {s.todo_count} open · {s.member_count} member{s.member_count === 1 ? '' : 's'}
              {s.my_role === 'owner' ? ' · yours' : ''}
            </div>
          </Link>
        ))
      )}
    </>
  )
}
