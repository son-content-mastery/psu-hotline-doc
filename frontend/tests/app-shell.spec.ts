import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const Page = { template: '<div />' }

describe('application shell', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('clears local identity and returns home even when logout fails', async () => {
    i18n.global.locale.value = 'en'
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: Page, meta: { titleKey: 'routes.home' } },
        {
          path: '/applications',
          name: 'application-list',
          component: Page,
          meta: { titleKey: 'routes.applications', requiresAuth: true, roles: ['APPLICANT'] },
        },
      ],
    })
    await router.push('/applications')
    await router.isReady()
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      email: 'applicant@example.test',
      display_name: 'Demo applicant',
      role: 'APPLICANT',
      local_authority: null,
    }
    auth.initialized = true
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 500,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ error: { code: 'SERVER_ERROR' } }),
      }),
    )

    const wrapper = mount(AppShell, {
      slots: { default: '<p>Protected application data</p>' },
      global: { plugins: [pinia, i18n, router] },
    })
    await wrapper.get('button.button-secondary').trigger('click')
    await flushPromises()

    expect(auth.user).toBeNull()
    expect(router.currentRoute.value.name).toBe('home')
    wrapper.unmount()
  })
})
