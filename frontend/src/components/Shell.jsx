import Icon from './Icons'
import { cx } from '../lib'

const NAV = [
  {
    section: 'Overview',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: 'grid' },
      { id: 'plan', label: 'Study plan', icon: 'calendar' },
    ],
  },
  {
    section: 'Learn',
    items: [
      { id: 'tutor', label: 'Tutor', icon: 'book' },
      { id: 'practice', label: 'Practice', icon: 'target' },
      { id: 'viva', label: 'Viva & speaking', icon: 'chat' },
      { id: 'revision', label: 'Revision', icon: 'refresh' },
    ],
  },
  {
    section: 'Manage',
    items: [
      { id: 'subjects', label: 'Subjects', icon: 'file' },
      { id: 'assignments', label: 'Assignments', icon: 'check' },
      { id: 'analytics', label: 'Analytics', icon: 'chart' },
      { id: 'settings', label: 'Settings', icon: 'user' },
    ],
  },
]

export function Shell({ route, go, student, onLogout, onOpenAdvisor, children }) {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[244px] shrink-0 flex-col border-r border-white/[0.06] bg-ink-950/50 px-3 py-5 backdrop-blur-xl lg:flex">
        <button onClick={() => go('dashboard')} className="flex items-center gap-2.5 px-2 text-left">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
            <Icon name="bolt" className="h-4 w-4" strokeWidth={2.2} />
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold tracking-tight text-zinc-100">PrepPilot AI</div>
            <div className="text-[10.5px] text-zinc-500">academic mentor</div>
          </div>
        </button>

        <nav className="mt-6 flex-1 space-y-5 overflow-y-auto">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-600">
                {group.section}
              </div>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => go(item.id)}
                    className={cx(
                      'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[12.5px] font-medium transition-colors',
                      route === item.id
                        ? 'bg-white/[0.07] text-white'
                        : 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200',
                    )}
                  >
                    <Icon name={item.icon} className={cx('h-4 w-4', route === item.id ? 'text-indigo-300' : 'text-zinc-500')} />
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <button
          onClick={onOpenAdvisor}
          className="mt-3 flex items-center justify-center gap-2 rounded-xl border border-indigo-400/25 bg-indigo-500/10 px-3 py-2 text-[12px] font-medium text-indigo-200 transition-colors hover:bg-indigo-500/20"
        >
          <Icon name="sparkles" className="h-3.5 w-3.5" />
          Ask the advisor
        </button>

        <div className="mt-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-2.5">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/[0.07] text-[11px] font-semibold text-zinc-300">
              {(student?.name || 'S').slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-[12px] font-medium text-zinc-200">{student?.name}</div>
              <div className="truncate text-[10.5px] text-zinc-500">
                Sem {student?.semester} · {student?.target_grade}
              </div>
            </div>
            <button onClick={onLogout} title="Sign out" className="rounded-md p-1 text-zinc-500 hover:bg-white/[0.06] hover:text-zinc-200">
              <Icon name="arrowRight" className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-ink-900/70 backdrop-blur-xl lg:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <button onClick={() => go('dashboard')} className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-violet-500 text-ink-950">
                <Icon name="bolt" className="h-3.5 w-3.5" strokeWidth={2.2} />
              </div>
              <span className="text-[13px] font-semibold text-zinc-100">PrepPilot AI</span>
            </button>
            <div className="flex gap-1">
              <button onClick={onOpenAdvisor} className="rounded-lg border border-white/10 px-2 py-1 text-[11px] text-zinc-300">
                Advisor
              </button>
              <button onClick={onLogout} className="rounded-lg border border-white/10 px-2 py-1 text-[11px] text-zinc-400">
                Sign out
              </button>
            </div>
          </div>
          <div className="flex gap-1 overflow-x-auto px-3 pb-2">
            {NAV.flatMap((g) => g.items).map((item) => (
              <button
                key={item.id}
                onClick={() => go(item.id)}
                className={cx(
                  'whitespace-nowrap rounded-lg px-2.5 py-1 text-[11px] font-medium',
                  route === item.id ? 'bg-white/[0.08] text-white' : 'text-zinc-400',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </header>

        <main className="flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  )
}
