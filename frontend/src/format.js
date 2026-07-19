// Pure display helpers — unit-tested; keep free of React and network code.

const DAY_MS = 86400 * 1000

function startOfDay(d) {
  const c = new Date(d)
  c.setHours(0, 0, 0, 0)
  return c
}

function timePart(d) {
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

export function isOverdue(dueAtIso, now = new Date()) {
  if (!dueAtIso) return false
  return new Date(dueAtIso) < now
}

export function dueLabel(dueAtIso, now = new Date()) {
  if (!dueAtIso) return ''
  const due = new Date(dueAtIso)
  if (due < now) {
    return `Overdue — ${due.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}`
  }
  const days = Math.round((startOfDay(due) - startOfDay(now)) / DAY_MS)
  if (days === 0) return `Today ${timePart(due)}`
  if (days === 1) return `Tomorrow ${timePart(due)}`
  if (days < 7) {
    return `${due.toLocaleDateString(undefined, { weekday: 'short' })} ${timePart(due)}`
  }
  return due.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function priorityMeta(priority) {
  const labels = ['', 'Low', 'Medium', 'High']
  const p = Math.min(Math.max(priority || 0, 0), 3)
  return { label: labels[p], className: `prio-${p}` }
}

export function recurrenceLabel(recurrence) {
  return recurrence ? `Repeats ${recurrence}` : ''
}

const PRESETS = [
  { label: 'At due time', minutes: 0 },
  { label: '30 min before', minutes: 30 },
  { label: '1 hour before', minutes: 60 },
  { label: '1 day before', minutes: 1440 },
]

export function reminderPresets(dueAtIso, now = new Date()) {
  if (!dueAtIso) return []
  const due = new Date(dueAtIso).getTime()
  return PRESETS.map(({ label, minutes }) => ({
    label,
    iso: new Date(due - minutes * 60 * 1000).toISOString(),
  })).filter((p) => new Date(p.iso) > now)
}

export function timeAgo(iso, now = new Date()) {
  const seconds = Math.max(0, (now - new Date(iso)) / 1000)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

// datetime-local <input> helpers: value is local wall time without zone.
export function isoToLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function localInputToIso(value) {
  return value ? new Date(value).toISOString() : null
}
