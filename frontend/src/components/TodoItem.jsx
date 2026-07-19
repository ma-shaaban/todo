import { useAuth } from '../auth.jsx'
import { dueLabel, isOverdue, priorityMeta, recurrenceLabel } from '../format.js'

export default function TodoItem({ todo, onToggle, onOpen, spaceName }) {
  const { user } = useAuth()
  const done = Boolean(todo.completed_at)
  const isEach = todo.completion_mode === 'each'
  const myRow = isEach ? todo.assignees?.find((a) => a.id === user?.id) : null
  const myChecked = Boolean(myRow?.completed_at)
  const checkedCount = isEach ? todo.assignees?.filter((a) => a.completed_at).length || 0 : 0
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
        className={`check ${!done && myChecked ? 'self-done' : ''}`}
        aria-label={done || myChecked ? 'Reopen' : 'Complete'}
        // In 'each' mode the circle is MY box; others' boxes are theirs.
        disabled={isEach && !myRow}
        title={isEach && !myRow ? 'Not assigned to you' : undefined}
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
          {isEach && (
            <span
              className="chip"
              title={todo.assignees
                ?.map((a) => `${a.completed_at ? '✓' : '○'} ${a.display_name}`)
                .join('  ')}
            >
              👥 {checkedCount}/{todo.assignees?.length || 0}
            </span>
          )}
          {todo.recurrence && <span>🔁 {recurrenceLabel(todo.recurrence).replace('Repeats ', '')}</span>}
          {todo.assignee && <span className="avatar" title={todo.assignee.display_name}>{initials}</span>}
          {todo.reminders?.some((r) => !r.fired_at) && <span>⏰</span>}
        </div>
      </div>
    </div>
  )
}
