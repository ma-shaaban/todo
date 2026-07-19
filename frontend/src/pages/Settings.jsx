import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../auth.jsx'
import { disablePush, enablePush, getPushState, isIosNotInstalled } from '../push.js'

export default function Settings() {
  const { user, update, logout } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(user?.display_name || '')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [push, setPush] = useState('loading') // loading|unsupported|denied|on|off|ios-install
  const [pushError, setPushError] = useState('')

  useEffect(() => {
    if (isIosNotInstalled()) setPush('ios-install')
    else getPushState().then(setPush)
  }, [])

  const togglePush = async () => {
    setPushError('')
    const was = push
    try {
      if (was === 'on') {
        setPush('off')
        await disablePush()
      } else {
        await enablePush()
        setPush('on')
      }
    } catch (e) {
      setPush(was)
      setPushError(e.message)
    }
  }

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
        {push === 'ios-install' ? (
          <p className="meta">
            On iPhone/iPad: first add this app to your Home Screen (Share button →{' '}
            <strong>Add to Home Screen</strong>), then open it from there and flip this switch —
            that's an Apple requirement for notifications.
          </p>
        ) : push === 'unsupported' ? (
          <p className="meta">This browser doesn't support push notifications.</p>
        ) : push === 'denied' ? (
          <p className="meta">
            Notifications are blocked for this site in your browser settings — allow them there,
            then come back.
          </p>
        ) : (
          <>
            <p className="meta">
              Get reminders and space activity even when the app is closed.
            </p>
            <button
              className={`btn ${push === 'on' ? 'secondary' : ''}`}
              disabled={push === 'loading'}
              onClick={togglePush}
            >
              {push === 'on' ? 'Turn off notifications' : 'Turn on notifications'}
            </button>
          </>
        )}
        {pushError && <div className="error">{pushError}</div>}
      </div>
      <button className="btn danger block" onClick={signOut}>
        Sign out
      </button>
    </>
  )
}
