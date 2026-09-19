import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { api } from '@/services/api'
import { installSessionExpiryHandler, safeRelativeRedirect } from '@/services/sessionExpiry'
import { useAuthStore } from '@/stores/auth'
import { CLASSIFICATION_SESSION_KEY } from '@/stores/classification'

const Page = { template: '<div />' }

describe('expired session handling', () => {
  let uninstall: (() => void) | undefined

  afterEach(() => {
    uninstall?.()
    uninstall = undefined
    vi.unstubAllGlobals()
  })

  it.each([
    ['https://evil.example/path', '/fallback'],
    ['//evil.example/path', '/fallback'],
    ['/\\evil.example/path', '/fallback'],
    ['', '/fallback'],
    ['/applications/7/tracking?tab=history#latest', '/applications/7/tracking?tab=history#latest'],
  ])('sanitizes return URL %s', (input, expected) => {
    expect(safeRelativeRedirect(input, '/fallback')).toBe(expected)
  })

  it('clears identity and returns a protected page to the role-aware login', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', name: 'login', component: Page, meta: { titleKey: 'routes.login' } },
        {
          path: '/officer/applications/9',
          name: 'officer-review-test',
          component: Page,
          meta: { titleKey: 'routes.officerReview', requiresAuth: true, roles: ['LOCAL_OFFICER'] },
        },
      ],
    })
    await router.push('/officer/applications/9?from=queue')
    await router.isReady()

    const auth = useAuthStore()
    auth.user = {
      id: 2,
      email: 'officer@example.test',
      display_name: 'Demo officer',
      role: 'LOCAL_OFFICER',
      local_authority: null,
    }
    auth.initialized = true
    window.sessionStorage.setItem(CLASSIFICATION_SESSION_KEY, '{"rooms":"8"}')
    uninstall = installSessionExpiryHandler(router, pinia)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'AUTHENTICATION_REQUIRED' } }),
      }),
    )

    await expect(api.get('/api/v1/officer/applications/9/')).rejects.toMatchObject({ status: 401 })
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('login'))

    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.query).toEqual({
      intent: 'officer',
      redirect: '/officer/applications/9?from=queue',
      notice: 'expired',
    })
    expect(window.sessionStorage.getItem(CLASSIFICATION_SESSION_KEY)).toBe('{"rooms":"8"}')
  })

  it('does not disrupt an anonymous public flow', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'public-test', component: Page, meta: { titleKey: 'routes.home' } },
        { path: '/login', name: 'login', component: Page, meta: { titleKey: 'routes.login' } },
      ],
    })
    await router.push('/')
    await router.isReady()
    uninstall = installSessionExpiryHandler(router, pinia)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'AUTHENTICATION_REQUIRED' } }),
      }),
    )

    await expect(api.get('/api/v1/example/')).rejects.toMatchObject({ status: 401 })
    expect(router.currentRoute.value.name).toBe('public-test')
    expect(useAuthStore().authenticated).toBe(false)
  })
})
