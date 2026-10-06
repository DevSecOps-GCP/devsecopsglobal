import { Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { RequireAuth } from './auth'
import { useAuth } from './useAuth'
import Admin from './pages/Admin'
import Landing from './pages/Landing'
import Library from './pages/Library'
import { Login, Signup } from './pages/AuthForms'
import Watch from './pages/Watch'

function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const onLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <header className="header">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden>◆</span>
        DevSecOps <strong>Global</strong>
      </Link>
      <nav className="nav">
        {user ? (
          <>
            <NavLink to="/" end>Library</NavLink>
            {user.is_admin && <NavLink to="/admin">Admin</NavLink>}
            <span className="nav-user" title={user.email}>{user.full_name}</span>
            <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
          </>
        ) : (
          <>
            <NavLink to="/login">Log in</NavLink>
            <Link to="/signup" className="btn btn-primary">Sign up</Link>
          </>
        )}
      </nav>
    </header>
  )
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return <div className="spinner" aria-label="Loading" />
  return user ? <Library /> : <Landing />
}

export default function App() {
  return (
    <div className="app">
      <Header />
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/videos/:id" element={<RequireAuth><Watch /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth admin><Admin /></RequireAuth>} />
          <Route path="*" element={<div className="empty"><h2>Page not found</h2><Link to="/">Go home</Link></div>} />
        </Routes>
      </main>
      <footer className="footer">DevSecOps Global · running on GKE</footer>
    </div>
  )
}
