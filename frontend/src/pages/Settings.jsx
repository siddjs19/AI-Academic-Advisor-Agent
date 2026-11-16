import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, Pill, SectionHeading, Spinner } from '../components/ui'
import { cx } from '../lib'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const toMin = (t) => {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}
const toTime = (min) => `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`

export default function Settings({ student, notify, refresh }) {
  const [form, setForm] = useState({
    name: student.name,
    college: student.college,
    programme: student.programme,
    semester: student.semester,
    target_grade: student.target_grade,
    daily_minutes: student.daily_minutes,
  })
  const [windows, setWindows] = useState([])
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.availability().then((res) => {
      const byDay = new Map(res.windows.map((w) => [w.weekday, w]))
      setWindows(
        DAYS.map((_, weekday) => {
          const w = byDay.get(weekday)
          return {
            weekday,
            enabled: Boolean(w),
            start: toTime(w ? w.start_min : 18 * 60),
            end: toTime(w ? w.end_min : 22 * 60),
          }
        }),
      )
    })
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => {})
  }, [])

  const setWindow = (weekday, patch) =>
    setWindows((ws) => ws.map((w) => (w.weekday === weekday ? { ...w, ...patch } : w)))

  async function save() {
    setBusy(true)
    try {
      await api.onboarding({
        profile: { ...form, semester: Number(form.semester), daily_minutes: Number(form.daily_minutes) },
        windows: windows
          .filter((w) => w.enabled)
          .map((w) => ({ weekday: w.weekday, start_min: toMin(w.start), end_min: toMin(w.end) })),
      })
      notify('Saved. Rebuild the plan to apply the new availability.')
      refresh()
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const hours = windows
    .filter((w) => w.enabled)
    .reduce((s, w) => s + Math.max(0, toMin(w.end) - toMin(w.start)) / 60, 0)

  return (
    <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <div className="space-y-4">
        <Card className="p-5">
          <SectionHeading title="Profile" hint="used in prompts and on the dashboard" />
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ['name', 'Name'],
              ['college', 'College'],
              ['programme', 'Programme'],
              ['target_grade', 'Target grade'],
            ].map(([key, label]) => (
              <label key={key} className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">{label}</span>
                <input className="field" value={form[key] ?? ''} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
              </label>
            ))}
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Semester</span>
              <input type="number" min="1" max="12" className="field" value={form.semester}
                onChange={(e) => setForm({ ...form, semester: e.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">
                Daily limit — {form.daily_minutes}m
              </span>
              <input type="range" min="60" max="480" step="30" className="w-full accent-indigo-400"
                value={form.daily_minutes} onChange={(e) => setForm({ ...form, daily_minutes: Number(e.target.value) })} />
            </label>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeading title="Weekly availability" hint={`${Math.round(hours)}h a week — the only time the planner will use`} />
          <div className="space-y-1.5">
            {windows.map((w) => (
              <div key={w.weekday} className={cx('flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2',
                w.enabled ? 'border-white/[0.08] bg-white/[0.03]' : 'border-white/[0.04]')}>
                <label className="flex w-16 items-center gap-2">
                  <input type="checkbox" checked={w.enabled} onChange={(e) => setWindow(w.weekday, { enabled: e.target.checked })}
                    className="h-3.5 w-3.5 accent-indigo-400" />
                  <span className={cx('text-[12px]', w.enabled ? 'text-zinc-200' : 'text-zinc-500')}>{DAYS[w.weekday]}</span>
                </label>
                <input type="time" value={w.start} disabled={!w.enabled} className="field h-8 w-28 py-1"
                  onChange={(e) => setWindow(w.weekday, { start: e.target.value })} />
                <span className="text-zinc-600">→</span>
                <input type="time" value={w.end} disabled={!w.enabled} className="field h-8 w-28 py-1"
                  onChange={(e) => setWindow(w.weekday, { end: e.target.value })} />
              </div>
            ))}
          </div>
          <div className="mt-3 flex justify-end">
            <Button variant="primary" icon="check" onClick={save} disabled={busy}>
              {busy ? <Spinner className="h-4 w-4" /> : 'Save changes'}
            </Button>
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card className="p-5">
          <SectionHeading title="System" />
          <div className="space-y-2 text-[12px]">
            <Row label="API" value={health ? 'reachable' : 'checking…'} tone={health ? 'ok' : undefined} />
            <Row label="Model provider" value={health?.llm || '—'} tone={health?.llm_enabled ? 'ok' : 'warn'} />
            <Row label="Generation" value={health?.llm_enabled ? 'enabled' : 'offline mode'} tone={health?.llm_enabled ? 'ok' : 'warn'} />
            <Row label="Version" value={health?.version || '—'} />
          </div>
          {!health?.llm_enabled && (
            <p className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-amber-100/90">
              Without a model, explanations, generated questions and rubric grading are unavailable. The app says
              so instead of fabricating content. Set <code className="font-mono">LLM_PROVIDER</code> and{' '}
              <code className="font-mono">LLM_API_KEY</code> in the backend environment.
            </p>
          )}
        </Card>

        <Card className="p-5">
          <SectionHeading title="Your data" />
          <ul className="space-y-2 text-[11.5px] leading-relaxed text-zinc-400">
            <li className="flex gap-2">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
              Everything is stored against your account; no other student can read it.
            </li>
            <li className="flex gap-2">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
              Deleting a course removes its topics, assessments and blocks.
            </li>
            <li className="flex gap-2">
              <Icon name="alert" className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
              Marks and syllabi are personal data under India's DPDP Act — export or deletion tools are still
              on the roadmap.
            </li>
          </ul>
        </Card>

        <Card className="p-5">
          <SectionHeading title="Session" />
          <p className="text-[11.5px] leading-relaxed text-zinc-400">
            Signing out bumps a token counter on the server, so every token issued before now stops working —
            not just the one in this browser.
          </p>
          <Pill className="mt-2.5" tone="info">JWT + revocation counter</Pill>
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value, tone }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.04] pb-1.5 last:border-0">
      <span className="text-zinc-500">{label}</span>
      <span className={cx('font-medium', tone === 'ok' ? 'text-emerald-300' : tone === 'warn' ? 'text-amber-300' : 'text-zinc-300')}>
        {value}
      </span>
    </div>
  )
}
