import { Link } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import type { AgentOverview, AgentSummary, AlertRule, LogItem, RunItem } from '../api/types'
import { useApi } from '../api/useApi'
import { useApp } from '../state'
import { Badge, Card, Counter, PageHeader, ago } from '../components/ui'

const tip = { contentStyle: { border: '3px solid var(--ink)', borderRadius: 0, background: 'var(--surface)', color: 'var(--ink)' } }

export default function Dashboard() {
  const { user } = useApp()
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const overview = useApi(() => api<AgentOverview[]>('/analytics/overview'), [])
  const runs = useApi(() => api<RunItem[]>('/runs', { query: { limit: 100 } }), [])
  const logs = useApi(() => api<LogItem[]>('/logs', { query: { limit: 6 } }), [])
  const alerts = useApi(() => api<AlertRule[]>('/alerts', { query: { limit: 100 } }), [])

  const loadError = agents.error || overview.error || runs.error || logs.error || alerts.error
  const loading = agents.loading || overview.loading || runs.loading

  const totals = (overview.data ?? []).reduce(
    (acc, row) => {
      acc.total += row.runs_total
      acc.failed += row.runs_failed
      acc.latencyWeighted += (row.avg_latency_ms ?? 0) * row.runs_completed
      acc.completed += row.runs_completed
      return acc
    },
    { total: 0, failed: 0, latencyWeighted: 0, completed: 0 },
  )
  const failureRate = totals.total ? Math.round((totals.failed / totals.total) * 100) : 0
  const avgLatency = totals.completed ? Math.round(totals.latencyWeighted / totals.completed) : 0
  const activeAgents = (agents.data ?? []).filter((a) => a.status === 'active').length
  const firing = (alerts.data ?? []).filter((a) => a.status === 'triggered').length

  // Runs per hour from the most recent runs (the list endpoint is capped at 100).
  const perHour = new Map<string, { runs: number; errors: number }>()
  for (const run of runs.data ?? []) {
    const hour = new Date(run.started_at).toISOString().slice(11, 13) + ':00'
    const bucket = perHour.get(hour) ?? { runs: 0, errors: 0 }
    bucket.runs += 1
    if (run.status === 'failed') bucket.errors += 1
    perHour.set(hour, bucket)
  }
  const series = [...perHour.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([hour, v]) => ({ hour, ...v }))

  const statusCounts = ['completed', 'running', 'failed'].map((s) => ({
    name: s,
    value: (runs.data ?? []).filter((r) => r.status === s).length,
  }))
  const pieColors = ['var(--ok)', 'var(--a3)', 'var(--bad)']
  const agentBars = (overview.data ?? []).map((row) => ({ name: row.agent_name, runs: row.runs_total }))

  const stats: [string, number, string, string][] = [
    ['Active agents', activeAgents, '', '/agents'],
    ['Runs (7 days)', totals.total, '', '/runs'],
    ['Failure rate', failureRate, '%', '/runs'],
    ['Avg latency', avgLatency, 'ms', '/metrics'],
  ]

  return (
    <>
      <PageHeader title="Dashboard" sub={`Welcome back, ${user?.full_name ?? ''}. Live figures from the database.`}>
        <Link to="/agents"><button className="btn">+ New agent</button></Link>
        <Link to="/alerts"><button className="btn alt">{firing} alert{firing === 1 ? '' : 's'} firing</button></Link>
      </PageHeader>

      {loadError && <div className="err" role="alert">⚠ {loadError}</div>}
      {loading && <p className="mono">Loading live data…</p>}

      <div className="grid g4">
        {stats.map(([label, value, suffix, to], i) => (
          <Link key={label} to={to} style={{ textDecoration: 'none', color: 'inherit' }}>
            <Card i={i}><div className="mono" style={{ fontSize: 12 }}>{label.toUpperCase()}</div><div className="big"><Counter to={value} suffix={suffix} /></div></Card>
          </Link>
        ))}
      </div>

      <div className="grid g2" style={{ marginTop: 22 }}>
        <Card i={4}>
          <h3>Runs by hour (recent)</h3>
          {series.length === 0 ? <p className="mono">No runs yet. Create a run to see activity here.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={series}><CartesianGrid strokeDasharray="4 4" stroke="var(--ink)" opacity={0.25} /><XAxis dataKey="hour" tick={{ fill: 'var(--ink)', fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fill: 'var(--ink)', fontSize: 11 }} /><Tooltip {...tip} />
                <Area dataKey="runs" stroke="var(--ink)" strokeWidth={3} fill="var(--a1)" /><Area dataKey="errors" stroke="var(--ink)" strokeWidth={3} fill="var(--bad)" /></AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card i={5}>
          <h3>Run status (recent)</h3>
          {statusCounts.every((s) => s.value === 0) ? <p className="mono">No runs yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart><Pie data={statusCounts} dataKey="value" nameKey="name" outerRadius={95} stroke="var(--ink)" strokeWidth={3} label>{statusCounts.map((_, i) => <Cell key={i} fill={pieColors[i]} />)}</Pie><Tooltip {...tip} /></PieChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card i={6}>
          <h3>Runs by agent (7 days)</h3>
          {agentBars.length === 0 ? <p className="mono">No activity in the last 7 days.</p> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={agentBars}><XAxis dataKey="name" tick={{ fill: 'var(--ink)', fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fill: 'var(--ink)' }} /><Tooltip {...tip} /><Bar dataKey="runs" fill="var(--a2)" stroke="var(--ink)" strokeWidth={3} /></BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card i={7}>
          <div className="row" style={{ justifyContent: 'space-between' }}><h3>Latest logs</h3><Link to="/logs"><button className="btn alt2">Open explorer →</button></Link></div>
          {(logs.data ?? []).length === 0 && <p className="mono">No logs recorded yet.</p>}
          {(logs.data ?? []).map((l) => (
            <div key={l.id} className="row mono" style={{ padding: '8px 0', borderBottom: '2px dashed var(--ink)', fontSize: 13 }}>
              <Badge v={l.severity} /> <span style={{ flex: 1 }}>{l.message}</span> <span>{ago(l.timestamp)}</span>
            </div>
          ))}
        </Card>
      </div>
    </>
  )
}
