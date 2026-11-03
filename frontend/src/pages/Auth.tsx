import { FormEvent, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { SWATCH, THEMES, useApp } from '../state'

const ticker = 'AGENTS ★ TASKS ★ RUNS ★ EVENTS ★ LOGS ★ METRICS ★ ALERTS ★ AUDIT ★ '.repeat(6)

export default function Auth() {
  const { user, sessionChecked, login, register, theme, setTheme } = useApp()
  const nav = useNavigate()
  const [mode, setMode] = useState<'signup' | 'login'>('login')
  const [f, setF] = useState({ name: '', email: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (sessionChecked && user) return <Navigate to="/dashboard" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    if (mode === 'signup' && f.name.trim().length < 2) return setErr('Enter your full name.')
    if (!/^\S+@\S+\.\S+$/.test(f.email)) return setErr('Enter a valid email address.')
    if (f.password.length < 8) return setErr('Password must be at least 8 characters.')
    setBusy(true)
    try {
      if (mode === 'signup') await register(f.name.trim(), f.email.trim(), f.password)
      else await login(f.email.trim(), f.password)
      nav('/dashboard')
    } catch (error) {
      setErr(error instanceof Error ? error.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => { setErr(''); setF({ ...f, [k]: e.target.value }) }

  return (
    <>
      <div className="marquee"><span>{ticker}</span><span>{ticker}</span></div>
      <div className="auth">
        <div className="hero">
          <motion.span className="sticker mono" initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 3 }} transition={{ type: 'spring' }} style={{ alignSelf: 'flex-start' }}>
            AI-AGENT OBSERVABILITY
          </motion.span>
          <motion.h1 initial={{ x: -80, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ type: 'spring', stiffness: 120 }}>
            Agent<span style={{ background: 'var(--a1)', border: '4px solid var(--ink)', padding: '0 12px', color: '#111', display: 'inline-block', transform: 'rotate(-2deg)' }}>DB</span>
          </motion.h1>
          <p style={{ fontSize: 20, maxWidth: 520 }}>Structured logging, metrics, alerts and audit trails for AI agents — powered by a relational database.</p>
          <div className="row">
            {['FastAPI', 'React', 'MySQL'].map((t, i) => (
              <motion.span key={t} className="box mono float" style={{ padding: '6px 12px', animationDelay: `${i * 0.4}s` }}>{t}</motion.span>
            ))}
          </div>
          <div className="row"><b>THEME:</b>
            {THEMES.map(t => <div key={t} className="swatch" title={t} style={{ background: SWATCH[t], outline: t === theme ? '3px solid var(--a2)' : 'none' }} onClick={() => setTheme(t)} />)}
          </div>
        </div>
        <div style={{ display: 'grid', placeItems: 'center', padding: 24 }}>
          <motion.form onSubmit={submit} className="box" style={{ width: 'min(420px, 100%)' }} initial={{ y: 80, opacity: 0, rotate: 3 }} animate={{ y: 0, opacity: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 140, damping: 14 }}>
            <div className="tabs">
              <button type="button" className={'btn' + (mode === 'signup' ? '' : ' ghost')} onClick={() => { setMode('signup'); setErr('') }}>Sign up</button>
              <button type="button" className={'btn' + (mode === 'login' ? ' alt' : ' ghost')} onClick={() => { setMode('login'); setErr('') }}>Log in</button>
            </div>
            {mode === 'signup' && (<><label>Full name</label><input value={f.name} onChange={set('name')} placeholder="Krishna Agrawal" /></>)}
            <label>Email</label><input value={f.email} onChange={set('email')} placeholder="you@college.edu" autoComplete="email" />
            <label>Password</label><input type="password" value={f.password} onChange={set('password')} placeholder="min 8 characters" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
            {err && <div className="err" role="alert">⚠ {err}</div>}
            <button className="btn" disabled={busy} style={{ width: '100%', marginTop: 18 }}>
              {busy ? 'Please wait…' : mode === 'signup' ? 'Create account →' : 'Enter dashboard →'}
            </button>
          </motion.form>
        </div>
      </div>
    </>
  )
}
