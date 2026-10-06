import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../useAuth'

function useAfterLogin() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  return () => navigate(from, { replace: true })
}

function useSubmit(action: () => Promise<void>, onSuccess: () => void) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await action()
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Network error, please retry')
    } finally {
      setBusy(false)
    }
  }
  return { error, busy, onSubmit }
}

export function Login() {
  const { user, login } = useAuth()
  const done = useAfterLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { error, busy, onSubmit } = useSubmit(() => login(email, password), done)

  if (user) return <Navigate to="/" replace />
  return (
    <form className="card auth-card" onSubmit={onSubmit}>
      <h1>Welcome back</h1>
      <label>
        Email
        <input type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
      <p className="muted">No account yet? <Link to="/signup">Sign up</Link></p>
    </form>
  )
}

export function Signup() {
  const { user, signup } = useAuth()
  const done = useAfterLogin()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { error, busy, onSubmit } = useSubmit(() => signup(email, fullName, password), done)

  if (user) return <Navigate to="/" replace />
  return (
    <form className="card auth-card" onSubmit={onSubmit}>
      <h1>Create your account</h1>
      <label>
        Full name
        <input autoComplete="name" required maxLength={120} value={fullName}
          onChange={(e) => setFullName(e.target.value)} />
      </label>
      <label>
        Email
        <input type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input type="password" autoComplete="new-password" required minLength={10} maxLength={128}
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <small className="muted">At least 10 characters.</small>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Sign up'}</button>
      <p className="muted">Already registered? <Link to="/login">Log in</Link></p>
    </form>
  )
}
