import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AgentSummary, ChatResult, MemoryTurn } from '../api/types'
import { useApi } from '../api/useApi'
import { Card, PageHeader } from '../components/ui'

export default function Chat() {
  const agents = useApi(() => api<AgentSummary[]>('/agents', { query: { limit: 100 } }), [])
  const [agentId, setAgentId] = useState(0)
  const [history, setHistory] = useState<MemoryTurn[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [contextInfo, setContextInfo] = useState('')

  useEffect(() => {
    if (!agentId && agents.data?.length) setAgentId(agents.data[0].id)
  }, [agentId, agents.data])

  useEffect(() => {
    if (!agentId) { setHistory([]); return }
    let cancelled = false
    api<{ agent_id: number; messages: MemoryTurn[] }>(`/agents/${agentId}/memory`)
      .then((result) => { if (!cancelled) setHistory(result.messages) })
      .catch((e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load memory.') })
    return () => { cancelled = true }
  }, [agentId])

  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!agentId || !message.trim()) return
    setBusy(true); setError('')
    try {
      const result = await api<ChatResult>(`/agents/${agentId}/chat`, { method: 'POST', json: { message: message.trim() } })
      const saved = await api<{ agent_id: number; messages: MemoryTurn[] }>(`/agents/${agentId}/memory`)
      setHistory(saved.messages)
      setContextInfo(`Context reduced about ${result.context_reduction_pct}% by characters (${result.context_original_chars.toLocaleString()} → ${result.context_sent_chars.toLocaleString()}); estimate, not token count.`)
      setMessage('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The model request failed.')
    } finally { setBusy(false) }
  }

  const selected = agents.data?.find((agent) => agent.id === agentId)
  return <>
    <PageHeader title="Agent Chat" sub="Chat runs are stored and reused as context on later requests.">
      <select value={agentId} onChange={(e) => setAgentId(Number(e.target.value))} aria-label="Choose agent">
        {(agents.data ?? []).map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {agent.model}</option>)}
      </select>
    </PageHeader>
    {error && <div className="err" role="alert">⚠ {error}</div>}
    {!agents.loading && !agents.data?.length && <p className="mono">Register an agent first. Its model field should be an OpenRouter model ID, such as openai/gpt-4o-mini.</p>}
    {selected && <Card>
      <div style={{ minHeight: 300, maxHeight: '55vh', overflowY: 'auto', display: 'grid', gap: 12, marginBottom: 20 }}>
        {!history.length && <p className="mono">No saved context for this agent yet. Send a message to start a persistent conversation.</p>}
        {history.map((turn) => <div key={turn.id} style={{ padding: 12, border: '2px solid var(--ink)', background: turn.role === 'user' ? 'var(--surface)' : 'var(--a1)', whiteSpace: 'pre-wrap' }}>
          <strong>{turn.role === 'user' ? 'You' : selected.name}</strong><div style={{ marginTop: 6 }}>{turn.content}</div>
        </div>)}
      </div>
      {contextInfo && <p className="mono" aria-live="polite">{contextInfo}</p>}
      <form onSubmit={send}>
        <label htmlFor="agent-message">Message</label>
        <textarea id="agent-message" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={12000} rows={4} placeholder="Ask your agent…" />
        <button className="btn" disabled={busy || !message.trim()} style={{ marginTop: 12 }}>{busy ? 'Waiting for model…' : 'Send'}</button>
      </form>
    </Card>}
  </>
}
