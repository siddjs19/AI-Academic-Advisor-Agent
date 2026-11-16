import Icon from '../components/Icons'
import { Button } from '../components/ui'

const PILLARS = [
  {
    icon: 'calendar',
    title: 'It plans',
    body: 'A CP-SAT solver places every topic inside your real free hours — caps, prerequisites and exam dates are hard constraints, not suggestions.',
  },
  {
    icon: 'book',
    title: 'It teaches',
    body: 'Ask a doubt and get an explanation pitched at your level, with a worked example and one question back to check you actually followed.',
  },
  {
    icon: 'target',
    title: 'It tests',
    body: 'Questions from your own syllabus, graded deterministically. Every answer updates a mastery estimate that needs evidence, not a lucky guess.',
  },
  {
    icon: 'chat',
    title: 'It examines',
    body: 'Mock viva and interview practice, one question at a time, scored on concept coverage, structure and clarity.',
  },
  {
    icon: 'refresh',
    title: 'It drills',
    body: 'Spaced repetition on the topics you keep losing marks in — cards come back exactly when they are about to be forgotten.',
  },
  {
    icon: 'sparkles',
    title: 'It follows up',
    body: 'Exam in 9 days at 34% readiness? You hear about it before you have to ask.',
  },
]

export default function Landing({ go }) {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
            <Icon name="bolt" className="h-4 w-4" strokeWidth={2.2} />
          </div>
          <span className="text-[14px] font-semibold tracking-tight">PrepPilot AI</span>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="subtle" onClick={() => go('auth')}>
            Sign in
          </Button>
          <Button size="sm" variant="primary" onClick={() => go('auth')}>
            Get started
          </Button>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-10 pt-10 sm:pt-16">
        <div className="max-w-3xl">
          <div className="chip mb-5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            plans are solved, not guessed
          </div>
          <h1 className="text-[34px] font-semibold leading-[1.1] tracking-tight text-white sm:text-[46px]">
            An academic mentor that plans, teaches, tests and follows up.
          </h1>
          <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
            PrepPilot reads your syllabus, remembers your marks, quizzes you on what you keep getting wrong and
            rebuilds the week when you fall behind. The planning is done by a constraint solver; the language
            model only teaches and explains — so the schedule you see is one that can actually be executed.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Button size="lg" variant="primary" icon="sparkles" onClick={() => go('auth')}>
              Open the demo account
            </Button>
            <span className="text-[12px] text-zinc-500">No signup needed · seeded semester included</span>
          </div>
        </div>

        <div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map((p) => (
            <div key={p.title} className="panel p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-indigo-300">
                <Icon name={p.icon} className="h-4 w-4" />
              </div>
              <h3 className="mt-3.5 text-[13.5px] font-semibold text-zinc-100">{p.title}</h3>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-zinc-400">{p.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-14 grid gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6 sm:grid-cols-3">
          {[
            ['One model, eight workflows', 'A supervisor routes to planning, teaching, assessment, viva, revision and analytics agents.'],
            ['Evidence, not vibes', 'Mastery needs repeated attempts at varying difficulty. One right answer never counts as mastery.'],
            ['Honest by construction', 'No model configured? The features that need generation say so instead of inventing content.'],
          ].map(([title, body]) => (
            <div key={title}>
              <div className="text-[12.5px] font-medium text-zinc-200">{title}</div>
              <p className="mt-1 text-[12px] leading-relaxed text-zinc-500">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-6 py-8 text-[11px] text-zinc-600">
        PrepPilot AI · FastAPI + OR-Tools + React · runs offline with a deterministic syllabus parser
      </footer>
    </div>
  )
}
