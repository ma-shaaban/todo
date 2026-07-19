import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../api.js'
import { useLiveRefresh } from '../live.js'

export default function Spaces() {
  const [spaces, setSpaces] = useState(null)
  const [name, setName] = useState('')
  const [templates, setTemplates] = useState([])
  const [tpl, setTpl] = useState(null) // template being configured, or null
  const [tplForm, setTplForm] = useState({ name: '', config: {} })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = (silent) =>
    api('/api/spaces')
      .then((d) => setSpaces(d.items))
      .catch((e) => !silent && setError(e.message))

  const loadTemplates = () =>
    api('/api/space-templates')
      .then((d) => setTemplates(d.items))
      .catch(() => {})

  useEffect(() => {
    load()
    loadTemplates()
  }, [])
  useLiveRefresh(() => {
    load(true)
    // Self-heal a failed first fetch (e.g. flaky network on PWA resume) —
    // otherwise the template section silently never appears.
    if (templates.length === 0) loadTemplates()
  })

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

  const openTemplate = (t) => {
    setError('')
    setTpl(t)
    setTplForm({
      name: t.default_space_name || t.name,
      config: Object.fromEntries(t.config_fields.map((f) => [f.key, f.default])),
    })
  }

  const setCfg = (key, value) =>
    setTplForm((f) => ({ ...f, config: { ...f.config, [key]: value } }))

  const createFromTemplate = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const space = await api('/api/spaces', {
        method: 'POST',
        body: { name: tplForm.name, template: tpl.key, config: tplForm.config },
      })
      navigate(`/spaces/${space.id}`)
    } catch (err) {
      setError(err.message)
      setBusy(false)
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
      {error && !tpl && <div className="error">{error}</div>}
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

      {templates.length > 0 && (
        <>
          <p className="hint" style={{ marginTop: 20 }}>
            Or start from a template:
          </p>
          {templates.map((t) => (
            <button key={t.key} className="card tpl" onClick={() => openTemplate(t)}>
              <h3>
                {t.icon} {t.name}
              </h3>
              <div className="meta">{t.description}</div>
            </button>
          ))}
        </>
      )}

      {tpl && (
        <div
          className="sheet-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) {
              setTpl(null)
              setError('')
            }
          }}
        >
          <div className="sheet">
            <h2>
              {tpl.icon} {tpl.name}
            </h2>
            <p className="hint">{tpl.description}</p>
            <form onSubmit={createFromTemplate}>
              <div className="field">
                <label>Space name</label>
                <input
                  value={tplForm.name}
                  onChange={(e) => setTplForm((f) => ({ ...f, name: e.target.value }))}
                />
              </div>
              {tpl.config_fields.map((f) =>
                f.type === 'select' ? (
                  <div className="field" key={f.key}>
                    <label>{f.label}</label>
                    <select
                      value={JSON.stringify(tplForm.config[f.key] ?? null)}
                      onChange={(e) => setCfg(f.key, JSON.parse(e.target.value))}
                    >
                      {f.options.map((o) => (
                        <option key={String(o.value)} value={JSON.stringify(o.value)}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div className="field" key={f.key}>
                    <label>{f.label}</label>
                    <input
                      value={tplForm.config[f.key] ?? ''}
                      onChange={(e) => setCfg(f.key, e.target.value)}
                    />
                  </div>
                ),
              )}
              {error && <div className="error">{error}</div>}
              <div className="actions">
                <button
                  className="btn secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setTpl(null)
                    setError('')
                  }}
                >
                  Cancel
                </button>
                <button className="btn" disabled={busy || !tplForm.name.trim()}>
                  {busy ? 'Creating…' : 'Create space'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
