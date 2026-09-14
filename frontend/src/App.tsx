import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Layout from './components/layout/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import MyProfile from './pages/MyProfile'
import MyPublications from './pages/MyPublications'
import VerificationQueue from './pages/VerificationQueue'
import ResearchImpact from './pages/ResearchImpact'
import ResearchIntegrity from './pages/ResearchIntegrity'
import ResearchSearch from './pages/ResearchSearch'
import ResearchAreas from './pages/ResearchAreas'
import Collaborations from './pages/Collaborations'
import Opportunities from './pages/Opportunities'
import ResearchPipeline from './pages/ResearchPipeline'
import KnowledgeGraph from './pages/KnowledgeGraph'
import ResearchAssistant from './pages/ResearchAssistant'
import Reports from './pages/Reports'
import Analytics from './pages/Analytics'
import Notifications from './pages/Notifications'
import Settings from './pages/Settings'
import Monitoring from './pages/Monitoring'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/profile" element={<MyProfile />} />
              <Route path="/publications" element={<MyPublications />} />
              <Route path="/verification" element={<VerificationQueue />} />
              <Route path="/impact" element={<ResearchImpact />} />
              <Route path="/integrity" element={<ResearchIntegrity />} />
              <Route path="/search" element={<ResearchSearch />} />
              <Route path="/areas" element={<ResearchAreas />} />
              <Route path="/collaborations" element={<Collaborations />} />
              <Route path="/opportunities" element={<Opportunities />} />
              <Route path="/pipeline" element={<ResearchPipeline />} />
              <Route path="/graph" element={<KnowledgeGraph />} />
              <Route path="/assistant" element={<ResearchAssistant />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/notifications" element={<Notifications />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
