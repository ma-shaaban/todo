import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../auth.jsx'

export default function Settings() {
  const { user, update, logout } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(user?.display_name || '')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const save = async (e) => {
    e.preventDefault()
    setError('')
    setSaved(false)
    try {
      await update({ display_name: name })
      setSaved(true)
    } catch (err) {
      setError(err.message)
    }
  }

  const signOut = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <>
      <header className="topbar">
        <h1>Settings</h1>
      </header>
      <div className="card">
        <form onSubmit={save}>
          <div className="field">
            <label>Your name (what others see)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label>Email</label>
            <input value={user?.email || ''} disabled />
          </div>
          {error && <div className="error">{error}</div>}
          {saved && <div className="hint">Saved ✓</div>}
          <button className="btn" disabled={!name.trim()}>
            Save
          </button>
        </form>
      </div>
      <div className="card">
        <h3>Notifications on this device</h3>
        <p className="meta">
          Phone notifications arrive with the app install feature (coming in the next update) —
          your in-app Alerts already work.
        </p>
      </div>
      <button className="btn danger block" onClick={signOut}>
        Sign out
      </button>
    </>
  )
}
