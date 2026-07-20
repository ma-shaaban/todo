import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import TodoEditor from '../components/TodoEditor.jsx'
import TodoItem from '../components/TodoItem.jsx'
import { dueLabel, timeAgo } from '../format.js'
import { useLiveRefresh } from '../live.js'

function activityLine(e) {
  const who = e.actor?.display_name || 'Someone'
  const t = e.data?.title
  switch (e.type) {
    case 'todo_created':
      return `${who} added “${t}”`
    case 'todo_completed':
      return `${who} completed “${t}”`
    case 'todo_checked':
      return `${who} checked off “${t}”`
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
  const [quickTodo, setQuickTodo] = useState(null) // notification deep-link panel
  const [invite, setInvite] = useState(null)
  const [auto, setAuto] = useState({ city: '', country: '', method: '' })
  const [autoBusy, setAutoBusy] = useState(false)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)

  // Seed the automation edit form from the saved config — keyed on the
  // config VALUES so the 15s live refresh (new object, same content)
  // doesn't stomp in-progress edits.
  const autoCfg = space?.automation?.config
  const autoKey = autoCfg ? `${autoCfg.city}|${autoCfg.country}|${autoCfg.method}` : ''
  useEffect(() => {
    if (autoCfg) {
      setAuto({
        city: autoCfg.city || '',
        country: autoCfg.country || '',
        method: autoCfg.method == null ? '' : String(autoCfg.method),
      })
    }
  }, [autoKey])

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

  // Other members' changes appear without a manual refresh: silently refetch
  // whatever this page is showing (404 still flips to not-found — the space
  // may have been deleted under us).
  const showingDone = done !== null
  const refresh = useCallback(() => {
    api(`/api/spaces/${id}`)
      .then(setSpace)
      .catch((e) => e.status === 404 && setNotFound(true))
    api(`/api/spaces/${id}/todos`)
      .then((d) => setTodos(d.items))
      .catch(() => {})
    if (showingDone) loadDone()
    if (tab === 'activity') loadActivity()
  }, [id, tab, showingDone])
  useLiveRefresh(refresh)

  // Deep link ?todo=<id> (from notifications): a quick-action panel —
  // people arriving from a reminder want "mark done", not the edit form.
  useEffect(() => {
    const target = params.get('todo')
    if (target && todos.length) {
      const t = todos.find((x) => x.id === target)
      if (t) {
        setQuickTodo(t)
        setParams({}, { replace: true })
      }
    }
  }, [params, todos])

  const loadDone = () =>
    api(`/api/spaces/${id}/todos?status=done`).then((d) => setDone(d.items)).catch(() => {})

  const loadActivity = () =>
    api(`/api/spaces/${id}/activity`)
      .then((d) => setActivity(d.items))
      .catch(() => setActivity((a) => a ?? []))

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
      } else if (
        todo.completion_mode === 'each' &&
        todo.assignees?.find((a) => a.id === user.id)?.completed_at
      ) {
        // Group todo, my box already checked → uncheck just my box.
        const updated = await api(`/api/todos/${todo.id}/reopen`, { method: 'POST' })
        setTodos((t) => t.map((x) => (x.id === todo.id ? updated : x)))
      } else {
        const res = await api(`/api/todos/${todo.id}/complete`, { method: 'POST' })
        if (res.completed.completed_at) {
          setTodos((t) => {
            const rest = t.filter((x) => x.id !== todo.id)
            return res.next ? [...rest, res.next] : rest
          })
          if (done !== null) setDone((d) => [res.completed, ...(d || [])])
        } else {
          // Group todo still waiting on others — stays open, my box checked.
          setTodos((t) => t.map((x) => (x.id === todo.id ? res.completed : x)))
        }
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

  const saveAutomation = async (e) => {
    e.preventDefault()
    setAutoBusy(true)
    try {
      await api(`/api/spaces/${id}/automation`, {
        method: 'PUT',
        body: {
          type: space.automation.type,
          config: {
            city: auto.city.trim(),
            country: auto.country.trim(),
            method: auto.method === '' ? null : Number(auto.method),
          },
        },
      })
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setAutoBusy(false)
    }
  }

  const disableAutomation = async () => {
    if (
      !confirm(
        'Turn off prayer times? Existing prayer todos stay. To turn it back on later, create a new space from the Prayer template.',
      )
    )
      return
    try {
      await api(`/api/spaces/${id}/automation`, { method: 'DELETE' })
      load()
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
            loadActivity()
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
          {/* Only spaces born from a template (or with the automation set
              via API) show this card — blank spaces carry no prayer UI. */}
          {space.automation && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>🕌 Prayer times</h3>
              <div className="meta">
                The five daily prayers appear automatically for everyone to check off, with
                reminders 15 minutes before and at prayer time. Missed prayers stay a week.
              </div>
              {space.my_role === 'owner' ? (
                <form onSubmit={saveAutomation}>
                  <div className="row" style={{ marginTop: 8 }}>
                    <div className="field">
                      <label>City</label>
                      <input
                        value={auto.city}
                        onChange={(e) => setAuto({ ...auto, city: e.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Country</label>
                      <input
                        value={auto.country}
                        onChange={(e) => setAuto({ ...auto, country: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="field">
                    <label>Calculation method</label>
                    <select
                      value={auto.method}
                      onChange={(e) => setAuto({ ...auto, method: e.target.value })}
                    >
                      {/* The API accepts methods 0–23; keep an off-list value
                          visible instead of a blank select that would get
                          silently replaced on the next save. */}
                      {!['5', '4', '3', '2', '1', '8', '13', ''].includes(auto.method) && (
                        <option value={auto.method}>Method {auto.method}</option>
                      )}
                      <option value="5">Egyptian General Authority</option>
                      <option value="4">Umm Al-Qura (Makkah)</option>
                      <option value="3">Muslim World League</option>
                      <option value="2">ISNA (North America)</option>
                      <option value="1">University of Karachi</option>
                      <option value="8">Gulf Region</option>
                      <option value="13">Diyanet (Turkey)</option>
                      <option value="">Automatic</option>
                    </select>
                  </div>
                  <div className="actions" style={{ justifyContent: 'flex-start' }}>
                    <button
                      className="btn secondary"
                      disabled={autoBusy || !auto.city.trim() || !auto.country.trim()}
                    >
                      {autoBusy ? 'Saving…' : 'Save changes'}
                    </button>
                    <button
                      className="linklike"
                      type="button"
                      style={{ color: 'var(--danger)' }}
                      onClick={disableAutomation}
                    >
                      Turn off
                    </button>
                  </div>
                </form>
              ) : (
                <div className="meta">
                  {space.automation.config.city}, {space.automation.config.country}
                </div>
              )}
            </div>
          )}
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

      {quickTodo &&
        (() => {
          const isEach = quickTodo.completion_mode === 'each'
          const myRow = isEach ? quickTodo.assignees?.find((a) => a.id === user.id) : null
          const canAct = !isEach || Boolean(myRow)
          return (
            <div
              className="sheet-backdrop"
              onClick={(e) => e.target === e.currentTarget && setQuickTodo(null)}
            >
              <div className="sheet">
                <h2>{quickTodo.title}</h2>
                {quickTodo.due_at && <p className="hint">Due {dueLabel(quickTodo.due_at)}</p>}
                {quickTodo.notes && <p className="hint">{quickTodo.notes}</p>}
                {isEach && (
                  <p className="hint">
                    {quickTodo.assignees
                      ?.map((a) => `${a.completed_at ? '✅' : '⭕'} ${a.display_name}`)
                      .join('   ')}
                  </p>
                )}
                <div className="actions">
                  <button className="btn secondary" onClick={() => setQuickTodo(null)}>
                    Close
                  </button>
                  <button
                    className="btn secondary"
                    onClick={() => {
                      setEditing(quickTodo)
                      setQuickTodo(null)
                    }}
                  >
                    Edit details
                  </button>
                  {canAct && (
                    <button
                      className="btn"
                      onClick={async () => {
                        await toggle(quickTodo)
                        setQuickTodo(null)
                      }}
                    >
                      {isEach
                        ? myRow?.completed_at
                          ? 'Uncheck my box'
                          : '✓ Check off my box'
                        : '✓ Mark done'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })()}

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
