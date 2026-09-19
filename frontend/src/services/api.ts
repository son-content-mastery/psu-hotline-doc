import type { ApiErrorPayload } from '@/types/api'

type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | undefined

export function setUnauthorizedHandler(handler?: UnauthorizedHandler): void {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly fields: Record<string, string[]>

  constructor(status: number, payload?: ApiErrorPayload) {
    super(payload?.error?.message ?? 'Request failed')
    this.name = 'ApiError'
    this.status = status
    this.code = payload?.error?.code ?? 'UNKNOWN_ERROR'
    this.fields = payload?.error?.fields ?? {}
  }
}

function getCookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`
  return document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  headers.set('Accept-Language', document.documentElement.lang === 'en' ? 'en' : 'th')

  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    const csrfToken = getCookie('csrftoken')
    if (csrfToken) headers.set('X-CSRFToken', decodeURIComponent(csrfToken))
  }

  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 204) return undefined as T

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson ? ((await response.json()) as T | ApiErrorPayload) : undefined

  if (!response.ok) {
    const error = new ApiError(response.status, payload as ApiErrorPayload | undefined)
    if (
      response.status === 401 &&
      error.code === 'AUTHENTICATION_REQUIRED' &&
      path !== '/api/v1/auth/logout/'
    ) {
      unauthorizedHandler?.()
    }
    throw error
  }
  return payload as T
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value)
}

export const api = {
  get: <T>(path: string, options?: RequestInit) => request<T>(path, options),
  post: <T>(path: string, body?: unknown, options?: RequestInit) =>
    request<T>(path, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : jsonBody(body ?? {}),
    }),
  patch: <T>(path: string, body: unknown, options?: RequestInit) =>
    request<T>(path, { ...options, method: 'PATCH', body: jsonBody(body) }),
}
