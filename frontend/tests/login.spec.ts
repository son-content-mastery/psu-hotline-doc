import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import LoginView from '@/views/shared/LoginView.vue'

const Page = { template: '<div />' }

describe('login experience', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lets the user reveal the password and reach password reset', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', name: 'login', component: LoginView },
        { path: '/register', name: 'register', component: Page },
        { path: '/forgot-password', name: 'forgot-password', component: Page },
      ],
    })
    await router.push('/login')
    await router.isReady()
    const wrapper = mount(LoginView, {
      global: { plugins: [createPinia(), i18n, router] },
    })

    const password = wrapper.get<HTMLInputElement>('#password')
    expect(password.attributes('type')).toBe('password')
    const toggle = wrapper.get<HTMLButtonElement>('button[aria-pressed]')
    expect(toggle.text()).toBe('Show password')
    await toggle.trigger('click')
    expect(password.attributes('type')).toBe('text')
    expect(toggle.attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('a[href="/forgot-password"]').text()).toBe('Forgot your password?')
    expect(wrapper.get('a[href="/register"]').text()).toBe('Create an applicant account')
    wrapper.unmount()
  })

  it('blocks an unverified account and offers a privacy-safe resend action', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', name: 'login', component: LoginView },
        { path: '/register', name: 'register', component: Page },
        { path: '/forgot-password', name: 'forgot-password', component: Page },
      ],
    })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        status: 403,
        ok: false,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({
          error: { code: 'EMAIL_NOT_VERIFIED', message: 'Verify your email before signing in.' },
        }),
      })
      .mockResolvedValueOnce({
        status: 202,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ accepted: true }),
      })
    vi.stubGlobal('fetch', fetchMock)
    await router.push('/login')
    await router.isReady()
    const wrapper = mount(LoginView, {
      global: { plugins: [createPinia(), i18n, router] },
    })

    await wrapper.get('#email').setValue('new@example.test')
    await wrapper.get('#password').setValue('Secure-passphrase-2026')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('This account has not verified its email.')
    const resend = wrapper.get<HTMLButtonElement>('button.button-secondary')
    await resend.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/auth/activation/resend/')
    expect(wrapper.text()).toContain('If an unverified account matches this email')
    wrapper.unmount()
  })
})
