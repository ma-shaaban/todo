import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError, authEvents } from '../api.js'

const jsonResponse = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('returns parsed JSON on success', async () => {
    fetch.mockResolvedValue(jsonResponse(200, { hello: 'world' }))
    expect(await api('/api/hello')).toEqual({ hello: 'world' })
  })

  it('sends JSON bodies with the right method and headers', async () => {
    fetch.mockResolvedValue(jsonResponse(201, { ok: true }))
    await api('/api/things', { method: 'POST', body: { a: 1 } })
    const [url, opts] = fetch.mock.calls[0]
    expect(url).toBe('/api/things')
    expect(opts.method).toBe('POST')
    expect(opts.headers['content-type']).toBe('application/json')
    expect(JSON.parse(opts.body)).toEqual({ a: 1 })
  })

  it('throws ApiError with the server detail', async () => {
    fetch.mockResolvedValue(jsonResponse(400, { detail: 'Please enter a title' }))
    await expect(api('/api/x')).rejects.toMatchObject({ status: 400, message: 'Please enter a title' })
  })

  it('emits auth:required on 401', async () => {
    fetch.mockResolvedValue(jsonResponse(401, { detail: 'Not authenticated' }))
    const handler = vi.fn()
    authEvents.addEventListener('auth:required', handler)
    await expect(api('/api/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledOnce()
    authEvents.removeEventListener('auth:required', handler)
  })

  it('wraps network failures in ApiError with status 0', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(api('/api/x')).rejects.toMatchObject({ status: 0 })
  })
})
