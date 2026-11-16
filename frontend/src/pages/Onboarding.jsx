import { useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, Spinner } from '../components/ui'
import { cx } from '../lib'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const toMin = (t) => {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

export default function Onboarding({ student, onDone, notify, onLogout }) {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    name: student?.name || '',
    college: student?.college || '',
    programme: student?.programme || 'B.E. Computer Engineering',
    semester: student?.semester || 1,
    target_grade: student?.target_grade || '8.5 CGPA',
    daily_minutes: student?.daily_minutes || 240,
  })
  const [windows, setWindows] = useState(
    [0, 1, 2, 3, 4].map((d) => ({ weekday: d, enabled: true, start: '18:00', end: '22:00' }))
      .concat([{ weekday: 5, enabled: true, start: '09:00', end: '13:00' }, { weekday: 6, enabled: false, start: '09:00', end: '13:00' }]),
  )
  const [busy, setBusy] = useState(false)

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))
  const setWindow = (weekday, patch) =>
    setWindows((ws) => ws.map((w) => (w.weekday === weekday ? { ...w, ...patch } : w)))

  const totalHours = windows
    .filter((w) => w.enabled)
    .reduce((sum, w) => sum + Math.max(0, toMin(w.end) - toMin(w.start)) / 60, 0)

  async function finish() {
    setBusy(true)
    try {
      const result = await api.onboarding({
        profile: { ...form, semester: Number(form.semester), daily_minutes: Number(form.daily_minutes) },
        windows: windows
          .filter((w) => w.enabled)
          .map((w) => ({ weekday: w.weekday, start_min: toMin(w.start), end_min: toMin(w.end) })),
      })
      notify('Profile saved. Upload a syllabus to get your first plan.')
      onDone(result.student)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-5 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
            <Icon name="bolt" className="h-4 w-4" strokeWidth={2.2} />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-zinc-100">Set up your profile</div>
            <div className="text-[11px] text-zinc-500">Step {step + 1} of 2</div>
          </div>
        </div>
        <button onClick={onLogout} className="text-[11.5px] text-zinc-500 hover:text-zinc-300">
          Sign out
        </button>
      </div>

      <Card className="p-6">
        {step === 0 ? (
          <div className="space-y-4">
            <h2 className="text-[16px] font-semibold text-zinc-100">Who are we planning for?</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Name</span>
                <input className="field" value={form.name} onChange={(e) => set('name', e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">College</span>
                <input className="field" value={form.college} onChange={(e) => set('college', e.target.value)} placeholder="VJTI, Mumbai" />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Programme</span>
                <input className="field" value={form.programme} onChange={(e) => set('programme', e.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Semester</span>
                <input
                  className="field"
                  type="number"
                  min="1"
                  max="12"
                  value={form.semester}
                  onChange={(e) => set('semester', e.target.value)}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Target grade</span>
                <input className="field" value={form.target_grade} onChange={(e) => set('target_grade', e.target.value)} />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">
                  Daily study limit — {form.daily_minutes} minutes
                </span>
                <input
                  type="range"
                  min="60"
                  max="480"
                  step="30"
                  value={form.daily_minutes}
                  onChange={(e) => set('daily_minutes', Number(e.target.value))}
                  className="w-full accent-indigo-400"
                />
                <span className="text-[11px] text-zinc-500">
                  The solver never schedules more than this in a day, however much is left.
                </span>
              </label>
            </div>
            <div className="flex justify-end">
              <Button variant="primary" icon="arrowRight" onClick={() => setStep(1)}>
                Next
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <h2 className="text-[16px] font-semibold text-zinc-100">When are you actually free?</h2>
              <p className="mt-1 text-[12.5px] text-zinc-500">
                These windows are the only place the planner will put work — {Math.round(totalHours)}h a week.
              </p>
            </div>
            <div className="space-y-1.5">
              {windows.map((w) => (
                <div
                  key={w.weekday}
                  className={cx(
                    'flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2',
                    w.enabled ? 'border-white/[0.08] bg-white/[0.03]' : 'border-white/[0.04] bg-transparent',
                  )}
                >
                  <label className="flex w-20 items-center gap-2">
                    <input
                      type="checkbox"
                      checked={w.enabled}
                      onChange={(e) => setWindow(w.weekday, { enabled: e.target.checked })}
                      className="h-3.5 w-3.5 accent-indigo-400"
                    />
                    <span className={cx('text-[12.5px]', w.enabled ? 'text-zinc-200' : 'text-zinc-500')}>{DAYS[w.weekday]}</span>
                  </label>
                  <input
                    type="time"
                    value={w.start}
                    disabled={!w.enabled}
                    onChange={(e) => setWindow(w.weekday, { start: e.target.value })}
                    className="field h-8 w-28 py-1"
                  />
                  <span className="text-zinc-600">→</span>
                  <input
                    type="time"
                    value={w.end}
                    disabled={!w.enabled}
                    onChange={(e) => setWindow(w.weekday, { end: e.target.value })}
                    className="field h-8 w-28 py-1"
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button variant="primary" icon="check" onClick={finish} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : 'Finish setup'}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <p className="mt-4 text-center text-[11px] text-zinc-600">
        You can change all of this later in Settings.
      </p>
    </div>
  )
}
