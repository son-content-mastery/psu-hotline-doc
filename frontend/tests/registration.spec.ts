import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import ActivateAccountView from '@/views/shared/ActivateAccountView.vue'
import RegisterView from '@/views/shared/RegisterView.vue'

const Page = { template: '<div />' }

function jsonResponse(status: number, body: unknown) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  }
}

function createAuthRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: Page },
      { path: '/register', name: 'register', component: RegisterView },
      { path: '/activate-account', name: 'activate-account', component: ActivateAccountView },
    ],
  })
}

describe('account registration and activation', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('creates only an applicant account request and shows the generic email handoff', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(202, { accepted: true }))
    vi.stubGlobal('fetch', fetchMock)
    const router = createAuthRouter()
    await router.push('/register?redirect=/applications')
    await router.isReady()
    const wrapper = mount(RegisterView, { global: { plugins: [createPinia(), i18n, router] } })

    await wrapper.get('#display-name').setValue('New applicant')
    await wrapper.get('#register-email').setValue('new@example.test')
    await wrapper.get('#register-password').setValue('Secure-passphrase-2026')
    await wrapper.get('#register-password-confirmation').setValue('Secure-passphrase-2026')
    await wrapper.get('#terms-accepted').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/auth/register/')
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit
    const body = JSON.parse(String(request.body)) as Record<string, unknown>
    expect(body).toMatchObject({
      display_name: 'New applicant',
      email: 'new@example.test',
      language: 'en',
      terms_accepted: true,
    })
    expect(body).not.toHaveProperty('role')
    expect(body).not.toHaveProperty('local_authority')
    expect(body).not.toHaveProperty('is_staff')
    expect(wrapper.text()).toContain('Check your email to verify the account')
    expect(wrapper.get('a').attributes('href')).toBe('/login?redirect=/applications')
    wrapper.unmount()
  })

  it('validates confirmation and consent before sending credentials', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const router = createAuthRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mount(RegisterView, { attachTo: document.body, global: { plugins: [createPinia(), i18n, router] } })

    await wrapper.get('#display-name').setValue('New applicant')
    await wrapper.get('#register-email').setValue('new@example.test')
    await wrapper.get('#register-password').setValue('first-password')
    await wrapper.get('#register-password-confirmation').setValue('different-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Enter the same password in both fields.')
    expect(wrapper.text()).toContain('Confirm this before creating the account.')
    expect(document.activeElement?.id).toBe('register-password-confirmation')
    wrapper.unmount()
  })

  it('presents server password-policy errors in the selected UI language', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Some fields are invalid.',
            fields: { password: ['This password is too common.'] },
          },
        }),
      ),
    )
    const router = createAuthRouter()
    await router.push('/register')
    await router.isReady()
    const wrapper = mount(RegisterView, { global: { plugins: [createPinia(), i18n, router] } })

    await wrapper.get('#display-name').setValue('New applicant')
    await wrapper.get('#register-email').setValue('new@example.test')
    await wrapper.get('#register-password').setValue('Password123')
    await wrapper.get('#register-password-confirmation').setValue('Password123')
    await wrapper.get('#terms-accepted').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('The new password does not meet the security requirements.')
    expect(wrapper.text()).not.toContain('This password is too common.')
    expect(wrapper.get('#register-password').attributes('aria-describedby')).toContain('registration-password-error')
    wrapper.unmount()
  })

  it('confirms a token and routes the verified user to sign in', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { activated: true }))
    vi.stubGlobal('fetch', fetchMock)
    const router = createAuthRouter()
    await router.push('/activate-account?token=signed-token')
    await router.isReady()
    const wrapper = mount(ActivateAccountView, { global: { plugins: [createPinia(), i18n, router] } })
    await flushPromises()

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/auth/activation/confirm/')
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({ token: 'signed-token' })
    expect(wrapper.text()).toContain('Your account is ready')
    expect(wrapper.get('a').attributes('href')).toBe('/login?notice=activated')
    wrapper.unmount()
  })

  it('offers a generic resend after an invalid or expired activation link', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(400, { error: { code: 'INVALID_ACTIVATION_TOKEN', message: 'Invalid activation token.' } }),
      )
      .mockResolvedValueOnce(jsonResponse(202, { accepted: true }))
    vi.stubGlobal('fetch', fetchMock)
    const router = createAuthRouter()
    await router.push('/activate-account?token=expired-token')
    await router.isReady()
    const wrapper = mount(ActivateAccountView, { global: { plugins: [createPinia(), i18n, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('This link cannot be used')
    await wrapper.get('#activation-email').setValue('new@example.test')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/auth/activation/resend/')
    expect(wrapper.text()).toContain('If an unverified account matches this email')
    wrapper.unmount()
  })
})
