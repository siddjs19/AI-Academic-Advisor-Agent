import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, Spinner } from '../components/ui'
import { cx } from '../lib'

export default function Auth({ onAuthed, notify, go }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [demo, setDemo] = useState(null)

  useEffect(() => {
    api.demo().then(setDemo).catch(() => setDemo(null))
  }, [])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result =
        mode === 'login' ? await api.login(email, password) : await api.register(email, password, name)
      notify(mode === 'login' ? 'Signed in.' : 'Account created.')
      onAuthed(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function useDemo() {
    if (!demo) return
    setBusy(true)
    setError('')
    try {
      const result = await api.login(demo.email, demo.password)
      onAuthed(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between border-r border-white/[0.06] bg-ink-950/40 p-10 lg:flex">
        <button onClick={() => go('landing')} className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
            <Icon name="bolt" className="h-4 w-4" strokeWidth={2.2} />
          </div>
          <span className="text-[14px] font-semibold tracking-tight">PrepPilot AI</span>
        </button>

        <div className="max-w-md">
          <h2 className="text-[26px] font-semibold leading-tight tracking-tight text-white">
            Your syllabus, your marks, your week — joined up.
          </h2>
          <p className="mt-4 text-[13.5px] leading-relaxed text-zinc-400">
            Every screen is backed by one shared memory: topics, assessments, attempts, mistakes and revision
            state. That is why the tutor knows what you failed, and the planner knows what you have not studied.
          </p>
          <div className="mt-7 space-y-3">
            {[
              ['Solver-first planning', 'OR-Tools CP-SAT, not a prompt'],
              ['Evidence-based mastery', 'attempts × difficulty × recency'],
              ['Proactive nudges', 'from real events, never filler'],
            ].map(([title, sub]) => (
              <div key={title} className="flex items-start gap-2.5">
                <Icon name="check" className="mt-0.5 h-3.5 w-3.5 text-emerald-400" />
                <div>
                  <div className="text-[12.5px] text-zinc-200">{title}</div>
                  <div className="text-[11.5px] text-zinc-500">{sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-zinc-600">FastAPI · OR-Tools · React · SQLite/Postgres</p>
      </div>

      <div className="flex w-full items-center justify-center p-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] p-1">
            {[
              ['login', 'Sign in'],
              ['register', 'Create account'],
            ].map(([id, label]) => (
              <button
                key={id}
                onClick={() => {
                  setMode(id)
                  setError('')
                }}
                className={cx(
                  'flex-1 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition-colors',
                  mode === id ? 'bg-white/[0.08] text-white' : 'text-zinc-400 hover:text-zinc-200',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === 'register' && (
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Name</span>
                <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" required />
              </label>
            )}
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Email</span>
              <input
                className="field"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@college.edu"
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Password</span>
              <input
                className="field"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="at least 8 characters"
                minLength={8}
                required
              />
            </label>

            {error && (
              <div className="rounded-lg border border-rose-400/25 bg-rose-500/10 px-3 py-2 text-[12px] text-rose-200">
                {error}
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full" disabled={busy}>
              {busy ? <Spinner className="h-4 w-4" /> : mode === 'login' ? 'Sign in' : 'Create account'}
            </Button>
          </form>

          {demo?.enabled && (
            <Card className="mt-5 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-zinc-500">Demo account</div>
              <div className="mt-1 font-mono text-[11.5px] text-zinc-300">
                {demo.email} · {demo.password}
              </div>
              <Button size="sm" variant="ghost" className="mt-2.5 w-full" onClick={useDemo} disabled={busy}>
                Sign in as the demo student
              </Button>
            </Card>
          )}

          <button onClick={() => go('landing')} className="mt-6 w-full text-center text-[11.5px] text-zinc-500 hover:text-zinc-300">
            ← back to the overview
          </button>
        </div>
      </div>
    </div>
  )
}
