import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, SectionHeading, Skeleton } from '../components/ui'
import { courseTone, cx, fmtTime, isoDay, minutesLabel, nextDays, splitLabel } from '../lib'

export default function Plan({ notify, refresh, go }) {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(null)
  const [weeks, setWeeks] = useState(1)

  async function load() {
    try {
      setData(await api.plan())
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function act(kind) {
    setBusy(kind)
    try {
      const res = kind === 'build' ? await api.buildPlan() : await api.replan()
      await load()
      refresh()
      notify(
        kind === 'build'
          ? `Plan built — ${res.blocks} blocks, ${res.required_hours}h of work in ${res.capacity_hours}h free.`
          : `Replanned — ${res.blocks_kept} kept, ${res.blocks_added} moved, ${res.missed_marked} marked missed.`,
      )
      if (res.notes?.length) notify(res.notes[0], res.status === 'ok' ? 'ok' : 'error')
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  async function log(id, done) {
    try {
      await api.logBlock(id, done)
      await load()
      refresh()
      notify(done ? 'Marked done.' : 'Marked skipped.')
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  if (!data) return <Skeleton className="h-96" />

  if (!data.plan) {
    return (
      <Card>
        <EmptyState
          icon="calendar"
          title="No plan yet"
          body="Once you have courses and free time, the solver places every topic before its exam — respecting your daily cap and prerequisites."
          action={
            <Button variant="primary" icon="sparkles" onClick={() => act('build')} disabled={busy}>
              {busy ? 'Solving…' : 'Build my plan'}
            </Button>
          }
        />
      </Card>
    )
  }

  const days = nextDays(7 * weeks)
  const byDay = days.map((d) => ({
    day: d,
    blocks: data.blocks
      .filter((b) => b.start.slice(0, 10) === isoDay(d))
      .sort((a, b) => a.start.localeCompare(b.start)),
  }))

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div>
            <div className="text-[10.5px] uppercase tracking-wider text-zinc-500">Status</div>
            <div className="mt-1 flex items-center gap-2">
              <Pill tone={data.plan.status === 'ok' ? 'ok' : data.plan.status === 'partial' ? 'warn' : 'bad'}>
                {data.plan.status}
              </Pill>
              <span className="text-[11px] text-zinc-500">run #{data.plan.plan_run_id}</span>
            </div>
          </div>
          <div className="h-8 w-px bg-white/[0.07]" />
          <div>
            <div className="text-[10.5px] uppercase tracking-wider text-zinc-500">Work vs free time</div>
            <div className="mt-1 text-[12.5px] text-zinc-200">
              {data.plan.required_hours}h needed · {data.plan.capacity_hours}h available
            </div>
          </div>
          <div className="h-8 w-px bg-white/[0.07]" />
          <div>
            <div className="text-[10.5px] uppercase tracking-wider text-zinc-500">Blocks</div>
            <div className="mt-1 text-[12.5px] tabular-nums text-zinc-200">{data.blocks.length}</div>
          </div>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setWeeks(weeks === 1 ? 2 : 1)}>
              {weeks === 1 ? 'Show 2 weeks' : 'Show 1 week'}
            </Button>
            <Button size="sm" variant="ghost" icon="bolt" onClick={() => act('replan')} disabled={busy}>
              Replan
            </Button>
            <Button size="sm" variant="primary" icon="sparkles" onClick={() => act('build')} disabled={busy}>
              {busy === 'build' ? 'Solving…' : 'Rebuild'}
            </Button>
          </div>
        </div>

        {data.plan.notes?.length > 0 && (
          <div className="mt-3 space-y-1 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-[12px] leading-relaxed text-amber-100/90">
            {data.plan.notes.map((n, i) => (
              <p key={i} className="flex gap-2">
                <Icon name="alert" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
                {n}
              </p>
            ))}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {byDay.map(({ day, blocks }) => {
          const today = isoDay(day) === isoDay(new Date())
          return (
            <div
              key={isoDay(day)}
              className={cx(
                'flex min-h-[200px] flex-col rounded-xl border p-2',
                today ? 'border-indigo-400/30 bg-indigo-400/[0.05]' : 'border-white/[0.06] bg-ink-950/30',
              )}
            >
              <div className="mb-2 flex items-baseline justify-between px-1">
                <div>
                  <div className={cx('text-[10.5px] uppercase tracking-wide', today ? 'text-indigo-300' : 'text-zinc-500')}>
                    {day.toLocaleDateString('en-IN', { weekday: 'short' })}
                  </div>
                  <div className="text-[14px] font-semibold tabular-nums text-zinc-200">{day.getDate()}</div>
                </div>
                {blocks.length > 0 && (
                  <span className="text-[10px] text-zinc-500">
                    {minutesLabel(blocks.reduce((s, b) => s + b.minutes, 0))}
                  </span>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-1.5">
                {blocks.length === 0 && (
                  <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-white/[0.06] text-[10px] text-zinc-600">
                    free
                  </div>
                )}
                {blocks.map((b) => {
                  const { course, topic } = splitLabel(b.label)
                  const tone = courseTone(course)
                  return (
                    <div key={b.id} className={cx('group relative overflow-hidden rounded-lg border-l-2 bg-white/[0.03] p-2 hover:bg-white/[0.06]', tone.border)}>
                      <div className="text-[10px] tabular-nums text-zinc-500">{fmtTime(b.start)}</div>
                      <div className="mt-0.5 line-clamp-2 text-[11.5px] font-medium leading-snug text-zinc-100">{topic}</div>
                      <div className="mt-1 flex items-center gap-1 text-[10px] text-zinc-500">
                        <span className={cx('h-1 w-1 rounded-full', tone.dot)} />
                        {minutesLabel(b.minutes)}
                      </div>
                      <div className="absolute inset-x-1 bottom-1 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <button onClick={() => log(b.id, true)} className="flex-1 rounded bg-emerald-400/15 py-0.5 text-[10px] text-emerald-300 hover:bg-emerald-400/25">
                          done
                        </button>
                        <button onClick={() => log(b.id, false)} className="flex-1 rounded bg-white/[0.06] py-0.5 text-[10px] text-zinc-400 hover:bg-white/[0.1]">
                          skip
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <Card className="p-4">
        <SectionHeading title="How this schedule was produced" hint="the constraints that were enforced" />
        <div className="grid gap-3 text-[12px] leading-relaxed text-zinc-400 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Daily cap', 'Never more than your configured daily minutes, whatever is left.'],
            ['Prerequisites', 'A topic is never scheduled before the topic it depends on.'],
            ['Deadlines', 'Nothing is placed after the assessment that covers it.'],
            ['Stability', 'Replans keep existing blocks where they can, so the calendar does not churn.'],
          ].map(([title, body]) => (
            <div key={title}>
              <div className="flex items-center gap-1.5 text-[12px] font-medium text-zinc-200">
                <Icon name="check" className="h-3 w-3 text-emerald-400" />
                {title}
              </div>
              <p className="mt-1 text-zinc-500">{body}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
