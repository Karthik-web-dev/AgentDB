import { useState } from 'react'
import { motion } from 'framer-motion'
import { THEMES, THEME_META, useApp } from '../state'
import { PageHeader } from '../components/ui'

const heights = [40, 70, 50, 90, 60, 80]

export default function Themes() {
  const { theme, setTheme } = useApp()
  const [filter, setFilter] = useState<'all' | 'light' | 'dark'>('all')
  const list = THEMES.filter(t => filter === 'all' || THEME_META[t][2] === filter)
  return (
    <>
      <PageHeader title="Themes" sub={`${THEMES.length} palettes · click a card to apply it instantly`}>
        {(['all', 'light', 'dark'] as const).map(f => (
          <button key={f} className={'btn' + (filter === f ? '' : ' ghost')} onClick={() => setFilter(f)}>{f}</button>
        ))}
      </PageHeader>
      <div className="grid g4" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(250px,1fr))' }}>
        {list.map((t, i) => (
          <motion.div key={t} className={'box hover tcard' + (t === theme ? ' sel' : '')} onClick={() => setTheme(t)}
            initial={{ opacity: 0, y: 30, rotate: i % 2 ? 1.5 : -1.5 }} animate={{ opacity: 1, y: 0, rotate: 0 }}
            transition={{ delay: i * 0.04, type: 'spring', stiffness: 220, damping: 18 }} whileTap={{ scale: 0.96 }}>
            <div className="tprev" data-theme={t}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="mini" style={{ background: 'var(--a1)', color: '#111' }}>AGENT/DB</span>
                <span className="mini" style={{ background: 'var(--ok)', color: '#111' }}>● live</span>
              </div>
              <div className="mini">Runs today<br /><span style={{ fontSize: 20 }}>1,284</span></div>
              <div className="bars">{heights.map((h, k) => <i key={k} style={{ height: `${h}%`, background: ['var(--a1)', 'var(--a2)', 'var(--a3)'][k % 3] }} />)}</div>
              <div className="row" style={{ gap: 6 }}>
                {['--a1', '--a2', '--a3', '--ok', '--bad', '--warn'].map(c => <span key={c} className="chip" style={{ background: `var(${c})` }} />)}
              </div>
            </div>
            <div className="row" style={{ justifyContent: 'space-between', padding: 14 }}>
              <div><h3 style={{ fontSize: 18 }}>{THEME_META[t][0]}</h3><span className="mono" style={{ fontSize: 11 }}>{THEME_META[t][2].toUpperCase()}</span></div>
              <span className={'badge ' + (t === theme ? 'b-active' : '')}>{t === theme ? 'Active' : 'Apply'}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </>
  )
}
