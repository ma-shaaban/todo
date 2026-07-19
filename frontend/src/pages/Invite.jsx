import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'

export default function Invite() {
  const { code } = useParams()
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api(`/api/invites/${code}`)
      .then(setPreview)
      .catch((e) => setError(e.status === 404 ? 'This invite link is not valid.' : e.message))
  }, [code])

  const join = async () => {
    setBusy(true)
    setError('')
    try {
      const res = await api(`/api/invites/${code}/accept`, { method: 'POST' })
      navigate(`/spaces/${res.space_id}`, { replace: true })
    } catch (e) {
      setError(e.status === 410 ? 'This invite link has expired or was revoked.' : e.message)
      setBusy(false)
    }
  }

  const next = encodeURIComponent(`/invite/${code}`)

  return (
    <div className="authpage">
      <h1>Todo</h1>
      {error && <p className="sub error">{error}</p>}
      {!error && !preview && <p className="sub">Checking your invite…</p>}
      {preview && !preview.valid && (
        <p className="sub error">This invite link has expired or was revoked. Ask for a new one.</p>
      )}
      {preview?.valid && (
        <>
          <p className="sub">
            <strong>{preview.inviter_name}</strong> invited you to join{' '}
            <strong>{preview.space_name}</strong> — a shared todo space.
          </p>
          {loading ? null : user ? (
            <button className="btn block" disabled={busy} onClick={join}>
              Join {preview.space_name}
            </button>
          ) : (
            <>
              <Link className="btn block" to={`/signup?next=${next}`}>
                Create an account to join
              </Link>
              <p className="alt">
                Have an account? <Link to={`/login?next=${next}`}>Sign in</Link>
              </p>
            </>
          )}
        </>
      )}
    </div>
  )
}
