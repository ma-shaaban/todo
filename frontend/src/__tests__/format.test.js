import { describe, it, expect } from 'vitest'
import { dueLabel, isOverdue, priorityMeta, recurrenceLabel, reminderPresets, timeAgo } from '../format.js'

// Fixed "now": Sunday 2026-07-19 12:00 local time.
const NOW = new Date(2026, 6, 19, 12, 0, 0)

const local = (y, m, d, h = 0, min = 0) => new Date(y, m, d, h, min).toISOString()

describe('dueLabel', () => {
  it('labels today and tomorrow with time', () => {
    expect(dueLabel(local(2026, 6, 19, 14, 0), NOW)).toBe('Today 14:00')
    expect(dueLabel(local(2026, 6, 20, 9, 30), NOW)).toBe('Tomorrow 09:30')
  })
  it('labels within a week by weekday', () => {
    expect(dueLabel(local(2026, 6, 22, 8, 0), NOW)).toMatch(/^Wed/)
  })
  it('labels far dates with day and month', () => {
    expect(dueLabel(local(2026, 8, 3, 8, 0), NOW)).toMatch(/3/)
    expect(dueLabel(local(2026, 8, 3, 8, 0), NOW)).toMatch(/Sep/)
  })
  it('marks overdue', () => {
    expect(dueLabel(local(2026, 6, 17, 9, 0), NOW)).toMatch(/^Overdue/)
    expect(isOverdue(local(2026, 6, 17, 9, 0), NOW)).toBe(true)
    expect(isOverdue(local(2026, 6, 20, 9, 0), NOW)).toBe(false)
  })
  it('returns empty for missing due', () => {
    expect(dueLabel(null, NOW)).toBe('')
  })
})

describe('priorityMeta', () => {
  it('maps levels', () => {
    expect(priorityMeta(0).label).toBe('')
    expect(priorityMeta(1).label).toBe('Low')
    expect(priorityMeta(2).label).toBe('Medium')
    expect(priorityMeta(3).label).toBe('High')
    expect(priorityMeta(3).className).toBe('prio-3')
  })
})

describe('recurrenceLabel', () => {
  it('labels recurrences', () => {
    expect(recurrenceLabel('daily')).toBe('Repeats daily')
    expect(recurrenceLabel('weekly')).toBe('Repeats weekly')
    expect(recurrenceLabel('monthly')).toBe('Repeats monthly')
    expect(recurrenceLabel(null)).toBe('')
  })
})

describe('reminderPresets', () => {
  it('offers only future presets', () => {
    const due = new Date(NOW.getTime() + 45 * 60 * 1000).toISOString() // in 45 min
    const labels = reminderPresets(due, NOW).map((p) => p.label)
    expect(labels).toContain('At due time')
    expect(labels).toContain('30 min before')
    expect(labels).not.toContain('1 hour before')
    expect(labels).not.toContain('1 day before')
  })
  it('returns all four when due is far away', () => {
    const due = new Date(NOW.getTime() + 3 * 86400 * 1000).toISOString()
    expect(reminderPresets(due, NOW)).toHaveLength(4)
  })
  it('returns empty without a due date', () => {
    expect(reminderPresets(null, NOW)).toEqual([])
  })
})

describe('timeAgo', () => {
  it('humanizes recent times', () => {
    const fiveMin = new Date(NOW.getTime() - 5 * 60 * 1000).toISOString()
    expect(timeAgo(fiveMin, NOW)).toBe('5m ago')
    const twoH = new Date(NOW.getTime() - 2 * 3600 * 1000).toISOString()
    expect(timeAgo(twoH, NOW)).toBe('2h ago')
    const threeD = new Date(NOW.getTime() - 3 * 86400 * 1000).toISOString()
    expect(timeAgo(threeD, NOW)).toBe('3d ago')
    expect(timeAgo(new Date(NOW.getTime() - 20000).toISOString(), NOW)).toBe('just now')
  })
})
