// Thin fetch wrapper for the AgentDB API. The Vite dev server and nginx both proxy /api to the backend.

const TOKEN_KEY = 'agentdb_token'
const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable (private mode): the session simply lasts for this page */
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & { json?: unknown; query?: Record<string, string | number | undefined | null> }

function buildQuery(query?: RequestOptions['query']): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

function errorMessage(data: unknown, fallback: string): string {
  const detail = (data as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg ?? 'Invalid value').join('; ')
  }
  return fallback
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, query, headers, ...rest } = options
  const finalHeaders = new Headers(headers)
  if (json !== undefined) finalHeaders.set('Content-Type', 'application/json')
  const token = getToken()
  if (token) finalHeaders.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}${buildQuery(query)}`, {
      ...rest,
      headers: finalHeaders,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the AgentDB server. Is the backend running?')
  }

  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(data, response.statusText || 'Request failed'))
  }
  return data as T
}
