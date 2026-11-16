import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, Progress, SectionHeading, Skeleton, Spinner } from '../components/ui'
import { COURSE_TONES, cx, fmtDay, relativeDays } from '../lib'

const SAMPLE = `CS307 Theory of Computation
Unit 1: Finite automata and regular languages (25%)
Unit 2: Context free grammars and pushdown automata (25%)
Unit 3: Turing machines and decidability (30%)
Unit 4: Complexity classes (20%)
Mid-semester exam: 01/12/2026
End-semester exam: 22/12/2026`

export default function Subjects({ notify, refresh }) {
  const [courses, setCourses] = useState(null)
  const [stage, setStage] = useState('list') // list | input | review
  const [draft, setDraft] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(null)
  const fileRef = useRef(null)

  async function load() {
    try {
      const res = await api.courses()
      setCourses(res.courses)
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function parseFile(file) {
    if (!file) return
    setBusy(true)
    try {
      const res = await api.parseSyllabusFile(file)
      setDraft(res.draft)
      setStage('review')
      notify(`Parsed ${res.draft.topics.length} topics from ${file.name}`)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function parseText() {
    if (!text.trim()) return notify('Paste a syllabus first', 'error')
    setBusy(true)
    try {
      const res = await api.parseSyllabusText(text)
      setDraft(res.draft)
      setStage('review')
      notify(`Parsed ${res.draft.topics.length} topics`)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    setBusy(true)
    try {
      const res = await api.confirmSyllabus(draft)
      notify(`${res.course} imported — ${res.topics} topics, ${res.assessments} assessments.`)
      setStage('list')
      setDraft(null)
      setText('')
      await load()
      refresh()
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function remove(course) {
    if (!window.confirm(`Delete ${course.name} and all of its topics?`)) return
    try {
      await api.deleteCourse(course.id)
      notify('Course deleted.')
      await load()
      refresh()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  const patchTopic = (i, key, value) =>
    setDraft((d) => ({ ...d, topics: d.topics.map((t, idx) => (idx === i ? { ...t, [key]: value } : t)) }))
  const removeTopic = (i) => setDraft((d) => ({ ...d, topics: d.topics.filter((_, idx) => idx !== i) }))

  // ------------------------------------------------------------------ review
  if (stage === 'review' && draft) {
    const flagged = draft.topics.filter((t) => t.needs_review).length
    return (
      <div className="space-y-4 pb-20">
        <Card className="p-5">
          <SectionHeading
            title="Review the extraction"
            hint="fix anything wrong — especially dates, they become hard deadlines"
            action={<Pill tone={flagged ? 'warn' : 'ok'}>{flagged} flagged</Pill>}
          />
          {draft.warnings?.length > 0 && (
            <div className="mb-3 space-y-1 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-[12px] text-amber-100/90">
              {draft.warnings.map((w, i) => (
                <p key={i}>• {w}</p>
              ))}
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Course name</span>
              <input
                className="field"
                value={draft.course.name}
                onChange={(e) => setDraft({ ...draft, course: { ...draft.course, name: e.target.value } })}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Code</span>
              <input
                className="field"
                value={draft.course.code || ''}
                onChange={(e) => setDraft({ ...draft, course: { ...draft.course, code: e.target.value } })}
              />
            </label>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <div className="px-5 py-4">
            <SectionHeading title={`Topics (${draft.topics.length})`} hint="hours are self-study effort" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-[12.5px]">
              <thead>
                <tr className="border-y border-white/[0.06] text-[10.5px] uppercase tracking-wider text-zinc-500">
                  <th className="px-5 py-2 font-medium">Topic</th>
                  <th className="w-24 px-2 py-2 font-medium">Hours</th>
                  <th className="w-24 px-2 py-2 font-medium">Weight %</th>
                  <th className="w-24 px-2 py-2 font-medium">Difficulty</th>
                  <th className="w-16 px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {draft.topics.map((t, i) => (
                  <tr key={i} className="border-b border-white/[0.04] last:border-0">
                    <td className="px-5 py-2">
                      <input
                        className={cx('field h-8 py-1', t.needs_review && 'border-amber-400/40')}
                        value={t.name}
                        onChange={(e) => patchTopic(i, 'name', e.target.value)}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input type="number" step="0.5" className="field h-8 py-1" value={t.est_hours}
                        onChange={(e) => patchTopic(i, 'est_hours', Number(e.target.value))} />
                    </td>
                    <td className="px-2 py-2">
                      <input type="number" className="field h-8 py-1" value={t.weight_pct}
                        onChange={(e) => patchTopic(i, 'weight_pct', Number(e.target.value))} />
                    </td>
                    <td className="px-2 py-2">
                      <select className="field h-8 py-1" value={t.difficulty}
                        onChange={(e) => patchTopic(i, 'difficulty', Number(e.target.value))}>
                        {[1, 2, 3, 4, 5].map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button onClick={() => removeTopic(i)} className="rounded p-1 text-zinc-600 hover:text-rose-300">
                        <Icon name="x" className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeading title={`Assessments (${draft.assessments.length})`} hint="these become the deadlines the solver respects" />
          {draft.assessments.length === 0 ? (
            <p className="py-3 text-[12.5px] text-zinc-500">No dates found — the planner will have no deadlines to work against.</p>
          ) : (
            <div className="space-y-1.5">
              {draft.assessments.map((a, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-white/[0.06] bg-ink-950/40 px-3 py-2">
                  <span className="text-[12.5px] text-zinc-200">{a.title}</span>
                  <Pill>{a.kind}</Pill>
                  <span className="ml-auto text-[11.5px] text-zinc-400">
                    {fmtDay(a.due_at)} · {a.weight_pct}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-white/[0.07] bg-ink-900/85 backdrop-blur-xl lg:left-[244px]">
          <div className="flex items-center justify-between gap-3 px-5 py-3 lg:px-8">
            <div className="text-[12px] text-zinc-400">
              {draft.topics.length} topics · {draft.assessments.length} assessments
              {flagged > 0 && <span className="ml-2 text-amber-300">{flagged} need review</span>}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStage('list')}>Cancel</Button>
              <Button variant="primary" icon="check" onClick={confirm} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : 'Confirm import'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------ input
  if (stage === 'input') {
    return (
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="p-5">
          <SectionHeading title="Add a syllabus" hint="PDF with a text layer, or paste it" />
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              parseFile(e.dataTransfer.files?.[0])
            }}
            className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border border-dashed border-white/[0.12] bg-ink-950/40 px-6 py-10 text-center hover:border-indigo-400/40 hover:bg-white/[0.03]"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-indigo-300">
              {busy ? <Spinner className="h-4 w-4" /> : <Icon name="upload" className="h-4 w-4" />}
            </div>
            <div>
              <p className="text-[12.5px] font-medium text-zinc-200">Drop a PDF or click to choose</p>
              <p className="mt-0.5 text-[11px] text-zinc-500">Text-based PDFs, up to 40 pages</p>
            </div>
            <input ref={fileRef} type="file" accept="application/pdf" className="hidden"
              onChange={(e) => parseFile(e.target.files?.[0])} />
          </div>

          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wider text-zinc-500">or paste text</span>
              <button onClick={() => setText(SAMPLE)} className="text-[11px] text-indigo-300 hover:text-indigo-200">
                use a sample
              </button>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              spellCheck={false}
              placeholder={'CS301 Data Structures\nUnit 1: Arrays and hashing (20%)\nMid-semester exam: 28/11/2026'}
              className="field resize-none font-mono text-[12px] leading-relaxed"
            />
            <div className="mt-2.5 flex items-center gap-2">
              <Button variant="primary" icon="sparkles" onClick={parseText} disabled={busy}>
                Parse syllabus
              </Button>
              <Button variant="subtle" onClick={() => setStage('list')}>Cancel</Button>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="text-[13px] font-medium text-zinc-100">What happens next</h3>
          <ol className="mt-3 space-y-2.5 text-[12px] leading-relaxed text-zinc-400">
            {[
              'Text is extracted from the PDF, or taken from what you pasted.',
              'A schema-constrained model call structures it — or a deterministic parser when no key is set.',
              'Every topic comes back with a confidence score; anything under 0.8 is flagged.',
              'You review and edit, then import. Nothing is saved before that.',
            ].map((line, i) => (
              <li key={i} className="flex gap-2.5">
                <span className="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-1.5 text-[10px] text-zinc-400">
                  {i + 1}
                </span>
                {line}
              </li>
            ))}
          </ol>
        </Card>
      </div>
    )
  }

  // ------------------------------------------------------------------ list
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-[16px] font-semibold text-zinc-100">Subjects</h1>
          <p className="text-[12px] text-zinc-500">Everything the planner, tutor and quiz generator draw on.</p>
        </div>
        <Button size="sm" variant="primary" icon="plus" onClick={() => setStage('input')}>
          Add syllabus
        </Button>
      </div>

      {!courses ? (
        <Skeleton className="h-40" />
      ) : courses.length === 0 ? (
        <Card>
          <EmptyState
            icon="file"
            title="No subjects yet"
            body="Upload a syllabus and the extraction is parsed, reviewed and imported in under a minute."
            action={<Button variant="primary" icon="upload" onClick={() => setStage('input')}>Upload a syllabus</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {courses.map((course, i) => {
            const tone = COURSE_TONES[i % COURSE_TONES.length]
            const open = expanded === course.id
            return (
              <Card key={course.id} className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className={cx('h-1.5 w-1.5 rounded-full', tone.dot)} />
                      <span className="truncate text-[13px] font-medium text-zinc-100">{course.name}</span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-zinc-500">
                      {course.code || '—'} · {course.topics.length} topics · {course.hours_left}h left
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11.5px] tabular-nums text-zinc-400">{course.mastery}%</span>
                    <button onClick={() => remove(course)} className="rounded p-1 text-zinc-600 hover:text-rose-300" title="Delete">
                      <Icon name="x" className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                <Progress value={course.mastery} tone={tone.bar} className="mt-2.5" />

                <div className="mt-3 space-y-1.5">
                  {(open ? course.topics : course.topics.slice(0, 3)).map((t) => (
                    <div key={t.id} className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-[11.5px] text-zinc-400">{t.name}</span>
                      <span className="text-[10.5px] tabular-nums text-zinc-500">{Math.round(t.mastery * 100)}%</span>
                      <div className="w-16">
                        <Progress value={t.mastery * 100} tone={tone.bar} />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-2.5 flex items-center justify-between">
                  <button onClick={() => setExpanded(open ? null : course.id)} className="text-[11px] text-indigo-300 hover:text-indigo-200">
                    {open ? 'Show less' : `Show all ${course.topics.length}`}
                  </button>
                  {course.assessments?.[0] && (
                    <span className="text-[10.5px] text-zinc-500">
                      next: {course.assessments[0].title} · {relativeDays(course.assessments[0].due_at)}
                    </span>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
