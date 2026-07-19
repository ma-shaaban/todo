import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { isoToLocalInput, localInputToIso, reminderPresets } from '../format.js'

const EMPTY = {
  title: '',
  notes: '',
  due_at: null,
  priority: 0,
  assignee_id: null,
  recurrence: null,
  reminders: [],
}

/** Create/edit sheet. `todo` = existing todo or null (create). */
export default function TodoEditor({ spaceId, todo, members, onSaved, onDeleted, onClose }) {
  const [form, setForm] = useState(EMPTY)
  const [customReminder, setCustomReminder] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (todo) {
      setForm({
        title: todo.title,
        notes: todo.notes || '',
        due_at: todo.due_at,
        priority: todo.priority || 0,
        assignee_id: todo.assignee?.id || null,
        recurrence: todo.recurrence,
        reminders: todo.reminders.filter((r) => !r.fired_at).map((r) => r.remind_at),
      })
    } else {
      setForm(EMPTY)
    }
    setError('')
  }, [todo?.id])

  const presets = useMemo(() => reminderPresets(form.due_at), [form.due_at])
  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const toggleReminder = (iso) =>
    set({
      reminders: form.reminders.includes(iso)
        ? form.reminders.filter((r) => r !== iso)
        : [...form.reminders, iso],
    })

  const addCustomReminder = () => {
    const iso = localInputToIso(customReminder)
    if (iso && !form.reminders.includes(iso)) {
      set({ reminders: [...form.reminders, iso] })
      setCustomReminder('')
    }
  }

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const body = { ...form }
      const saved = todo
        ? await api(`/api/todos/${todo.id}`, { method: 'PATCH', body })
        : await api(`/api/spaces/${spaceId}/todos`, { method: 'POST', body })
      onSaved(saved)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!confirm('Delete this todo?')) return
    setBusy(true)
    try {
      await api(`/api/todos/${todo.id}`, { method: 'DELETE' })
      onDeleted(todo)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="sheet-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet">
        <h2>{todo ? 'Edit todo' : 'New todo'}</h2>

        <div className="field">
          <label>Title</label>
          <input
            value={form.title}
            autoFocus={!todo}
            onChange={(e) => set({ title: e.target.value })}
            placeholder="What needs doing?"
          />
        </div>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
        </div>

        <div className="row">
          <div className="field">
            <label>Due</label>
            <input
              type="datetime-local"
              value={isoToLocalInput(form.due_at)}
              onChange={(e) => {
                const due = localInputToIso(e.target.value)
                set({ due_at: due, reminders: [], recurrence: due ? form.recurrence : null })
              }}
            />
          </div>
          <div className="field">
            <label>Priority</label>
            <select
              value={form.priority}
              onChange={(e) => set({ priority: Number(e.target.value) })}
            >
              <option value={0}>None</option>
              <option value={1}>Low</option>
              <option value={2}>Medium</option>
              <option value={3}>High</option>
            </select>
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>Assign to</label>
            <select
              value={form.assignee_id || ''}
              onChange={(e) => set({ assignee_id: e.target.value || null })}
            >
              <option value="">Nobody</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Repeat</label>
            <select
              value={form.recurrence || ''}
              disabled={!form.due_at}
              onChange={(e) => set({ recurrence: e.target.value || null })}
            >
              <option value="">Never</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>

        {form.due_at && (
          <div className="field">
            <label>Remind me</label>
            <div className="reminder-list">
              {presets.map((p) => (
                <label key={p.iso}>
                  <input
                    type="checkbox"
                    checked={form.reminders.includes(p.iso)}
                    onChange={() => toggleReminder(p.iso)}
                  />
                  {p.label}
                </label>
              ))}
              {form.reminders
                .filter((r) => !presets.some((p) => p.iso === r))
                .map((r) => (
                  <label key={r}>
                    <input type="checkbox" checked onChange={() => toggleReminder(r)} />
                    {new Date(r).toLocaleString()}
                  </label>
                ))}
              <div className="row">
                <input
                  type="datetime-local"
                  value={customReminder}
                  onChange={(e) => setCustomReminder(e.target.value)}
                />
                <button className="btn secondary" type="button" onClick={addCustomReminder}>
                  Add
                </button>
              </div>
            </div>
          </div>
        )}

        {error && <div className="error">{error}</div>}

        <div className="actions">
          {todo && (
            <button className="btn danger" disabled={busy} onClick={remove}>
              Delete
            </button>
          )}
          <button className="btn secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy || !form.title.trim()} onClick={save}>
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
