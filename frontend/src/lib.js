export const cx = (...parts) => parts.filter(Boolean).join(' ')

const TIME = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
const DAY = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: '2-digit', month: 'short' })
const LONG_DAY = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })
const SHORT_DAY = new Intl.DateTimeFormat('en-IN', { weekday: 'short' })

export const asDate = (iso) => (iso ? new Date(iso) : null)
export const fmtTime = (iso) => (iso ? TIME.format(new Date(iso)) : '')
export const fmtDay = (iso) => (iso ? DAY.format(new Date(iso)) : '')
export const fmtLongDay = (iso) => (iso ? LONG_DAY.format(new Date(iso)) : '')
export const fmtWeekday = (iso) => (iso ? SHORT_DAY.format(new Date(iso)) : '')
export const dayKey = (iso) => (iso ? iso.slice(0, 10) : '')

export const minutesLabel = (mins) => {
  if (!mins) return ''
  if (mins < 60) return `${mins}m`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

export const isToday = (iso) => {
  if (!iso) return false
  const d = new Date(iso)
  const now = new Date()
  return (
    d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
  )
}

export const relativeDays = (iso) => {
  if (!iso) return ''
  const target = new Date(iso)
  const now = new Date()
  const diff = Math.round((target.setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86400000)
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  if (diff < 0) return `${Math.abs(diff)}d ago`
  return `in ${diff}d`
}

export const splitLabel = (label = '') => {
  const [course, ...rest] = label.split(' · ')
  return rest.length ? { course, topic: rest.join(' · ') } : { course: '', topic: course }
}

export const COURSE_TONES = [
  { dot: 'bg-indigo-400', text: 'text-indigo-300', soft: 'bg-indigo-400/10', border: 'border-indigo-400/30', bar: 'bg-indigo-400' },
  { dot: 'bg-emerald-400', text: 'text-emerald-300', soft: 'bg-emerald-400/10', border: 'border-emerald-400/30', bar: 'bg-emerald-400' },
  { dot: 'bg-amber-400', text: 'text-amber-300', soft: 'bg-amber-400/10', border: 'border-amber-400/30', bar: 'bg-amber-400' },
  { dot: 'bg-sky-400', text: 'text-sky-300', soft: 'bg-sky-400/10', border: 'border-sky-400/30', bar: 'bg-sky-400' },
  { dot: 'bg-rose-400', text: 'text-rose-300', soft: 'bg-rose-400/10', border: 'border-rose-400/30', bar: 'bg-rose-400' },
  { dot: 'bg-violet-400', text: 'text-violet-300', soft: 'bg-violet-400/10', border: 'border-violet-400/30', bar: 'bg-violet-400' },
]

export const toneForCourse = (courses, courseName) => {
  const index = (courses || []).findIndex((c) => c.name === courseName)
  return COURSE_TONES[(index < 0 ? 0 : index) % COURSE_TONES.length]
}

export const nextDays = (count = 7) => {
  const out = []
  const base = new Date()
  base.setHours(0, 0, 0, 0)
  for (let i = 0; i < count; i += 1) {
    const d = new Date(base)
    d.setDate(base.getDate() + i)
    out.push(d)
  }
  return out
}

export const isoDay = (date) => {
  const d = new Date(date)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const SAFE_TONES = [COURSE_TONES[0], COURSE_TONES[1], COURSE_TONES[2], COURSE_TONES[3], COURSE_TONES[5]]

export const courseTone = (name = "") => {
  let h = 0
  for (let i = 0; i < name.length; i += 1) h = (h * 31 + name.charCodeAt(i)) | 0
  return SAFE_TONES[Math.abs(h) % SAFE_TONES.length]
}
