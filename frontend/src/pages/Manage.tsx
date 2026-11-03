import { FormEvent, useState } from 'react'
import { api } from '../api/client'
import type { AgentSummary, TaskItem } from '../api/types'
import { useApi } from '../api/useApi'
import { Badge, Card, Modal, PageHeader, Table } from '../components/ui'

const ENVIRONMENTS = ['development', 'staging', 'production'] as const
const PRIORITIES = ['low', 'medium', 'high', 'critical'] as const

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export function Agents() {
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ name: '', model: '', environment: 'development', description: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const list = (agents.data ?? []).filter((a) => (a.name + a.model).toLowerCase().includes(q.toLowerCase()))

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    if (!f.name.trim() || !f.model.trim()) return setErr('Name and model are required.')
    setBusy(true)
    try {
      await api('/agents', { method: 'POST', json: { name: f.name.trim(), model: f.model.trim(), environment: f.environment, description: f.description.trim() || null } })
      setOpen(false)
      setF({ name: '', model: '', environment: 'development', description: '' })
      agents.reload()
    } catch (error) {
      setErr(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Agents" sub={agents.loading ? 'Loading…' : `${agents.data?.length ?? 0} registered agents`}>
        <input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 200 }} />
        <button className="btn" onClick={() => setOpen(true)}>+ Register agent</button>
      </PageHeader>
      {agents.error && <div className="err" role="alert">⚠ {agents.error}</div>}
      {!agents.loading && list.length === 0 && <p className="mono">No agents yet. Register one to start recording runs.</p>}
      <div className="grid g4">
        {list.map((a, i) => (
          <Card key={a.id} i={i}>
            <div className="row" style={{ justifyContent: 'space-between' }}><h3>{a.name}</h3><Badge v={a.status} /></div>
            <div className="mono" style={{ fontSize: 12, marginTop: 8 }}>MODEL: {a.model}<br />ENV: {a.environment} · v{a.version}</div>
          </Card>
        ))}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Register agent">
        <form onSubmit={save}>
          <label>Name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={100} />
          <label>Model</label><input value={f.model} onChange={(e) => setF({ ...f, model: e.target.value })} maxLength={50} placeholder="gpt-4o" />
          <label>Environment</label>
          <select value={f.environment} onChange={(e) => setF({ ...f, environment: e.target.value })}>{ENVIRONMENTS.map((x) => <option key={x}>{x}</option>)}</select>
          <label>Description (optional)</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          {err && <div className="err" role="alert">⚠ {err}</div>}
          <button className="btn" disabled={busy} style={{ marginTop: 16, width: '100%' }}>{busy ? 'Saving…' : 'Save'}</button>
        </form>
      </Modal>
    </>
  )
}

export function Tasks() {
  const tasks = useApi(() => api<TaskItem[]>('/tasks', { query: { limit: 100 } }), [])
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('all')
  const [f, setF] = useState({ title: '', agent_id: 0, priority: 'medium' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const list = (tasks.data ?? []).filter((t) => status === 'all' || t.status === status)
  const agentName = (id: number) => agents.data?.find((a) => a.id === id)?.name ?? `agent #${id}`

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    const agentId = f.agent_id || agents.data?.[0]?.id
    if (!f.title.trim()) return setErr('Give the task a title.')
    if (!agentId) return setErr('Register an agent before creating a task.')
    setBusy(true)
    try {
      await api('/tasks', { method: 'POST', json: { agent_id: agentId, title: f.title.trim(), priority: f.priority } })
      setOpen(false)
      setF({ title: '', agent_id: 0, priority: 'medium' })
      tasks.reload()
    } catch (error) {
      setErr(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Tasks" sub={tasks.loading ? 'Loading…' : `${tasks.data?.length ?? 0} tasks assigned to agents`}>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 160 }}>{['all', 'pending', 'in_progress', 'completed', 'failed', 'cancelled'].map((s) => <option key={s}>{s}</option>)}</select>
        <button className="btn" onClick={() => setOpen(true)}>+ New task</button>
      </PageHeader>
      {tasks.error && <div className="err" role="alert">⚠ {tasks.error}</div>}
      <Table
        head={['ID', 'Title', 'Agent', 'Status', 'Priority']}
        rows={list.map((t) => [`#${t.id}`, t.title, agentName(t.agent_id), <Badge v={t.status} />, <Badge v={t.priority} />])}
      />
      <Modal open={open} onClose={() => setOpen(false)} title="New task">
        <form onSubmit={save}>
          <label>Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} maxLength={150} />
          <label>Agent</label>
          <select value={f.agent_id} onChange={(e) => setF({ ...f, agent_id: Number(e.target.value) })}>
            {(agents.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <label>Priority</label>
          <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select>
          {err && <div className="err" role="alert">⚠ {err}</div>}
          <button className="btn" disabled={busy} style={{ marginTop: 16, width: '100%' }}>{busy ? 'Creating…' : 'Create'}</button>
        </form>
      </Modal>
    </>
  )
}
