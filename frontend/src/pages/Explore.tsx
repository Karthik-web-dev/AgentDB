import { FormEvent, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import type { AgentCost, AgentOverview, AgentSummary, AlertFiring, AlertRule, AuditRecord, ChainVerification, LatencyAnomaly, LogItem, RunItem } from '../api/types'
import { useApi } from '../api/useApi'
import { THEMES, useApp } from '../state'
import { Badge, Card, Modal, PageHeader, Table, ago } from '../components/ui'

const tip = { contentStyle: { border: '3px solid var(--ink)', borderRadius: 0, background: 'var(--surface)', color: 'var(--ink)' } }

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

function Notice({ error }: { error: string | null }) {
  return error ? <div className="err" role="alert">⚠ {error}</div> : null
}

export function Runs() {
  const runs = useApi(() => api<RunItem[]>('/runs', { query: { limit: 100 } }), [])
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [s, setS] = useState('all')
  const list = (runs.data ?? []).filter((r) => s === 'all' || r.status === s)
  const agentName = (id: number) => agents.data?.find((a) => a.id === id)?.name ?? `agent #${id}`
  return (
    <>
      <PageHeader title="Runs" sub="Execution history of every agent, newest first">
        <select value={s} onChange={(e) => setS(e.target.value)} style={{ width: 160 }}>{['all', 'running', 'completed', 'failed', 'cancelled'].map((x) => <option key={x}>{x}</option>)}</select>
      </PageHeader>
      <Notice error={runs.error} />
      <Table
        head={['Run', 'Agent', 'Status', 'Started', 'Completed']}
        rows={list.map((r) => [`#${r.id}`, agentName(r.agent_id), <Badge v={r.status} />, ago(r.started_at), r.completed_at ? ago(r.completed_at) : '—'])}
      />
    </>
  )
}

export function Logs() {
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [sev, setSev] = useState('all')
  const logs = useApi(
    () => api<LogItem[]>('/logs', { query: { limit: 100, severity: sev === 'all' ? undefined : sev, search: search || undefined } }),
    [sev, search],
  )
  return (
    <>
      <PageHeader title="Log Explorer" sub={logs.loading ? 'Loading…' : `${logs.data?.length ?? 0} structured log entries`}>
        <form onSubmit={(e) => { e.preventDefault(); setSearch(q.trim()) }} className="row">
          <input placeholder="Search message…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 220 }} />
          <button className="btn alt2" type="submit">Search</button>
        </form>
        <select value={sev} onChange={(e) => setSev(e.target.value)} style={{ width: 150 }}>{['all', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map((x) => <option key={x}>{x}</option>)}</select>
      </PageHeader>
      <Notice error={logs.error} />
      <Table
        head={['Time', 'Severity', 'Run', 'Message']}
        rows={(logs.data ?? []).map((l) => [ago(l.timestamp), <Badge v={l.severity} />, `#${l.run_id}`, <span className="mono">{l.message}</span>])}
      />
    </>
  )
}

export function Metrics() {
  const overview = useApi(() => api<AgentOverview[]>('/analytics/overview'), [])
  const anomalies = useApi(() => api<LatencyAnomaly[]>('/analytics/latency-anomalies', { query: { z_threshold: 3 } }), [])
  const cost = useApi(() => api<AgentCost[]>('/analytics/cost'), [])
  const bars = (overview.data ?? []).map((row) => ({ name: row.agent_name, latency: row.avg_latency_ms ?? 0, failure: row.failure_rate_pct }))
  return (
    <>
      <PageHeader title="Metrics" sub="Performance, anomalies and cost over the last 7 days" />
      <Notice error={overview.error || anomalies.error || cost.error} />
      <div className="grid g2">
        <Card>
          <h3>Average latency per agent (ms)</h3>
          {bars.length === 0 ? <p className="mono">No completed runs in the last 7 days.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={bars}><CartesianGrid strokeDasharray="4 4" stroke="var(--ink)" opacity={0.25} /><XAxis dataKey="name" tick={{ fill: 'var(--ink)', fontSize: 11 }} /><YAxis tick={{ fill: 'var(--ink)', fontSize: 11 }} /><Tooltip {...tip} /><Bar dataKey="latency" fill="var(--a2)" stroke="var(--ink)" strokeWidth={2} /></BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card i={1}>
          <h3>Latency anomalies (|z| ≥ 3)</h3>
          {(anomalies.data ?? []).length === 0 ? <p className="mono">No anomalies detected.</p> : (
            <Table
              head={['Run', 'Agent', 'Latency', 'Baseline', 'z']}
              rows={(anomalies.data ?? []).map((a) => [`#${a.run_id}`, `#${a.agent_id}`, `${a.latency_ms} ms`, `${a.baseline_mean_ms} ms`, a.z_score ?? a.detection_reason])}
            />
          )}
        </Card>
        <Card i={2}>
          <h3>Token cost (all time)</h3>
          {(cost.data ?? []).length === 0 ? <p className="mono">No cost data yet. Report token usage as metrics to see costs.</p> : (
            <Table
              head={['Agent', 'Runs', 'Priced', 'Unpriced', 'Cost (USD)']}
              rows={(cost.data ?? []).map((c) => [c.agent_name, c.total_runs, c.priced_runs, c.unpriced_runs, `$${c.total_cost_usd.toFixed(4)}`])}
            />
          )}
        </Card>
      </div>
    </>
  )
}

const RULE_OPERATORS = ['>', '>=', '<', '<=', '==', '!='] as const

export function Alerts() {
  const alerts = useApi(() => api<AlertRule[]>('/alerts', { query: { limit: 100 } }), [])
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [open, setOpen] = useState(false)
  const [viewing, setViewing] = useState<{ rule: AlertRule; firings: AlertFiring[] } | null>(null)
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ rule_name: '', rule_type: 'threshold' as 'threshold' | 'failure_window', metric_name: 'latency_ms', condition_operator: '>', threshold_value: 2000, time_window_minutes: 10, agent_id: '' })

  const run = async (action: () => Promise<unknown>) => {
    setActionError('')
    try {
      await action()
      alerts.reload()
    } catch (error) {
      setActionError(errorText(error))
    }
  }

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setActionError('')
    if (!f.rule_name.trim()) return setActionError('Give the rule a name.')
    setBusy(true)
    try {
      const body: Record<string, unknown> = {
        rule_name: f.rule_name.trim(),
        rule_type: f.rule_type,
        threshold_value: Number(f.threshold_value),
        time_window_minutes: Number(f.time_window_minutes),
        agent_id: f.agent_id ? Number(f.agent_id) : null,
      }
      if (f.rule_type === 'threshold') {
        body.metric_name = f.metric_name.trim()
        body.condition_operator = f.condition_operator
      }
      await api('/alerts', { method: 'POST', json: body })
      setOpen(false)
      setF({ ...f, rule_name: '' })
      alerts.reload()
    } catch (error) {
      setActionError(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  const viewFirings = async (rule: AlertRule) => {
    try {
      const firings = await api<AlertFiring[]>(`/alerts/${rule.id}/firings`, { query: { limit: 50 } })
      setViewing({ rule, firings })
    } catch (error) {
      setActionError(errorText(error))
    }
  }

  return (
    <>
      <PageHeader title="Alerts" sub="Threshold and failure-window rules, evaluated inside the database">
        <button className="btn" onClick={() => setOpen(true)}>+ New rule</button>
      </PageHeader>
      <Notice error={alerts.error || actionError} />
      {!alerts.loading && (alerts.data ?? []).length === 0 && <p className="mono">No alert rules yet.</p>}
      <div className="grid g4">
        {(alerts.data ?? []).map((a, i) => (
          <Card key={a.id} i={i}>
            <div className="row" style={{ justifyContent: 'space-between' }}><h3>{a.rule_name}</h3><Badge v={a.status} /></div>
            <p className="mono" style={{ margin: '10px 0' }}>
              {a.rule_type === 'failure_window'
                ? `≥ ${a.threshold_value} failed runs in ${a.time_window_minutes} min`
                : `${a.metric_name} ${a.condition_operator} ${a.threshold_value}`}
              <br />{a.agent_id ? `agent #${a.agent_id}` : 'all your agents'}
            </p>
            <div className="row">
              <button className="btn alt2" onClick={() => run(() => api(`/alerts/${a.id}`, { method: 'PATCH', json: { status: a.status === 'disabled' ? 'active' : 'disabled' } }))}>
                {a.status === 'disabled' ? 'Enable' : 'Disable'}
              </button>
              {a.status !== 'resolved' && <button className="btn" onClick={() => run(() => api(`/alerts/${a.id}/resolve`, { method: 'POST' }))}>Resolve</button>}
              <button className="btn ghost" onClick={() => viewFirings(a)}>History</button>
            </div>
          </Card>
        ))}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="New alert rule">
        <form onSubmit={create}>
          <label>Name</label><input value={f.rule_name} onChange={(e) => setF({ ...f, rule_name: e.target.value })} maxLength={100} />
          <label>Rule type</label>
          <select value={f.rule_type} onChange={(e) => setF({ ...f, rule_type: e.target.value as 'threshold' | 'failure_window' })}>
            <option value="threshold">Metric threshold</option>
            <option value="failure_window">Failed runs in a window</option>
          </select>
          {f.rule_type === 'threshold' ? (
            <>
              <label>Metric name</label><input value={f.metric_name} onChange={(e) => setF({ ...f, metric_name: e.target.value })} maxLength={50} />
              <label>Condition</label>
              <select value={f.condition_operator} onChange={(e) => setF({ ...f, condition_operator: e.target.value })}>{RULE_OPERATORS.map((o) => <option key={o}>{o}</option>)}</select>
              <label>Threshold</label><input type="number" value={f.threshold_value} onChange={(e) => setF({ ...f, threshold_value: Number(e.target.value) })} />
            </>
          ) : (
            <>
              <label>Failures that trigger it</label><input type="number" min={1} value={f.threshold_value} onChange={(e) => setF({ ...f, threshold_value: Number(e.target.value) })} />
              <label>Window (minutes)</label><input type="number" min={1} value={f.time_window_minutes} onChange={(e) => setF({ ...f, time_window_minutes: Number(e.target.value) })} />
            </>
          )}
          <label>Applies to</label>
          <select value={f.agent_id} onChange={(e) => setF({ ...f, agent_id: e.target.value })}>
            <option value="">All my agents</option>
            {(agents.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          {actionError && <div className="err" role="alert">⚠ {actionError}</div>}
          <button className="btn" disabled={busy} style={{ marginTop: 16, width: '100%' }}>{busy ? 'Saving…' : 'Create rule'}</button>
        </form>
      </Modal>

      <Modal open={viewing !== null} onClose={() => setViewing(null)} title={`History: ${viewing?.rule.rule_name ?? ''}`}>
        {viewing && (viewing.firings.length === 0
          ? <p className="mono">This rule has not fired yet.</p>
          : <Table head={['Fired', 'Observed', 'Threshold', 'Source']} rows={viewing.firings.map((x) => [ago(x.fired_at), x.observed_value, x.threshold_value, x.run_id ? `run #${x.run_id}` : `metric #${x.metric_id}`])} />)}
      </Modal>
    </>
  )
}

export function Audit() {
  const audit = useApi(() => api<AuditRecord[]>('/audit', { query: { limit: 100 } }), [])
  const [verdict, setVerdict] = useState<ChainVerification | null>(null)
  const [verifyError, setVerifyError] = useState('')
  const verify = async () => {
    setVerifyError('')
    try {
      setVerdict(await api<ChainVerification>('/audit/verify'))
    } catch (error) {
      setVerifyError(errorText(error))
    }
  }
  return (
    <>
      <PageHeader title="Audit Trail" sub="Records of important changes, linked into a tamper-evident chain">
        <button className="btn alt2" onClick={verify}>Verify chain</button>
      </PageHeader>
      <Notice error={audit.error || verifyError} />
      {verdict && (
        <div className={verdict.is_valid ? 'box' : 'err'} role="status" style={{ marginBottom: 18 }}>
          <b>{verdict.is_valid ? '✔ Intact' : '✘ Broken'}</b> — {verdict.message}
        </div>
      )}
      <Table
        head={['#', 'Chain', 'Action', 'Entity', 'When']}
        rows={(audit.data ?? []).map((a) => [a.id, a.chain_seq ?? '—', <span className="badge">{a.action}</span>, `${a.entity_type}${a.entity_id ? ` #${a.entity_id}` : ''}`, ago(a.timestamp)])}
      />
    </>
  )
}

export function Settings() {
  const { theme, setTheme, user, logout } = useApp()
  return (
    <>
      <PageHeader title="Settings" sub="Profile and appearance" />
      <div className="grid g2">
        <Card><h3>Profile</h3><p className="mono" style={{ marginTop: 10 }}>Name: {user?.full_name}<br />Email: {user?.email}<br />Role: {user?.role}</p>
          <button className="btn alt" style={{ marginTop: 14 }} onClick={logout}>Log out</button>
        </Card>
        <Card i={1}><h3>Theme</h3>
          <div className="row" style={{ marginTop: 12 }}>{THEMES.slice(0, 6).map((t) => <button key={t} className={'btn' + (t === theme ? '' : ' ghost')} onClick={() => setTheme(t)}>{t}</button>)}</div>
        </Card>
      </div>
    </>
  )
}
