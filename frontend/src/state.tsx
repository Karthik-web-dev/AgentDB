import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api, ApiError, getToken, setToken } from './api/client'
import type { Token, User } from './api/types'

export const THEME_META = {
  yellow: ['Banana Pop', '#ffd400', 'light'], pink: ['Hot Pink', '#ff4d94', 'light'], mint: ['Mint Fresh', '#00d084', 'light'], dark: ['Night Shift', '#b6ff3c', 'dark'],
  orange: ['Blaze', '#ff7a1a', 'light'], sky: ['Clear Sky', '#4cc9f0', 'light'], lilac: ['Lilac Dream', '#b388ff', 'light'], red: ['Red Alert', '#ff3b30', 'light'],
  concrete: ['Concrete Jungle', '#c8c8c8', 'light'], retro: ['Retro Diner', '#2a9d8f', 'light'], cyber: ['Cyberpunk', '#ff2bd6', 'dark'], forest: ['Deep Forest', '#7bd88f', 'dark'],
  ocean: ['Deep Ocean', '#38bdf8', 'dark'], coffee: ['Coffee Shop', '#a0673a', 'light'], bubblegum: ['Bubblegum', '#ff9ecb', 'light'], sunset: ['Sunset Strip', '#ff6b35', 'light'],
  toxic: ['Toxic Waste', '#39ff14', 'dark'], ice: ['Ice Cold', '#a5e1ff', 'light'],
} as const
export type Theme = keyof typeof THEME_META
export const THEMES = Object.keys(THEME_META) as Theme[]
export const SWATCH: Record<string, string> = Object.fromEntries(Object.entries(THEME_META).map(([k, v]) => [k, v[1]]))

type Ctx = {
  theme: Theme
  setTheme: (t: Theme) => void
  /** The signed-in user, or null. `sessionChecked` is false until the stored token has been verified. */
  user: User | null
  sessionChecked: boolean
  login: (email: string, password: string) => Promise<void>
  register: (fullName: string, email: string, password: string) => Promise<void>
  logout: () => void
}

const C = createContext<Ctx>(null as unknown as Ctx)
export const useApp = () => useContext(C)

function loadTheme(): Theme {
  try {
    const stored = localStorage.getItem('theme')
    const parsed = stored ? (JSON.parse(stored) as Theme) : 'yellow'
    return parsed in THEME_META ? parsed : 'yellow'
  } catch {
    return 'yellow'
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(loadTheme)
  const [user, setUser] = useState<User | null>(null)
  const [sessionChecked, setSessionChecked] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', JSON.stringify(theme)) } catch { /* ignore */ }
  }, [theme])

  // Restore the session from the stored token. An expired or invalid token is discarded.
  useEffect(() => {
    if (!getToken()) {
      setSessionChecked(true)
      return
    }
    api<User>('/auth/me')
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setSessionChecked(true))
  }, [])

  const login = async (email: string, password: string) => {
    const token = await api<Token>('/auth/login', { method: 'POST', json: { email, password } })
    setToken(token.access_token)
    setUser(await api<User>('/auth/me'))
  }

  const register = async (fullName: string, email: string, password: string) => {
    await api<User>('/auth/register', { method: 'POST', json: { full_name: fullName, email, password } })
    await login(email, password)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  return (
    <C.Provider value={{ theme, setTheme, user, sessionChecked, login, register, logout }}>
      {children}
    </C.Provider>
  )
}

export { ApiError }
