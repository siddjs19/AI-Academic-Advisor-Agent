import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icons'
import { Button, Card, EmptyState, Pill, Progress, SectionHeading, Spinner } from '../components/ui'
import { cx } from '../lib'

const RATINGS = [
  [0, 'Again', 'bg-rose-500/15 text-rose-300 border-rose-400/25'],
  [1, 'Hard', 'bg-amber-400/10 text-amber-300 border-amber-400/25'],
  [2, 'Good', 'bg-indigo-400/10 text-indigo-300 border-indigo-400/25'],
  [3, 'Easy', 'bg-emerald-400/10 text-emerald-300 border-emerald-400/25'],
]

export default function Revision({ notify }) {
  const [queue, setQueue] = useState([])
  const [total, setTotal] = useState(0)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(0)
  const [generating, setGenerating] = useState(false)

  async function load() {
    try {
      const res = await api.dueCards()
      setQueue(res.cards)
      setTotal(res.total_cards)
      setIndex(0)
      setFlipped(false)
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function rate(rating) {
    const card = queue[index]
    if (!card) return
    setBusy(true)
    try {
      await api.reviewCard(card.id, rating)
      setDone((d) => d + 1)
      setFlipped(false)
      if (index + 1 >= queue.length) {
        setIndex(queue.length)
      } else {
        setIndex((i) => i + 1)
      }
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function generate() {
    setGenerating(true)
    try {
      const res = await api.generateCards([], 6)
      notify(`${res.created} cards added from your weakest topics.`)
      await load()
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setGenerating(false)
    }
  }

  const card = queue[index]
  const progress = queue.length ? Math.round((index / queue.length) * 100) : 0

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Card className="flex min-h-[420px] flex-col p-5">
        <SectionHeading
          title="Due now"
          hint={queue.length ? `${queue.length} cards in this session` : 'nothing scheduled'}
          action={
            <Button size="sm" variant="ghost" icon="plus" onClick={generate} disabled={generating}>
              {generating ? 'Building…' : 'Generate cards'}
            </Button>
          }
        />

        {queue.length === 0 ? (
          <EmptyState
            icon="refresh"
            title="Your queue is clear"
            body="Spaced repetition works by returning cards just before you would forget them. Generate a set from your weakest topics to start."
            action={<Button variant="primary" icon="plus" onClick={generate} disabled={generating}>Generate cards</Button>}
          />
        ) : card ? (
          <>
            <Progress value={progress} className="mb-4" />
            <button
              onClick={() => setFlipped((f) => !f)}
              className="flex flex-1 cursor-pointer flex-col items-center justify-center rounded-xl border border-white/[0.07] bg-ink-950/40 px-6 py-10 text-center transition-colors hover:border-white/15"
            >
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">{flipped ? 'answer' : 'question'}</span>
              <span className={cx('mt-3 text-[15px] leading-relaxed', flipped ? 'text-zinc-200' : 'text-zinc-100')}>
                {flipped ? card.back : card.front}
              </span>
              {!flipped && <span className="mt-5 text-[11px] text-zinc-500">click to reveal</span>}
            </button>

            <div className="mt-4 grid grid-cols-4 gap-1.5">
              {RATINGS.map(([value, label, style]) => (
                <button
                  key={value}
                  onClick={() => rate(value)}
                  disabled={!flipped || busy}
                  className={cx(
                    'rounded-lg border py-2 text-[11.5px] font-medium transition-opacity',
                    style,
                    (!flipped || busy) && 'opacity-40',
                  )}
                >
                  {busy ? '…' : label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-center text-[10.5px] text-zinc-500">
              Rating schedules the card: “again” returns tomorrow, “easy” pushes it weeks out.
            </p>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
              <Icon name="check" className="h-5 w-5" />
            </div>
            <p className="mt-3 text-[13px] text-zinc-200">Session complete</p>
            <p className="mt-1 text-[11.5px] text-zinc-500">{done} cards reviewed just now.</p>
            <Button className="mt-4" variant="ghost" icon="refresh" onClick={load}>
              Check the queue again
            </Button>
          </div>
        )}
      </Card>

      <div className="space-y-3">
        <Card className="p-4">
          <SectionHeading title="Collection" />
          <div className="flex items-baseline gap-2">
            <span className="text-[24px] font-semibold text-zinc-100">{total}</span>
            <span className="text-[11.5px] text-zinc-500">cards total</span>
          </div>
          <div className="mt-2 flex gap-1.5">
            <Pill tone="info">{queue.length} due</Pill>
            <Pill>{done} reviewed</Pill>
          </div>
        </Card>

        <Card className="p-4">
          <h3 className="text-[12.5px] font-medium text-zinc-100">The algorithm</h3>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-zinc-400">
            A simplified SM-2: each card carries an ease factor and an interval. A good answer multiplies the
            interval by the ease; a lapse resets it to one day and lowers the ease. Nothing is scheduled by
            "pick a random old topic".
          </p>
          <ul className="mt-2.5 space-y-1 text-[11px] text-zinc-500">
            <li>• first success → 3 days</li>
            <li>• second → 6 days</li>
            <li>• then interval × ease (1.3 – 2.8)</li>
          </ul>
        </Card>
      </div>
    </div>
  )
}
