import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, Progress, SectionHeading, Skeleton, Spinner } from '../components/ui'
import { cx } from '../lib'

const DIFFICULTIES = ['beginner', 'intermediate', 'advanced']

export default function Practice({ notify }) {
  const [courses, setCourses] = useState(null)
  const [selected, setSelected] = useState([])
  const [count, setCount] = useState(5)
  const [difficulty, setDifficulty] = useState('intermediate')
  const [quiz, setQuiz] = useState(null)
  const [responses, setResponses] = useState({})
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const [c, h] = await Promise.all([api.courses(), api.practiceHistory()])
      setCourses(c.courses)
      setHistory(h.attempts)
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const allTopics = (courses || []).flatMap((c) => c.topics.map((t) => ({ ...t, course: c.name, code: c.code })))
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  async function generate() {
    if (!selected.length) return notify('Pick at least one topic', 'error')
    setBusy(true)
    try {
      const res = await api.generatePractice({
        topic_ids: selected.slice(0, 6),
        mode: 'topic',
        difficulty,
        count: Number(count),
      })
      setQuiz(res)
      setResponses({})
      setResult(null)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setBusy(true)
    try {
      const res = await api.submitPractice(quiz.quiz_set_id, responses)
      setResult(res)
      setQuiz(null)
      await load()
      notify(`Scored ${res.score}/${res.max_score} — mastery updated.`)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  // ------------------------------------------------------------------ result
  if (result) {
    const tone = result.accuracy_pct >= 70 ? 'ok' : result.accuracy_pct >= 40 ? 'warn' : 'bad'
    return (
      <div className="space-y-4">
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-zinc-500">Attempt complete</div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-[26px] font-semibold text-white">{result.accuracy_pct}%</span>
                <span className="text-[12px] text-zinc-500">
                  {result.score} / {result.max_score} marks
                </span>
              </div>
            </div>
            <Pill tone={tone}>{result.accuracy_pct >= 70 ? 'solid' : result.accuracy_pct >= 40 ? 'shaky' : 'needs work'}</Pill>
          </div>
          <Progress value={result.accuracy_pct} className="mt-3" tone={result.accuracy_pct >= 70 ? 'bg-emerald-400' : 'bg-amber-400'} />
          {result.weakest_topics?.length > 0 && (
            <p className="mt-3 text-[12px] text-zinc-400">
              Mastery moved. Still weakest: <span className="text-zinc-200">{result.weakest_topics.join(', ')}</span>.
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <Button variant="primary" icon="refresh" onClick={() => setResult(null)}>
              Another set
            </Button>
            <Button variant="ghost" onClick={() => window.location.assign('#/plan')}>
              See the plan
            </Button>
          </div>
        </Card>

        <div className="space-y-2">
          {result.results.map((r, i) => (
            <Card key={r.question_id} className="p-4">
              <div className="flex items-start gap-2.5">
                <span
                  className={cx(
                    'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full',
                    r.correct === true
                      ? 'bg-emerald-400/15 text-emerald-300'
                      : r.correct === false
                        ? 'bg-rose-500/15 text-rose-300'
                        : 'bg-white/[0.06] text-zinc-400',
                  )}
                >
                  <Icon name={r.correct === true ? 'check' : r.correct === false ? 'x' : 'clock'} className="h-3 w-3" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] text-zinc-100">
                    <span className="text-zinc-500">{i + 1}. </span>
                    {r.stem}
                  </div>
                  <div className="mt-1 text-[11.5px] text-zinc-400">{r.feedback}</div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <Pill>{r.qtype}</Pill>
                    <span className="text-[10.5px] text-zinc-500">
                      {r.awarded}/{r.marks} marks · graded by {r.graded_by}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------ taking
  if (quiz) {
    const answered = Object.keys(responses).length
    return (
      <div className="mx-auto max-w-3xl space-y-4 pb-24">
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-[13px] font-medium text-zinc-100">{quiz.title}</div>
              <div className="text-[11px] text-zinc-500">
                {quiz.questions.length} questions · source: {quiz.source === 'llm' ? 'generated' : 'sample bank'}
              </div>
            </div>
            <div className="text-[11.5px] text-zinc-400">
              {answered}/{quiz.questions.length} answered
            </div>
          </div>
          <Progress value={(answered / quiz.questions.length) * 100} className="mt-2.5" />
        </Card>

        {quiz.questions.map((q, i) => (
          <Card key={q.id} className="p-4">
            <div className="flex items-baseline justify-between gap-3">
              <div className="text-[12.5px] leading-relaxed text-zinc-100">
                <span className="text-zinc-500">{i + 1}. </span>
                {q.stem}
              </div>
              <Pill>{q.qtype}</Pill>
            </div>

            <div className="mt-3">
              {(q.qtype === 'mcq' || q.qtype === 'truefalse') &&
                q.options.map((opt) => (
                  <label
                    key={opt}
                    className={cx(
                      'mb-1.5 flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-[12px] transition-colors',
                      responses[q.id]?.value === opt
                        ? 'border-indigo-400/50 bg-indigo-400/10 text-zinc-100'
                        : 'border-white/[0.07] bg-white/[0.02] text-zinc-300 hover:border-white/20',
                    )}
                  >
                    <input
                      type="radio"
                      name={`q${q.id}`}
                      className="h-3.5 w-3.5 accent-indigo-400"
                      checked={responses[q.id]?.value === opt}
                      onChange={() => setResponses((r) => ({ ...r, [q.id]: { value: opt } }))}
                    />
                    {opt}
                  </label>
                ))}

              {q.qtype === 'multi' &&
                q.options.map((opt) => {
                  const current = responses[q.id]?.value || []
                  const on = current.includes(opt)
                  return (
                    <label
                      key={opt}
                      className={cx(
                        'mb-1.5 flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-[12px]',
                        on ? 'border-indigo-400/50 bg-indigo-400/10 text-zinc-100' : 'border-white/[0.07] bg-white/[0.02] text-zinc-300',
                      )}
                    >
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 accent-indigo-400"
                        checked={on}
                        onChange={() =>
                          setResponses((r) => ({
                            ...r,
                            [q.id]: { value: on ? current.filter((v) => v !== opt) : [...current, opt] },
                          }))
                        }
                      />
                      {opt}
                    </label>
                  )
                })}

              {q.qtype === 'numerical' && (
                <input
                  type="number"
                  step="any"
                  className="field max-w-[200px]"
                  placeholder="your answer"
                  value={responses[q.id]?.value ?? ''}
                  onChange={(e) => setResponses((r) => ({ ...r, [q.id]: { value: e.target.value } }))}
                />
              )}

              {(q.qtype === 'short' || q.qtype === 'descriptive') && (
                <textarea
                  rows={q.qtype === 'short' ? 2 : 4}
                  className="field resize-none"
                  placeholder={q.qtype === 'short' ? 'two or three sentences' : 'a structured paragraph'}
                  value={responses[q.id]?.value ?? ''}
                  onChange={(e) => setResponses((r) => ({ ...r, [q.id]: { value: e.target.value } }))}
                />
              )}
            </div>
          </Card>
        ))}

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-white/[0.07] bg-ink-900/85 backdrop-blur-xl lg:left-[244px]">
          <div className="flex items-center justify-between px-5 py-3 lg:px-8">
            <span className="text-[11.5px] text-zinc-500">
              Objective answers are graded by rules; written answers use keyword coverage or a rubric.
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setQuiz(null)}>Discard</Button>
              <Button variant="primary" icon="check" onClick={submit} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : 'Submit attempt'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ------------------------------------------------------------------ setup
  return (
    <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
      <Card className="p-5">
        <SectionHeading title="Build a practice set" hint="questions come from your own topics" />
        {!courses ? (
          <Skeleton className="h-40" />
        ) : allTopics.length === 0 ? (
          <EmptyState icon="target" title="No topics yet" body="Import a syllabus first — questions are generated from your own topics." />
        ) : (
          <>
            <div className="max-h-[380px] space-y-1 overflow-y-auto pr-1">
              {(courses || []).map((c) => (
                <div key={c.id} className="mb-2">
                  <div className="px-1 pb-1 text-[10.5px] uppercase tracking-wider text-zinc-500">{c.name}</div>
                  {c.topics.map((t) => (
                    <label
                      key={t.id}
                      className={cx(
                        'mb-1 flex cursor-pointer items-center gap-2.5 rounded-lg border px-2.5 py-1.5',
                        selected.includes(t.id)
                          ? 'border-indigo-400/40 bg-indigo-400/[0.08]'
                          : 'border-white/[0.05] bg-white/[0.02] hover:border-white/15',
                      )}
                    >
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 accent-indigo-400"
                        checked={selected.includes(t.id)}
                        onChange={() => toggle(t.id)}
                      />
                      <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-200">{t.name}</span>
                      <span className="text-[10.5px] tabular-nums text-zinc-500">{Math.round(t.mastery * 100)}%</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <select value={count} onChange={(e) => setCount(e.target.value)} className="field h-9 w-32 py-1 text-[12px]">
                {[3, 5, 8, 10].map((n) => (
                  <option key={n} value={n}>{n} questions</option>
                ))}
              </select>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="field h-9 w-36 py-1 text-[12px]">
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <Button variant="primary" icon="target" onClick={generate} disabled={busy || !selected.length}>
                {busy ? <Spinner className="h-4 w-4" /> : `Generate (${selected.length} topic${selected.length === 1 ? '' : 's'})`}
              </Button>
            </div>
          </>
        )}
      </Card>

      <div className="space-y-3">
        <Card className="p-4">
          <h3 className="text-[12.5px] font-medium text-zinc-100">Grading, honestly</h3>
          <ul className="mt-2.5 space-y-2 text-[11.5px] leading-relaxed text-zinc-400">
            <li>• MCQ, multi-select, true/false and numerical answers are graded by rules — exact, reproducible.</li>
            <li>• Short answers are scored on concept coverage against expected keywords.</li>
            <li>• A descriptive answer with no rubric and no model is stored as <span className="text-zinc-200">pending</span>, never given an invented mark.</li>
          </ul>
        </Card>

        <Card className="p-4">
          <SectionHeading title="Recent attempts" />
          {history.length === 0 ? (
            <p className="py-3 text-[12px] text-zinc-500">No attempts yet.</p>
          ) : (
            <div className="space-y-1.5">
              {history.slice(0, 6).map((a) => (
                <div key={a.attempt_id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[11.5px] text-zinc-300">{a.quiz}</div>
                    <div className="text-[10.5px] text-zinc-500">
                      {new Date(a.at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                    </div>
                  </div>
                  <span
                    className={cx(
                      'text-[11.5px] tabular-nums',
                      a.accuracy_pct >= 70 ? 'text-emerald-300' : a.accuracy_pct >= 40 ? 'text-amber-300' : 'text-rose-300',
                    )}
                  >
                    {a.accuracy_pct}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
