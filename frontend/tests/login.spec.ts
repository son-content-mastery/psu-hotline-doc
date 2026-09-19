import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import LoginView from '@/views/shared/LoginView.vue'

const Page = { template: '<div />' }

describe('login experience', () => {
  it('lets the user reveal the password and reach password reset', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', name: 'login', component: LoginView },
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
  })
})
