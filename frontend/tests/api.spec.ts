import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, setUnauthorizedHandler } from '@/services/api'

describe('API client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setUnauthorizedHandler()
    document.cookie = 'csrftoken=; Max-Age=0; path=/'
  })

  it('sends same-origin credentials, locale, JSON, and CSRF on mutations', async () => {
    document.documentElement.lang = 'en'
    document.cookie = 'csrftoken=test-token; path=/'
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({ ok: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await api.post('/api/v1/example/', { answer: true })

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = options.headers as Headers
    expect(options.credentials).toBe('include')
    expect(options.method).toBe('POST')
    expect(headers.get('Accept-Language')).toBe('en')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('X-CSRFToken')).toBe('test-token')
  })

  it('preserves the documented error code and field errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 409,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({
          error: {
            code: 'MISSING_REQUIRED_DOCUMENTS',
            message: 'Missing documents.',
            fields: { missing_document_type_ids: ['1'] },
          },
        }),
      }),
    )

    await expect(api.post('/api/v1/applications/1/submit/', {})).rejects.toMatchObject({
      status: 409,
      code: 'MISSING_REQUIRED_DOCUMENTS',
      fields: { missing_document_type_ids: ['1'] },
    })
  })

  it('notifies the application when a protected request returns 401', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'AUTHENTICATION_REQUIRED' } }),
      }),
    )

    await expect(api.get('/api/v1/applications/1/')).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).toHaveBeenCalledTimes(1)
  })

  it('keeps invalid-login 401 responses local to the login form', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'INVALID_CREDENTIALS' } }),
      }),
    )

    await expect(api.post('/api/v1/auth/login/', {})).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('does not treat an unrelated 401 error code as session expiry', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'INVALID_CREDENTIALS' } }),
      }),
    )

    await expect(api.get('/api/v1/example/')).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('lets logout handle an already-expired session locally', async () => {
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'AUTHENTICATION_REQUIRED' } }),
      }),
    )

    await expect(api.post('/api/v1/auth/logout/')).rejects.toMatchObject({ status: 401 })
    expect(unauthorized).not.toHaveBeenCalled()
  })
})
