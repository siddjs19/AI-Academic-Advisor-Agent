import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, Pill, Spinner } from '../components/ui'
import { cx } from '../lib'

const LEVELS = [
  ['beginner', 'From scratch'],
  ['intermediate', 'Course level'],
  ['advanced', 'Precise / derivations'],
]

export default function Tutor({ notify }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [level, setLevel] = useState('intermediate')
  const [topics, setTopics] = useState([])
  const [topicId, setTopicId] = useState('')
  const [busy, setBusy] = useState(false)
  const scroller = useRef(null)

  useEffect(() => {
    api.courses().then((res) => setTopics(res.courses.flatMap((c) => c.topics.map((t) => ({ ...t, course: c.name }))))).catch(() => {})
    api.tutorHistory().then((res) => setMessages(res.messages.map((m) => ({ role: m.role, text: m.content })))).catch(() => {})
  }, [])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function send(e) {
    e?.preventDefault()
    const question = input.trim()
    if (!question || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: question }])
    setBusy(true)
    try {
      const res = await api.ask(question, topicId ? Number(topicId) : null, level)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: res.answer,
          meta: res.llm_required ? 'no model configured' : res.topic ? `topic: ${res.topic}` : '',
          warning: res.llm_required,
        },
      ])
    } catch (err) {
      notify(err.message, 'error')
      setMessages((m) => [...m, { role: 'assistant', text: `Something went wrong: ${err.message}`, warning: true }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Card className="flex h-[calc(100vh-150px)] min-h-[440px] flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
              <Icon name="book" className="h-3.5 w-3.5" strokeWidth={2} />
            </div>
            <div>
              <div className="text-[12.5px] font-medium text-zinc-100">Teaching agent</div>
              <div className="text-[10.5px] text-zinc-500">explains, then checks understanding</div>
            </div>
          </div>
          <div className="flex gap-1 rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
            {LEVELS.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setLevel(id)}
                className={cx(
                  'rounded-md px-2 py-1 text-[10.5px] font-medium',
                  level === id ? 'bg-white/[0.08] text-white' : 'text-zinc-500 hover:text-zinc-300',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div ref={scroller} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="mx-auto max-w-sm pt-10 text-center">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-indigo-300">
                <Icon name="book" className="h-4 w-4" />
              </div>
              <p className="mt-3 text-[13px] text-zinc-300">Ask anything from your syllabus.</p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-zinc-500">
                I know your topics and how many graded answers you have on each, so I pitch the explanation
                accordingly.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                {['Explain deadlock with an example', 'Why is 3NF weaker than BCNF?', 'What is dynamic programming actually doing?'].map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[11px] text-zinc-400 hover:border-indigo-400/40 hover:text-zinc-100"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={cx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div
                className={cx(
                  'max-w-[86%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed',
                  m.role === 'user'
                    ? 'bg-indigo-500/90 text-white'
                    : m.warning
                      ? 'border border-amber-400/25 bg-amber-400/[0.06] text-amber-100/90'
                      : 'border border-white/[0.07] bg-white/[0.03] text-zinc-200',
                )}
              >
                {m.text}
                {m.meta && <div className="mt-1.5 text-[10px] uppercase tracking-wider text-zinc-500">{m.meta}</div>}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl border border-white/[0.07] bg-white/[0.03] px-3.5 py-2.5 text-[12px] text-zinc-400">
                <Spinner className="h-3.5 w-3.5" /> thinking…
              </div>
            </div>
          )}
        </div>

        <form onSubmit={send} className="border-t border-white/[0.06] px-3 py-3">
          <div className="flex items-center gap-2">
            <select value={topicId} onChange={(e) => setTopicId(e.target.value)} className="field h-9 w-40 shrink-0 py-1 text-[11.5px]">
              <option value="">auto-detect topic</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>{t.name.slice(0, 40)}</option>
              ))}
            </select>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a doubt…"
              className="field"
              disabled={busy}
            />
            <Button type="submit" variant="primary" icon="send" disabled={busy || !input.trim()}>
              Ask
            </Button>
          </div>
        </form>
      </Card>

      <div className="space-y-3">
        <Card className="p-4">
          <h3 className="text-[12.5px] font-medium text-zinc-100">How it answers</h3>
          <ul className="mt-2.5 space-y-2 text-[11.5px] leading-relaxed text-zinc-400">
            <li className="flex gap-2">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
              Your mastery estimate for the topic is passed into the prompt, so the depth matches you.
            </li>
            <li className="flex gap-2">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
              Uploaded notes are searched for the relevant passage before answering.
            </li>
            <li className="flex gap-2">
              <Icon name="check" className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
              Every reply ends with a question back — reading is not the same as understanding.
            </li>
          </ul>
        </Card>
        <Card className="p-4">
          <h3 className="text-[12.5px] font-medium text-zinc-100">After this</h3>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-zinc-400">
            Take a practice set on the same topic. The attempt feeds your mastery estimate, which changes what the
            planner schedules next.
          </p>
          <Pill className="mt-2.5" tone="info">read → test → replan</Pill>
        </Card>
      </div>
    </div>
  )
}
