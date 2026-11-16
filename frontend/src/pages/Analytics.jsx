import { useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import Icon from '../components/Icons'
import { Card, Pill, Progress, SectionHeading, Skeleton, Stat } from '../components/ui'
import { COURSE_TONES, cx } from '../lib'

const TOOLTIP = {
  contentStyle: {
    background: '#0f1118',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    fontSize: 12,
    color: '#e4e4e7',
  },
  labelStyle: { color: '#a1a1aa', fontSize: 11 },
}

export default function Analytics({ notify }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    api
      .analytics()
      .then(setData)
      .catch((err) => notify(err.message, 'error'))
  }, [])

  if (!data) return <Skeleton className="h-96" />

  const series = data.accuracy_series.map((p, i) => ({
    name: `#${i + 1}`,
    accuracy: p.accuracy,
  }))

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Attempts" value={data.attempts} sub={`last ${data.window_days} days`} icon="target" />
        <Stat
          label="Study adherence"
          value={data.study.adherence_pct === null ? '—' : `${data.study.adherence_pct}%`}
          sub={`${data.study.completed_hours}h of ${data.study.planned_hours}h elapsed`}
          icon="calendar"
        />
        <Stat
          label="Revision retention"
          value={data.revision.retention_pct === null ? '—' : `${data.revision.retention_pct}%`}
          sub={`${data.revision.reviews} reviews · ${data.revision.due_now} due`}
          icon="refresh"
        />
        <Stat label="Courses tracked" value={data.courses.length} sub={`${data.courses.reduce((s, c) => s + c.topics, 0)} topics`} icon="book" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card className="p-5">
          <SectionHeading title="Accuracy over time" hint="each point is one submitted attempt" />
          {series.length === 0 ? (
            <p className="py-14 text-center text-[12.5px] text-zinc-500">
              No attempts yet — take a practice set and this fills in.
            </p>
          ) : (
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="acc" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#818cf8" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#818cf8" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#71717a', fontSize: 10 }} stroke="rgba(255,255,255,0.08)" />
                  <YAxis domain={[0, 100]} tick={{ fill: '#71717a', fontSize: 10 }} stroke="rgba(255,255,255,0.08)" />
                  <Tooltip {...TOOLTIP} />
                  <Area type="monotone" dataKey="accuracy" stroke="#818cf8" strokeWidth={2} fill="url(#acc)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionHeading title="Mastery by course" hint="weighted across topics, from evidence" />
          {data.courses.length === 0 ? (
            <p className="py-10 text-center text-[12.5px] text-zinc-500">No courses yet.</p>
          ) : (
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.courses.map((c) => ({ name: c.code || c.course.slice(0, 8), mastery: c.mastery }))}
                  margin={{ top: 6, right: 8, left: -22, bottom: 0 }}
                >
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#71717a', fontSize: 10 }} stroke="rgba(255,255,255,0.08)" />
                  <YAxis domain={[0, 100]} tick={{ fill: '#71717a', fontSize: 10 }} stroke="rgba(255,255,255,0.08)" />
                  <Tooltip {...TOOLTIP} />
                  <Bar dataKey="mastery" radius={[4, 4, 0, 0]} fill="#a78bfa" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeading title="Weak topics" hint="below 60% mastery, ranked by weight × gap" />
          {data.weak_topics.length === 0 ? (
            <p className="py-6 text-center text-[12.5px] text-zinc-500">Nothing below the threshold.</p>
          ) : (
            <div className="space-y-2.5">
              {data.weak_topics.map((w) => (
                <div key={w.topic_id}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[12px] text-zinc-200">{w.topic}</span>
                    <span className="text-[11px] tabular-nums text-zinc-400">{Math.round(w.mastery * 100)}%</span>
                  </div>
                  <Progress
                    value={w.mastery * 100}
                    tone={w.mastery < 0.3 ? 'bg-rose-400' : w.mastery < 0.45 ? 'bg-amber-400' : 'bg-emerald-400'}
                    className="mt-1"
                  />
                  <div className="mt-0.5 text-[10.5px] text-zinc-500">
                    {w.course} · {w.weight_pct}% weight · {w.evidence.attempts} attempts
                    {w.evidence.confident ? ' · confident' : ' · low confidence'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionHeading title="Repeated mistakes" hint="same topic missed more than once" />
          {data.repeated_mistakes.length === 0 ? (
            <p className="py-6 text-center text-[12.5px] text-zinc-500">No repeated misses — or no attempts yet.</p>
          ) : (
            <div className="space-y-2">
              {data.repeated_mistakes.map((m) => (
                <div key={m.topic_id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[12px] text-zinc-200">{m.topic}</span>
                    <Pill tone="bad">{m.misses} misses</Pill>
                  </div>
                  <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-zinc-500">
                    {m.questions[0]}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeading title="Per-course detail" hint="assessed topics vs total" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-[12px]">
            <thead>
              <tr className="border-b border-white/[0.06] text-[10.5px] uppercase tracking-wider text-zinc-500">
                <th className="py-2 font-medium">Course</th>
                <th className="py-2 font-medium">Mastery</th>
                <th className="py-2 font-medium">Assessed</th>
                <th className="py-2 font-medium">Hours left</th>
              </tr>
            </thead>
            <tbody>
              {data.courses.map((c, i) => (
                <tr key={c.course_id} className="border-b border-white/[0.04] last:border-0">
                  <td className="py-2">
                    <div className="flex items-center gap-1.5">
                      <span className={cx('h-1.5 w-1.5 rounded-full', COURSE_TONES[i % COURSE_TONES.length].dot)} />
                      <span className="text-zinc-200">{c.course}</span>
                    </div>
                  </td>
                  <td className="py-2 tabular-nums text-zinc-300">{c.mastery}%</td>
                  <td className="py-2 tabular-nums text-zinc-400">
                    {c.assessed_topics}/{c.topics}
                  </td>
                  <td className="py-2 tabular-nums text-zinc-400">{c.hours_left}h</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-zinc-500">
          <Icon name="alert" className="mt-0.5 h-3 w-3 shrink-0" />
          Mastery is an estimate from evidence, not a grade prediction. A single correct answer never marks a
          topic as known.
        </p>
      </Card>
    </div>
  )
}
