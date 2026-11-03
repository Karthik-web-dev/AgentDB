import { ReactNode, useEffect, useState } from 'react'
import { motion, animate } from 'framer-motion'

export const Badge = ({ v }: { v: string }) => <span className={`badge b-${v}`}>{v}</span>

export function PageHeader({ title, sub, children }: { title: string; sub: string; children?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="row" style={{ justifyContent: 'space-between', marginBottom: 24 }}>
      <div>
        <h1 style={{ fontSize: 44 }}>{title}</h1>
        <p className="mono" style={{ marginTop: 4 }}>{sub}</p>
      </div>
      <div className="row">{children}</div>
    </motion.div>
  )
}

export function Card({ children, i = 0, style }: { children: ReactNode; i?: number; style?: React.CSSProperties }) {
  return (
    <motion.div className="box hover" style={style} initial={{ opacity: 0, y: 30, rotate: -1 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ delay: i * 0.07, type: 'spring', stiffness: 220, damping: 18 }}>
      {children}
    </motion.div>
  )
}

export function Counter({ to, suffix = '' }: { to: number; suffix?: string }) {
  const [v, setV] = useState(0)
  useEffect(() => { const c = animate(0, to, { duration: 1.2, onUpdate: x => setV(Math.round(x * 10) / 10) }); return () => c.stop() }, [to])
  return <>{v.toLocaleString()}{suffix}</>
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="box" style={{ padding: 0, overflowX: 'auto' }}>
      <table>
        <thead><tr>{head.map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <motion.tr key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 15) * 0.025 }}>
              {r.map((c, j) => <td key={j}>{c}</td>)}
            </motion.tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={head.length}>Nothing found. Try another filter.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  if (!open) return null
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.55)', display: 'grid', placeItems: 'center', zIndex: 50 }}>
      <motion.div className="box" onClick={e => e.stopPropagation()} initial={{ scale: 0.7, rotate: -4 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 300, damping: 18 }} style={{ width: 'min(460px, 92vw)' }}>
        <h2 style={{ marginBottom: 8 }}>{title}</h2>
        {children}
      </motion.div>
    </motion.div>
  )
}

export const ago = (iso: string) => {
  const m = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  return m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`
}
