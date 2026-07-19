import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import TodoEditor from '../components/TodoEditor.jsx'
import TodoItem from '../components/TodoItem.jsx'
import { timeAgo } from '../format.js'

function activityLine(e) {
  const who = e.actor?.display_name || 'Someone'
  const t = e.data?.title
  switch (e.type) {
    case 'todo_created':
      return `${who} added “${t}”`
    case 'todo_completed':
      return `${who} completed “${t}”`
    case 'todo_reopened':
      return `${who} reopened “${t}”`
    case 'todo_deleted':
      return `${who} deleted “${t}”`
    case 'todo_assigned':
      return `${who} assigned “${t}” to ${e.data?.assignee_name}`
    case 'member_joined':
      return `${who} joined`
    case 'member_left':
      return `${who} left`
    case 'member_removed':
      return `${who} removed ${e.data?.removed_name}`
    case 'space_renamed':
      return `${who} renamed the space to “${e.data?.name}”`
    default:
      return who
  }
}

export default function Space() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [space, setSpace] = useState(null)
  const [todos, setTodos] = useState([])
  const [done, setDone] = useState(null)
  const [tab, setTab] = useState('todos')
  const [activity, setActivity] = useState(null)
  const [quick, setQuick] = useState('')
  const [editing, setEditing] = useState(undefined) // undefined=closed, null=new, todo=edit
  const [invite, setInvite] = useState(null)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    api(`/api/spaces/${id}`)
      .then(setSpace)
      .catch((e) => (e.status === 404 ? setNotFound(true) : setError(e.message)))
    api(`/api/spaces/${id}/todos`)
      .then((d) => setTodos(d.items))
      .catch(() => {})
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  // Deep link ?todo=<id> (from notifications) opens the editor.
  useEffect(() => {
    const target = params.get('todo')
    if (target && todos.length) {
      const t = todos.find((x) => x.id === target)
      if (t) {
        setEditing(t)
        setParams({}, { replace: true })
      }
    }
  }, [params, todos])

  const loadDone = () =>
    api(`/api/spaces/${id}/todos?status=done`).then((d) => setDone(d.items)).catch(() => {})

  const quickAdd = async (e) => {
    e.preventDefault()
    if (!quick.trim()) return
    try {
      const todo = await api(`/api/spaces/${id}/todos`, {
        method: 'POST',
        body: { title: quick },
      })
      setTodos((t) => [...t, todo])
      setQuick('')
    } catch (err) {
      setError(err.message)
    }
  }

  const toggle = async (todo) => {
    try {
      if (todo.completed_at) {
        const reopened = await api(`/api/todos/${todo.id}/reopen`, { method: 'POST' })
        setDone((d) => (d || []).filter((t) => t.id !== todo.id))
        setTodos((t) => [...t, reopened])
      } else {
        const res = await api(`/api/todos/${todo.id}/complete`, { method: 'POST' })
        setTodos((t) => {
          const rest = t.filter((x) => x.id !== todo.id)
          return res.next ? [...rest, res.next] : rest
        })
        if (done !== null) setDone((d) => [res.completed, ...(d || [])])
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const onSaved = (saved) => {
    setTodos((t) => {
      const idx = t.findIndex((x) => x.id === saved.id)
      if (idx >= 0) {
        const copy = [...t]
        copy[idx] = saved
        return copy
      }
      return [...t, saved]
    })
    setEditing(undefined)
  }

  const createInvite = async () => {
    try {
      const inv = await api(`/api/spaces/${id}/invites`, { method: 'POST' })
      const url = `${window.location.origin}/invite/${inv.code}`
      setInvite(url)
      if (navigator.share) {
        navigator.share({ title: `Join ${space.name}`, url }).catch(() => {})
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).catch(() => {})
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const removeMember = async (member) => {
    const leaving = member.id === user.id
    if (!confirm(leaving ? 'Leave this space?' : `Remove ${member.display_name}?`)) return
    try {
      await api(`/api/spaces/${id}/members/${member.id}`, { method: 'DELETE' })
      if (leaving) navigate('/')
      else load()
    } catch (err) {
      setError(err.message)
    }
  }

  const deleteSpace = async () => {
    if (!confirm(`Delete "${space.name}" and all its todos?`)) return
    try {
      await api(`/api/spaces/${id}`, { method: 'DELETE' })
      navigate('/')
    } catch (err) {
      setError(err.message)
    }
  }

  if (notFound) {
    return (
      <>
        <header className="topbar">
          <Link className="back" to="/">‹</Link>
          <h1>Not found</h1>
        </header>
        <div className="empty">This space doesn't exist or you're not a member.</div>
      </>
    )
  }
  if (!space) return <div className="empty">Loading…</div>

  const members = space.members
  const open = [...todos].filter((t) => !t.completed_at)

  return (
    <>
      <header className="topbar">
        <Link className="back" to="/">‹</Link>
        <h1>{space.name}</h1>
      </header>

      <div className="tabs">
        <button className={tab === 'todos' ? 'active' : ''} onClick={() => setTab('todos')}>
          Todos
        </button>
        <button
          className={tab === 'members' ? 'active' : ''}
          onClick={() => setTab('members')}
        >
          Members ({members.length})
        </button>
        <button
          className={tab === 'activity' ? 'active' : ''}
          onClick={() => {
            setTab('activity')
            api(`/api/spaces/${id}/activity`)
              .then((d) => setActivity(d.items))
              .catch(() => setActivity([]))
          }}
        >
          Activity
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {tab === 'todos' && (
        <>
          <form className="quickadd" onSubmit={quickAdd}>
            <input
              value={quick}
              onChange={(e) => setQuick(e.target.value)}
              placeholder="Add a todo…"
            />
            <button className="btn" disabled={!quick.trim()}>
              Add
            </button>
          </form>
          {open.length === 0 && <div className="empty">Nothing to do here 🎉</div>}
          {open.map((t) => (
            <TodoItem key={t.id} todo={t} onToggle={toggle} onOpen={setEditing} />
          ))}
          <p className="hint">
            <button className="linklike" onClick={() => setEditing(null)}>
              + Todo with details
            </button>
            {' · '}
            {done === null ? (
              <button className="linklike" onClick={loadDone}>
                Show done
              </button>
            ) : (
              <button className="linklike" onClick={() => setDone(null)}>
                Hide done
              </button>
            )}
          </p>
          {done !== null &&
            done.map((t) => <TodoItem key={t.id} todo={t} onToggle={toggle} onOpen={setEditing} />)}
        </>
      )}

      {tab === 'members' && (
        <>
          <button className="btn block" onClick={createInvite}>
            Invite with a link
          </button>
          {invite && (
            <div className="invite-box">
              Share this link (valid 7 days): <br />
              <strong>{invite}</strong>
              <br />
              <button
                className="linklike"
                onClick={() => navigator.clipboard?.writeText(invite)}
              >
                Copy
              </button>
            </div>
          )}
          <div style={{ height: 12 }} />
          {members.map((m) => (
            <div className="member" key={m.id}>
              <span className="avatar">{m.display_name.slice(0, 2).toUpperCase()}</span>
              <span className="name">
                {m.display_name}
                {m.id === user.id ? ' (you)' : ''}
              </span>
              <span className="role">{m.role}</span>
              {m.role !== 'owner' && (space.my_role === 'owner' || m.id === user.id) && (
                <button className="linklike" onClick={() => removeMember(m)}>
                  {m.id === user.id ? 'Leave' : 'Remove'}
                </button>
              )}
            </div>
          ))}
          {space.my_role === 'owner' && (
            <p className="hint">
              <button className="linklike" style={{ color: 'var(--danger)' }} onClick={deleteSpace}>
                Delete this space
              </button>
            </p>
          )}
        </>
      )}

      {tab === 'activity' &&
        (activity === null ? (
          <div className="empty">Loading…</div>
        ) : activity.length === 0 ? (
          <div className="empty">No activity yet.</div>
        ) : (
          activity.map((e) => (
            <div className="card" key={e.id}>
              {activityLine(e)}
              <div className="meta">{timeAgo(e.created_at)}</div>
            </div>
          ))
        ))}

      {editing !== undefined && (
        <TodoEditor
          spaceId={id}
          todo={editing}
          members={members}
          onSaved={onSaved}
          onDeleted={(t) => {
            setTodos((list) => list.filter((x) => x.id !== t.id))
            setDone((list) => (list ? list.filter((x) => x.id !== t.id) : list))
            setEditing(undefined)
          }}
          onClose={() => setEditing(undefined)}
        />
      )}
    </>
  )
}
