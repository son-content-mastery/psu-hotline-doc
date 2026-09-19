import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import HomeView from '@/views/HomeView.vue'
import { i18n } from '@/i18n'

describe('public role gateway', () => {
  it('renders exactly the three allowed role options in order', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: HomeView },
        { path: '/classification/:step', name: 'classification-step', component: HomeView },
        { path: '/login', name: 'login', component: HomeView },
      ],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(HomeView, {
      global: {
        plugins: [createPinia(), i18n, router],
      },
    })

    const headings = wrapper.findAll('h2').map((heading) => heading.text())
    expect(headings).toEqual([
      'Accommodation operator / owner',
      'Local officer',
      'Central officer',
    ])
    expect(wrapper.findAll('ol > li')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('Super administrator')
  })
})
