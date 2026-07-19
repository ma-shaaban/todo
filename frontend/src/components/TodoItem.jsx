import { dueLabel, isOverdue, priorityMeta, recurrenceLabel } from '../format.js'

export default function TodoItem({ todo, onToggle, onOpen, spaceName }) {
  const done = Boolean(todo.completed_at)
  const prio = priorityMeta(todo.priority)
  const overdue = !done && isOverdue(todo.due_at)
  const initials = (todo.assignee?.display_name || '')
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className={`todo ${done ? 'done' : ''}`}>
      <button
        className="check"
        aria-label={done ? 'Reopen' : 'Complete'}
        onClick={() => onToggle(todo)}
      >
        ✓
      </button>
      <div className="body" onClick={() => onOpen(todo)}>
        <div className="title">{todo.title}</div>
        <div className="sub">
          {spaceName && <span className="chip">{spaceName}</span>}
          {todo.due_at && (
            <span className={overdue ? 'overdue' : ''}>{dueLabel(todo.due_at)}</span>
          )}
          {prio.label && <span className={`chip ${prio.className}`}>{prio.label}</span>}
          {todo.recurrence && <span>🔁 {recurrenceLabel(todo.recurrence).replace('Repeats ', '')}</span>}
          {todo.assignee && <span className="avatar" title={todo.assignee.display_name}>{initials}</span>}
          {todo.reminders?.some((r) => !r.fired_at) && <span>⏰</span>}
        </div>
      </div>
    </div>
  )
}
