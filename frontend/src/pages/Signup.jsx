import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../auth.jsx'

export default function Signup() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const next = params.get('next') || '/'

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await signup(email, password, name)
      navigate(next, { replace: true })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="authpage">
      <h1>Create account</h1>
      <p className="sub">A minute from now you'll have a shared todo list</p>
      <form onSubmit={submit}>
        <div className="field">
          <label>Your name</label>
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Ana" />
        </div>
        <div className="field">
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
          />
        </div>
        {error && <div className="error">{error}</div>}
        <button className="btn block" disabled={busy}>
          Create account
        </button>
      </form>
      <p className="alt">
        Already have one? <Link to={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link>
      </p>
    </div>
  )
}
