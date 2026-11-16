import { useCallback, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'
import { Shell } from './components/Shell'
import { Toasts } from './components/ui'
import AdvisorPanel from './components/AdvisorPanel'
import Analytics from './pages/Analytics'
import Assignments from './pages/Assignments'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'
import Onboarding from './pages/Onboarding'
import Plan from './pages/Plan'
import Practice from './pages/Practice'
import Revision from './pages/Revision'
import Settings from './pages/Settings'
import Subjects from './pages/Subjects'
import Tutor from './pages/Tutor'
import Viva from './pages/Viva'

const PAGES = {
  dashboard: Dashboard,
  plan: Plan,
  subjects: Subjects,
  tutor: Tutor,
  practice: Practice,
  viva: Viva,
  revision: Revision,
  analytics: Analytics,
  assignments: Assignments,
  settings: Settings,
}

const readHash = () => window.location.hash.replace(/^#\/?/, '') || 'dashboard'

export default function App() {
  const [route, setRoute] = useState(readHash)
  const [student, setStudent] = useState(null)
  const [booting, setBooting] = useState(true)
  const [toasts, setToasts] = useState([])
  const [advisorOpen, setAdvisorOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const notify = useCallback((message, tone = 'ok') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev.slice(-3), { id, message, tone }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200)
  }, [])

  const go = useCallback((next) => {
    window.location.hash = `#/${next}`
    setRoute(next)
  }, [])

  useEffect(() => {
    const onHash = () => setRoute(readHash())
    window.addEventListener('hashchange', onHash)
    const onLogout = () => {
      setStudent(null)
      go('auth')
    }
    window.addEventListener('pp:logout', onLogout)
    return () => {
      window.removeEventListener('hashchange', onHash)
      window.removeEventListener('pp:logout', onLogout)
    }
  }, [go])

  const bootstrap = useCallback(async () => {
    if (!getToken()) {
      setBooting(false)
      return
    }
    try {
      setStudent(await api.me())
    } catch {
      setToken(null)
      setStudent(null)
    } finally {
      setBooting(false)
    }
  }, [])

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  function onAuthed(result) {
    setToken(result.token)
    setStudent(result.student)
    go(result.student?.onboarded ? 'dashboard' : 'onboarding')
  }

  function onOnboarded(updated) {
    setStudent(updated)
    setRefreshKey((k) => k + 1)
    go('dashboard')
  }

  async function logout() {
    try {
      await api.logout()
    } catch {
      /* token may already be dead; clearing locally is what matters */
    }
    setToken(null)
    setStudent(null)
    go('auth')
    notify('Signed out — every session token was revoked.')
  }

  const refresh = () => setRefreshKey((k) => k + 1)

  if (booting) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/10 border-t-indigo-400" />
      </div>
    )
  }

  if (!student) {
    if (route === 'auth') {
      return (
        <>
          <Auth onAuthed={onAuthed} notify={notify} go={go} />
          <Toasts items={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
        </>
      )
    }
    return (
      <>
        <Landing go={go} />
        <Toasts items={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
      </>
    )
  }

  if (!student.onboarded) {
    return (
      <>
        <Onboarding student={student} onDone={onOnboarded} notify={notify} onLogout={logout} />
        <Toasts items={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
      </>
    )
  }

  const Page = PAGES[route] || Dashboard

  return (
    <>
      <Shell
        route={route}
        go={go}
        student={student}
        onLogout={logout}
        onOpenAdvisor={() => setAdvisorOpen(true)}
      >
        <Page
          key={`${route}-${refreshKey}`}
          go={go}
          notify={notify}
          refresh={refresh}
          student={student}
          onOpenAdvisor={() => setAdvisorOpen(true)}
        />
      </Shell>
      {advisorOpen && (
        <AdvisorPanel
          onClose={() => setAdvisorOpen(false)}
          notify={notify}
          onChanged={refresh}
          go={go}
        />
      )}
      <Toasts items={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
    </>
  )
}
