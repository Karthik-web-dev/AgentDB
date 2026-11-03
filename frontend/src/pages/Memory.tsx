import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AgentSummary, MemorySummary, MemoryTurn } from '../api/types'
import { useApi } from '../api/useApi'
import { Card, PageHeader } from '../components/ui'

export default function Memory() {
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [agentId, setAgentId] = useState(0)
  const [summary, setSummary] = useState<MemorySummary | null>(null)
  const [messages, setMessages] = useState<MemoryTurn[]>([])
  const [loading, setLoading] = useState(false)
  const [compacting, setCompacting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!agentId && agents.data?.length) setAgentId(agents.data[0].id)
  }, [agentId, agents.data])

  useEffect(() => {
    if (!agentId) { setSummary(null); setMessages([]); return }
    let cancelled = false
    setLoading(true); setError('')
    Promise.all([
      api<MemorySummary>(`/agents/${agentId}/memory/summary`),
      api<{ agent_id: number; messages: MemoryTurn[] }>(`/agents/${agentId}/memory`),
    ]).then(([compressed, raw]) => {
      if (cancelled) return
      setSummary(compressed)
      setMessages(raw.messages)
    }).catch((e: unknown) => {
      if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load agent memory.')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [agentId])

  const compact = async () => {
    if (!agentId) return
    setCompacting(true); setError(''); setNotice('')
    try {
      const compressed = await api<MemorySummary>(`/agents/${agentId}/memory/summary?rebuild=true`, { method: 'POST' })
      const raw = await api<{ agent_id: number; messages: MemoryTurn[] }>(`/agents/${agentId}/memory`)
      setSummary(compressed)
      setMessages(raw.messages)
      setNotice(`Rebuilt memory from ${compressed.source_message_count} messages. The complete fact list is now persistent context for the next chat request.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not compress conversation memory.')
    } finally { setCompacting(false) }
  }

  const selected = agents.data?.find((agent) => agent.id === agentId)
  const coveredMessages = messages.filter((message) => message.id <= (summary?.summarized_through_id ?? 0))
  const hasUncompressedMessages = messages.some((message) => message.id > (summary?.summarized_through_id ?? 0))
  return <>
    <PageHeader title="Memory" sub="The compact summary sent to the model, with the source turns it represents.">
      {/* {selected && <button className="btn" onClick={compact} disabled={loading || compacting || messages.length === 0}>
        {compacting ? 'Rebuilding…' : 'Rebuild summary from all messages'}
      </button>} */}
      <select value={agentId} onChange={(e) => setAgentId(Number(e.target.value))} aria-label="Choose agent">
        {(agents.data ?? []).map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.model}</option>)}
      </select>
    </PageHeader>
    {error && <div className="err" role="alert">⚠ {error}</div>}
    {notice && <p className="mono" role="status">{notice}</p>}
    {!agents.loading && !agents.data?.length && <p className="mono">Register an agent and chat with it to build persistent memory.</p>}
    {selected && <>
      <div className="grid g4" style={{ marginBottom: 20 }}>
        <Card><div className="mono">SOURCE MESSAGES</div><h2>{summary?.source_message_count ?? 0}</h2></Card>
        <Card><div className="mono">SOURCE CHARACTERS</div><h2>{(summary?.source_chars ?? 0).toLocaleString()}</h2></Card>
        <Card><div className="mono">SUMMARY CHARACTERS</div><h2>{(summary?.summary_chars ?? 0).toLocaleString()}</h2></Card>
        <Card><div className="mono">SUMMARY REDUCTION</div><h2>{summary?.reduction_pct ?? 0}%</h2></Card>
      </div>
      <Card>
        <h3>Generated context sent to the model</h3>
        {loading ? <p className="mono">Loading memory…</p> : summary?.summary
          ? <pre style={{ whiteSpace: 'pre-wrap', font: 'inherit', margin: 0 }}>{summary.summary}</pre>
          : <p className="mono">No summary has been generated yet. Add chat turns, then select “Rebuild summary from all messages” to create one immediately.</p>}
      </Card>
      <Card style={{ marginTop: 20 }}>
        <details>
          <summary style={{ cursor: 'pointer', fontWeight: 800 }}>Show the {coveredMessages.length} original messages represented by this summary</summary>
          <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
            {coveredMessages.map((turn) => <div key={turn.id} style={{ padding: 12, border: '2px solid var(--ink)', background: turn.role === 'user' ? 'var(--surface)' : 'var(--a1)', whiteSpace: 'pre-wrap' }}>
              <strong>{turn.role === 'user' ? 'User' : selected.name} · run #{turn.run_id}</strong>
              <div style={{ marginTop: 6 }}>{turn.content}</div>
            </div>)}
            {!coveredMessages.length && <p className="mono">No source turns are covered by a summary yet.</p>}
          </div>
        </details>
      </Card>
    </>}
  </>
}
