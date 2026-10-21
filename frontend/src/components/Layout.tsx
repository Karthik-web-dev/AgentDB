import { NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { SWATCH, THEMES, useApp } from '../state'

const links = [
  ['/dashboard', 'Dashboard'], ['/agents', 'Agents'], ['/tasks', 'Tasks'], ['/runs', 'Runs'],
  ['/logs', 'Log Explorer'], ['/metrics', 'Metrics'], ['/alerts', 'Alerts'], ['/audit', 'Audit Trail'], ['/themes', 'Themes'], ['/settings', 'Settings'],
]

export default function Layout() {
  const { user, sessionChecked, theme, setTheme, logout } = useApp()
  const loc = useLocation()
  const nav = useNavigate()
  if (!sessionChecked) return <div className="main mono">Checking your session…</div>
  if (!user) return <Navigate to="/" replace />
  return (
    <div className="shell">
      <aside className="side">
        <div className="logo">AGENT/DB</div>
        {links.map(([to, label], i) => (
          <motion.div key={to} initial={{ x: -40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.04 }}>
            <NavLink to={to} className={({ isActive }) => 'nav' + (isActive ? ' active' : '')}>{label}</NavLink>
          </motion.div>
        ))}
        <div style={{ flex: 1 }} />
        <button className="btn ghost" onClick={() => { logout(); nav('/') }}>Log out</button>
      </aside>
      <div>
        <div className="top">
          <span className="mono">👋 {user.full_name} · {user.email}</span>
          <div className="row">
            <span style={{ fontWeight: 700, fontSize: 12 }}>THEME</span>
            {THEMES.slice(0, 7).map(t => (
              <div key={t} title={t} className={'swatch' + (t === theme ? ' on' : '')} style={{ background: SWATCH[t], outline: t === theme ? '3px solid var(--a2)' : 'none' }} onClick={() => setTheme(t)} />
            ))}
            <NavLink to="/themes" className="btn ghost" style={{ padding: '2px 10px', textDecoration: 'none', fontSize: 12 }}>All {THEMES.length} →</NavLink>
          </div>
        </div>
        <main className="main">
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname} initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }} transition={{ duration: 0.2 }}>
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
