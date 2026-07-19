// Tiny JSON API client. Session auth rides on the httponly cookie, so
// there's no token handling here — just JSON in/out and error normalizing.

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// Own event bus (not window) so auth handling is testable everywhere.
export const authEvents = new EventTarget()

export async function api(path, { method = 'GET', body } = {}) {
  let res
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { 'content-type': 'application/json' } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Network error — check your connection')
  }
  if (res.status === 204) return null
  let data = null
  try {
    data = await res.json()
  } catch {
    // Non-JSON response (shouldn't happen on /api/*) — fall through.
  }
  if (!res.ok) {
    if (res.status === 401) {
      authEvents.dispatchEvent(new Event('auth:required'))
    }
    const message = (data && data.detail) || `Something went wrong (${res.status})`
    throw new ApiError(res.status, typeof message === 'string' ? message : 'Invalid input')
  }
  return data
}
