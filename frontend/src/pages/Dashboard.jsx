import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, Progress, SectionHeading, Skeleton, Stat } from '../components/ui'
import { COURSE_TONES, courseTone, cx, fmtTime, minutesLabel, relativeDays, splitLabel } from '../lib'

const SEVERITY = {
  critical: { tone: 'bad', ring: 'border-rose-400/25 bg-rose-500/[0.07]', icon: 'alert', text: 'text-rose-300' },
  warn: { tone: 'warn', ring: 'border-amber-400/25 bg-amber-400/[0.06]', icon: 'alert', text: 'text-amber-300' },
  info: { tone: 'info', ring: 'border-white/[0.08] bg-white/[0.025]', icon: 'sparkles', text: 'text-indigo-300' },
}

const ACTION_LABEL = {
  build_plan: 'Rebuild plan',
  replan: 'Replan',
  start_quiz: 'Practise this',
  open_revision: 'Review cards',
  open_assignment: 'Open',
  open_practice: 'Start practice',
}

export default function Dashboard({ go, notify, refresh }) {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      setData(await api.dashboard())
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function runAction(rec) {
    setBusy(true)
    try {
      await api.actOnRecommendation(rec.id, 'accepted')
      const type = rec.action?.type
      if (type === 'build_plan') {
        const res = await api.buildPlan()
        notify(`Plan rebuilt — ${res.blocks} blocks.`)
        await load()
        refresh()
      } else if (type === 'replan') {
        const res = await api.replan()
        notify(`Replanned — ${res.blocks_added} blocks moved.`)
        await load()
        refresh()
      } else if (type === 'start_quiz' || type === 'open_practice') {
        go('practice')
      } else if (type === 'open_revision') {
        go('revision')
      } else if (type === 'open_assignment') {
        go('assignments')
      } else {
        await load()
      }
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function dismiss(rec) {
    try {
      await api.actOnRecommendation(rec.id, 'dismissed')
      setData((d) => ({ ...d, recommendations: d.recommendations.filter((r) => r.id !== rec.id) }))
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  async function logBlock(id, done) {
    setBusy(true)
    try {
      await api.logBlock(id, done)
      await load()
      notify(done ? 'Marked done.' : 'Marked skipped — replan when you want to catch up.')
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[86px]" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  const { stats, readiness, weak_topics: weak, today_blocks: today, deadlines, recommendations, next_block: next } = data
  const weakest = readiness.length ? readiness.reduce((a, b) => (a.readiness <= b.readiness ? a : b)) : null

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[19px] font-semibold tracking-tight text-zinc-100">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'},{' '}
            {data.student.name.split(' ')[0]}
          </h1>
          <p className="mt-0.5 text-[12.5px] text-zinc-500">
            {data.student.programme} · semester {data.student.semester} · target {data.student.target_grade}
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" icon="chat" onClick={() => go('tutor')}>
            Ask a doubt
          </Button>
          <Button size="sm" variant="primary" icon="target" onClick={() => go('practice')}>
            Practise
          </Button>
        </div>
      </div>

      {!data.llm.enabled && (
        <Card className="border-amber-400/20 bg-amber-400/[0.05] p-3.5">
          <div className="flex gap-2.5">
            <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div className="text-[12px] leading-relaxed text-amber-100/90">
              <span className="font-medium">Offline mode.</span> No model is configured, so explanations and
              generated questions are unavailable — the app will say so rather than invent content. Planning,
              grading of objective questions, spaced repetition and analytics all work fully. Set{' '}
              <code className="rounded bg-black/30 px-1 py-0.5 font-mono text-[11px]">LLM_PROVIDER</code> and{' '}
              <code className="rounded bg-black/30 px-1 py-0.5 text-[11px]">LLM_API_KEY</code> to enable generation.
            </div>
          </div>
        </Card>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Readiness" value={`${stats.readiness}%`} sub={weakest ? `weakest: ${weakest.code}` : 'no courses yet'} icon="target"
          tone={stats.readiness >= 65 ? 'text-emerald-300' : stats.readiness >= 40 ? 'text-amber-300' : 'text-rose-300'} />
        <Stat label="Work vs time" value={`${stats.required_hours}h`} sub={`${stats.capacity_hours}h free · ${stats.blocks} blocks`} icon="calendar" />
        <Stat label="Cards due" value={stats.due_cards} sub={`${stats.attempts} attempts logged`} icon="refresh" />
        <Stat label="Open tasks" value={stats.open_assignments} sub={stats.adherence_pct === null ? 'no history yet' : `${stats.adherence_pct}% adherence`} icon="check" />
      </div>

      {recommendations.length > 0 && (
        <div className="space-y-2">
          <SectionHeading title="Your advisor noticed" hint="generated from your own data, not a content calendar" />
          {recommendations.map((rec) => {
            const sev = SEVERITY[rec.severity] || SEVERITY.info
            return (
              <div key={rec.id} className={cx('rounded-xl border p-3.5', sev.ring)}>
                <div className="flex flex-wrap items-start gap-3">
                  <Icon name={sev.icon} className={cx('mt-0.5 h-4 w-4 shrink-0', sev.text)} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-zinc-100">{rec.title}</div>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-zinc-400">{rec.body}</p>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => runAction(rec)} disabled={busy}>
                      {ACTION_LABEL[rec.action?.type] || 'Open'}
                    </Button>
                    <Button size="sm" variant="subtle" onClick={() => dismiss(rec)}>
                      Dismiss
                    </Button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="p-5">
          <SectionHeading
            title="Today"
            hint={today.length ? `${today.reduce((s, b) => s + b.minutes, 0) / 60}h scheduled` : 'nothing scheduled'}
            action={next ? <Pill tone="info">next {fmtTime(next.start)}</Pill> : null}
          />
          {today.length === 0 ? (
            <p className="py-8 text-center text-[12.5px] text-zinc-500">
              A clear day. Ask the planner for a rebuild if you want work placed today.
            </p>
          ) : (
            <div className="space-y-1">
              {today.map((b) => {
                const { course, topic } = splitLabel(b.label)
                const tone = courseTone(course)
                return (
                  <div key={b.id} className="group flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/[0.03]">
                    <span className="w-14 shrink-0 text-right text-[11px] tabular-nums text-zinc-500">{fmtTime(b.start)}</span>
                    <span className={cx('h-8 w-0.5 rounded-full', tone.bar)} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12.5px] text-zinc-100">{topic}</div>
                      <div className="text-[11px] text-zinc-500">{course} · {minutesLabel(b.minutes)}</div>
                    </div>
                    <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      <button onClick={() => logBlock(b.id, true)} disabled={busy} className="rounded border border-emerald-400/25 bg-emerald-400/10 p-1 text-emerald-300">
                        <Icon name="check" className="h-3 w-3" />
                      </button>
                      <button onClick={() => logBlock(b.id, false)} disabled={busy} className="rounded border border-white/10 p-1 text-zinc-400">
                        <Icon name="x" className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionHeading title="Readiness by course" hint="weighted mastery against the next exam" />
          <div className="space-y-3">
            {readiness.length === 0 && <EmptyState icon="book" title="No courses yet" body="Upload a syllabus to get started." action={<Button size="sm" variant="primary" onClick={() => go('subjects')}>Add a syllabus</Button>} />}
            {readiness.map((r, i) => {
              const tone = COURSE_TONES[i % COURSE_TONES.length]
              return (
                <div key={r.course_id}>
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-[12.5px] text-zinc-200">{r.course}</div>
                      <div className="text-[11px] text-zinc-500">
                        {r.exam_title ? `${r.exam_title} · ${relativeDays(r.exam_at)}` : 'no exam scheduled'}
                      </div>
                    </div>
                    <span className="text-[12px] tabular-nums text-zinc-300">{r.readiness}%</span>
                  </div>
                  <Progress value={r.readiness} tone={tone.bar} className="mt-1.5" />
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card className="p-5">
          <SectionHeading title="Weakest topics" hint="mastery below 60%, ranked by weight × gap" action={<Button size="sm" variant="subtle" onClick={() => go('analytics')}>All</Button>} />
          <div className="space-y-2">
            {weak.length === 0 && <p className="py-6 text-center text-[12.5px] text-zinc-500">Nothing flagged — take a practice set to build evidence.</p>}
            {weak.map((w) => (
              <div key={w.topic_id} className="flex items-center gap-2.5 rounded-lg bg-white/[0.02] px-2.5 py-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] text-zinc-200">{w.topic}</div>
                  <div className="text-[11px] text-zinc-500">
                    {w.course} · {w.weight_pct}% weight · {w.evidence.attempts} attempts
                  </div>
                </div>
                <span className={cx('text-[12px] tabular-nums', w.mastery < 0.35 ? 'text-rose-300' : 'text-amber-300')}>
                  {Math.round(w.mastery * 100)}%
                </span>
                <Button size="sm" variant="subtle" onClick={() => go('practice')}>
                  drill
                </Button>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeading title="Deadlines" hint="next six graded events" />
          <div className="space-y-1.5">
            {deadlines.length === 0 && <p className="py-6 text-center text-[12.5px] text-zinc-500">No upcoming assessments.</p>}
            {deadlines.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5">
                <div className="min-w-0">
                  <div className="truncate text-[12.5px] text-zinc-200">{d.title}</div>
                  <div className="text-[11px] text-zinc-500">{d.code || d.course} · {d.weight_pct}%</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[11.5px] text-zinc-300">{relativeDays(d.due_at)}</div>
                  <div className={cx('text-[10.5px]', d.days_left <= 3 ? 'text-rose-300' : d.days_left <= 7 ? 'text-amber-300' : 'text-zinc-500')}>
                    {d.days_left}d left
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
