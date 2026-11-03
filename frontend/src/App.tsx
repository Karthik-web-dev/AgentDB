import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import { Agents, Tasks } from './pages/Manage'
import { Alerts, Audit, Logs, Metrics, Runs, Settings } from './pages/Explore'
import Themes from './pages/Themes'
import Chat from './pages/Chat'
import Memory from './pages/Memory'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Auth />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/themes" element={<Themes />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
