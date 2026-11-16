import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from './Icons'
import { Button, Pill, Spinner } from './ui'
import { cx } from '../lib'

const PROMPTS = [
  'What should I do next?',
  'Make me a plan for this week',
  'I missed two sessions',
  'Which topics matter most?',
  'How am I doing?',
]

const AGENT_LABEL = {
  supervisor: 'supervisor',
  planning: 'planning agent',
  teaching: 'teaching agent',
  assessment: 'assessment agent',
  communication: 'viva agent',
  revision: 'revision agent',
  analytics: 'analytics agent',
  assignments: 'assignment agent',
}

export default function AdvisorPanel({ onClose, notify, onChanged, go }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        "I'm the supervisor. I route your request to whichever specialist fits — planning, teaching, assessment, viva, revision or analytics — and I answer from your data, not from thin air.",
      agent: 'supervisor',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scroller = useRef(null)

  useEffect(() => {
    api
      .advisorHistory()
      .then((res) => {
        if (res.messages?.length) {
          setMessages(res.messages.map((m) => ({ role: m.role, content: m.content, agent: m.agent })))
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function send(text) {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: message }])
    setBusy(true)
    try {
      const res = await api.chat(message)
      setMessages((m) => [...m, { role: 'assistant', content: res.answer, agent: res.agent, intent: res.intent }])
      if ((res.actions || []).some((a) => a.startsWith('plan'))) onChanged?.()
    } catch (err) {
      notify(err.message, 'error')
      setMessages((m) => [...m, { role: 'assistant', content: `That failed: ${err.message}`, agent: 'supervisor' }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} aria-label="Close" />
      <div className="relative flex h-full w-full max-w-[420px] flex-col border-l border-white/[0.08] bg-ink-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
              <Icon name="sparkles" className="h-3.5 w-3.5" strokeWidth={2} />
            </div>
            <div>
              <div className="text-[12.5px] font-medium text-zinc-100">Advisor</div>
              <div className="text-[10.5px] text-zinc-500">supervisor · routes to 7 agents</div>
            </div>
          </div>
          <button onClick={onClose} className="rounded p-1 text-zinc-500 hover:text-zinc-200">
            <Icon name="x" className="h-4 w-4" />
          </button>
        </div>

        <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto px-3.5 py-4">
          {messages.map((m, i) => (
            <div key={i} className={cx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div
                className={cx(
                  'max-w-[88%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-[12.5px] leading-relaxed',
                  m.role === 'user'
                    ? 'bg-indigo-500/90 text-white'
                    : 'border border-white/[0.07] bg-white/[0.03] text-zinc-200',
                )}
              >
                {m.content}
                {m.agent && m.role === 'assistant' && (
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[9.5px] uppercase tracking-wider text-zinc-400">
                      {AGENT_LABEL[m.agent] || m.agent}
                    </span>
                    {m.intent && <span className="text-[9.5px] text-zinc-600">{m.intent}</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-[11.5px] text-zinc-500">
              <Spinner className="h-3.5 w-3.5" /> delegating…
            </div>
          )}
        </div>

        <div className="border-t border-white/[0.06] px-3 py-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                disabled={busy}
                className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10.5px] text-zinc-400 hover:border-indigo-400/40 hover:text-zinc-100"
              >
                {p}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
            className="flex gap-2"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your plan, a topic, or what to do next…"
              className="field"
              disabled={busy}
            />
            <Button type="submit" variant="primary" icon="send" disabled={busy || !input.trim()}>
              Send
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
