import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, SectionHeading, Spinner } from '../components/ui'
import { cx } from '../lib'

const KINDS = [
  ['viva', 'College viva'],
  ['interview', 'Technical interview'],
  ['hr', 'HR interview'],
  ['presentation', 'Presentation defence'],
]

export default function Viva({ notify }) {
  const [topics, setTopics] = useState([])
  const [topicId, setTopicId] = useState('')
  const [kind, setKind] = useState('viva')
  const [session, setSession] = useState(null)
  const [turns, setTurns] = useState([])
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    api.courses().then((r) => {
      const flat = r.courses.flatMap((c) => c.topics.map((t) => ({ ...t, course: c.name })))
      setTopics(flat)
      if (flat.length) setTopicId(String(flat[0].id))
    })
    api.vivaHistory().then((r) => setHistory(r.sessions)).catch(() => {})
  }, [])

  async function start() {
    if (!topicId) return notify('Pick a topic first', 'error')
    setBusy(true)
    try {
      const res = await api.startViva(Number(topicId), kind)
      setSession(res)
      setTurns([{ role: 'examiner', text: res.question }])
      setReport(null)
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function send() {
    const text = answer.trim()
    if (!text) return
    setBusy(true)
    setTurns((t) => [...t, { role: 'you', text }])
    setAnswer('')
    try {
      const res = await api.answerViva(session.session_id, text)
      setTurns((t) => [
        ...t,
        { role: 'feedback', text: res.feedback, score: res.score },
        ...(res.next_question ? [{ role: 'examiner', text: res.next_question }] : []),
      ])
      if (res.finished) {
        setReport({ score: res.score, feedback: res.report })
        api.vivaHistory().then((r) => setHistory(r.sessions)).catch(() => {})
      }
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!session) {
    return (
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="p-5">
          <SectionHeading title="Start a mock viva" hint="one question at a time, with scoring after every answer" />
          {topics.length === 0 ? (
            <EmptyState icon="chat" title="No topics yet" body="Import a syllabus first — the examiner asks about your own topics." />
          ) : (
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Topic</span>
                <select value={topicId} onChange={(e) => setTopicId(e.target.value)} className="field">
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.course} — {t.name}
                    </option>
                  ))}
                </select>
              </label>
              <div>
                <span className="mb-1 block text-[11px] uppercase tracking-wider text-zinc-500">Format</span>
                <div className="grid grid-cols-2 gap-1.5">
                  {KINDS.map(([id, label]) => (
                    <button
                      key={id}
                      onClick={() => setKind(id)}
                      className={cx(
                        'rounded-lg border px-3 py-2 text-[12px] text-left',
                        kind === id ? 'border-indigo-400/50 bg-indigo-400/10 text-zinc-100' : 'border-white/[0.07] text-zinc-400 hover:border-white/20',
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <Button variant="primary" icon="chat" onClick={start} disabled={busy}>
                {busy ? <Spinner className="h-4 w-4" /> : 'Begin session'}
              </Button>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <SectionHeading title="Past sessions" />
          {history.length === 0 ? (
            <p className="py-3 text-[12px] text-zinc-500">No sessions yet.</p>
          ) : (
            <div className="space-y-2">
              {history.map((s) => (
                <div key={s.id} className="rounded-lg bg-white/[0.02] px-2.5 py-2">
                  <div className="flex items-center justify-between">
                    <span className="truncate text-[11.5px] text-zinc-200">{s.topic}</span>
                    <span className="text-[11px] tabular-nums text-zinc-400">{s.score ?? '—'}</span>
                  </div>
                  <div className="text-[10.5px] text-zinc-500">
                    {s.kind} · {s.status} · {new Date(s.at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className="p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-[12.5px] font-medium text-zinc-100">{session.topic}</div>
            <div className="text-[11px] text-zinc-500">
              {session.kind} · evaluated by {session.evaluator === 'llm' ? 'the model' : 'concept coverage rules'}
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={() => { setSession(null); setTurns([]); setReport(null) }}>
            End session
          </Button>
        </div>
      </Card>

      <div className="space-y-2.5">
        {turns.map((t, i) => (
          <div key={i} className={cx('flex', t.role === 'you' ? 'justify-end' : 'justify-start')}>
            <div
              className={cx(
                'max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[12.5px] leading-relaxed',
                t.role === 'you'
                  ? 'bg-indigo-500/90 text-white'
                  : t.role === 'feedback'
                    ? 'border border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-100/90'
                    : 'border border-white/[0.07] bg-white/[0.03] text-zinc-200',
              )}
            >
              {t.role === 'examiner' && <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500">examiner</div>}
              {t.role === 'feedback' && (
                <div className="mb-1 text-[10px] uppercase tracking-wider text-emerald-400/80">
                  feedback · score {Math.round(t.score * 100)}%
                </div>
              )}
              {t.text}
            </div>
          </div>
        ))}
        {busy && <div className="text-[11.5px] text-zinc-500">assessing…</div>}
      </div>

      {report ? (
        <Card className="border-indigo-400/25 bg-indigo-400/[0.05] p-4">
          <div className="flex items-center gap-2">
            <Icon name="check" className="h-4 w-4 text-indigo-300" />
            <span className="text-[13px] font-medium text-zinc-100">Session complete</span>
            <Pill tone="info">{report.score}/100</Pill>
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-300">{report.feedback}</p>
          <p className="mt-2 text-[11px] text-zinc-500">
            This score was folded into your mastery estimate for the topic.
          </p>
        </Card>
      ) : (
        <Card className="p-3">
          <textarea
            rows={3}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Answer out loud in your head, then type what you said…"
            className="field resize-none"
            disabled={busy}
          />
          <div className="mt-2 flex justify-end">
            <Button variant="primary" icon="send" onClick={send} disabled={busy || !answer.trim()}>
              Answer
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
