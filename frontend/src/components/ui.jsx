import { cx } from '../lib'
import Icon from './Icons'

export function Card({ className, children, ...rest }) {
  return (
    <div className={cx('panel', className)} {...rest}>
      {children}
    </div>
  )
}

export function SectionHeading({ title, hint, action }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-sm font-semibold tracking-tight text-zinc-100">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-zinc-500">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

export function Button({ variant = 'ghost', size = 'md', icon, className, children, ...rest }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 ' +
    'disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50'
  const variants = {
    primary:
      'bg-gradient-to-b from-indigo-400 to-indigo-500 text-ink-950 shadow-glow hover:from-indigo-300 hover:to-indigo-400 active:translate-y-px',
    ghost: 'border border-white/10 bg-white/[0.03] text-zinc-200 hover:border-white/20 hover:bg-white/[0.06]',
    subtle: 'text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100',
    danger: 'border border-rose-400/25 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20',
  }
  const sizes = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-9 px-3.5 text-[13px]',
    lg: 'h-11 px-5 text-sm',
  }
  return (
    <button className={cx(base, variants[variant], sizes[size], className)} {...rest}>
      {icon && <Icon name={icon} className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} />}
      {children}
    </button>
  )
}

export function Stat({ label, value, sub, icon, tone = 'text-zinc-100' }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">{label}</span>
        {icon && <Icon name={icon} className="h-4 w-4 text-zinc-600" />}
      </div>
      <div className={cx('mt-2 text-2xl font-semibold tracking-tight', tone)}>{value}</div>
      {sub && <div className="mt-1 text-xs text-zinc-500">{sub}</div>}
    </Card>
  )
}

export function Pill({ tone = 'default', children, className }) {
  const tones = {
    default: 'border-white/10 bg-white/[0.04] text-zinc-300',
    ok: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
    warn: 'border-amber-400/25 bg-amber-400/10 text-amber-300',
    bad: 'border-rose-400/25 bg-rose-400/10 text-rose-300',
    info: 'border-indigo-400/25 bg-indigo-400/10 text-indigo-300',
  }
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Progress({ value = 0, tone = 'bg-indigo-400', className }) {
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]', className)}>
      <div
        className={cx('h-full rounded-full transition-all duration-500', tone)}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}

export function Spinner({ className = 'h-4 w-4' }) {
  return (
    <svg className={cx('animate-spin', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.18" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export function Skeleton({ className }) {
  return <div className={cx('animate-pulse rounded-lg bg-white/[0.05]', className)} />
}

export function EmptyState({ icon = 'sparkles', title, body, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-indigo-300">
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <div>
        <p className="text-sm font-medium text-zinc-200">{title}</p>
        {body && <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-zinc-500">{body}</p>}
      </div>
      {action}
    </div>
  )
}

export function Toasts({ items, onDismiss }) {
  return (
    <div className="pointer-events-none fixed bottom-24 right-5 z-50 flex w-80 flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          className={cx(
            'pointer-events-auto animate-fade-up rounded-xl border px-3.5 py-2.5 text-[13px] shadow-card backdrop-blur-md',
            t.tone === 'error'
              ? 'border-rose-400/30 bg-rose-950/70 text-rose-100'
              : 'border-emerald-400/25 bg-emerald-950/60 text-emerald-100',
          )}
        >
          <div className="flex items-start gap-2">
            <Icon name={t.tone === 'error' ? 'alert' : 'check'} className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="flex-1 leading-snug">{t.message}</span>
            <button onClick={() => onDismiss(t.id)} className="text-white/40 hover:text-white/80">
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
