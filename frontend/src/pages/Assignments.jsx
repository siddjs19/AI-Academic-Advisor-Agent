import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, Progress, SectionHeading, Spinner } from '../components/ui'
import { cx, relativeDays } from '../lib'

const KINDS = ['assignment', 'project', 'lab', 'presentation']

export default function Assignments({ notify }) {
  const [items, setItems] = useState(null)
  const [courses, setCourses] = useState([])
  const [form, setForm] = useState({ title: '', kind: 'assignment', course_id: '', due_at: '', notes: '' })
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)

  async function load() {
    try {
      const [a, c] = await Promise.all([api.assignments(), api.courses()])
      setItems(a.assignments)
      setCourses(c.courses)
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function create(e) {
    e.preventDefault()
    if (!form.title.trim()) return notify('Give it a title', 'error')
    setBusy(true)
    try {
      const res = await api.createAssignment({
        title: form.title,
        kind: form.kind,
        course_id: form.course_id ? Number(form.course_id) : null,
        due_at: form.due_at ? new Date(form.due_at).toISOString().slice(0, 19) : null,
        weight_pct: 0,
        notes: form.notes,
      })
      notify(`Added — broken into ${res.tasks} tasks.`)
      setForm({ title: '', kind: 'assignment', course_id: '', due_at: '', notes: '' })
      setOpen(false)
      await load()
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function toggle(assignment, task) {
    try {
      await api.toggleTask(assignment.id, task.id)
      await load()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  async function remove(assignment) {
    if (!window.confirm(`Delete "${assignment.title}"?`)) return
    try {
      await api.deleteAssignment(assignment.id)
      await load()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-[16px] font-semibold text-zinc-100">Assignments & projects</h1>
          <p className="text-[12px] text-zinc-500">Broken into tasks the moment you add them.</p>
        </div>
        <Button size="sm" variant="primary" icon="plus" onClick={() => setOpen((o) => !o)}>
          New item
        </Button>
      </div>

      {open && (
        <Card className="p-4">
          <form onSubmit={create} className="grid gap-2.5 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Title</span>
              <input className="field" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="DBMS lab file — transactions" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Type</span>
              <select className="field" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                {KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Course</span>
              <select className="field" value={form.course_id} onChange={(e) => setForm({ ...form, course_id: e.target.value })}>
                <option value="">—</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Due</span>
              <input type="datetime-local" className="field" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Brief (optional)</span>
              <input className="field" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="what has to be submitted" />
            </label>
            <div className="sm:col-span-2 flex justify-end gap-2">
              <Button type="button" variant="subtle" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : 'Add and decompose'}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {!items ? (
        <Card className="p-10 text-center text-[12.5px] text-zinc-500">Loading…</Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon="check"
            title="Nothing open"
            body="Add an assignment and it is split into concrete tasks with time estimates — the kind of thing you can actually schedule."
            action={<Button variant="primary" icon="plus" onClick={() => setOpen(true)}>Add one</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {items.map((a) => {
            const overdue = a.due_at && new Date(a.due_at) < new Date() && a.progress.pct < 100
            return (
              <Card key={a.id} className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-medium text-zinc-100">{a.title}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-500">
                      <Pill>{a.kind}</Pill>
                      {a.course && <span>{a.course}</span>}
                      {a.due_at && (
                        <span className={cx(overdue && 'text-rose-300')}>· due {relativeDays(a.due_at)}</span>
                      )}
                    </div>
                  </div>
                  <button onClick={() => remove(a)} className="rounded p-1 text-zinc-600 hover:text-rose-300">
                    <Icon name="x" className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="mt-3">
                  <div className="flex items-center justify-between text-[10.5px] text-zinc-500">
                    <span>{a.progress.done}/{a.progress.tasks} tasks</span>
                    <span>{a.progress.minutes_left} min left</span>
                  </div>
                  <Progress value={a.progress.pct} className="mt-1" />
                </div>

                <div className="mt-3 space-y-1">
                  {a.tasks.map((t) => (
                    <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 hover:bg-white/[0.03]">
                      <input
                        type="checkbox"
                        checked={t.done}
                        onChange={() => toggle(a, t)}
                        className="h-3.5 w-3.5 accent-indigo-400"
                      />
                      <span className={cx('min-w-0 flex-1 truncate text-[11.5px]', t.done ? 'text-zinc-500 line-through' : 'text-zinc-300')}>
                        {t.title}
                      </span>
                      <span className="text-[10px] text-zinc-600">{t.est_minutes}m</span>
                    </label>
                  ))}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
