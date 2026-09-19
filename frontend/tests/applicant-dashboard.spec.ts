import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import ApplicationListView from '@/views/applicant/ApplicationListView.vue'

const Page = { template: '<div />' }

const response = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      reference_number: null,
      property_name: 'Demo draft',
      property_type: { id: 1, code: 'TYPE_1', name: 'Accommodation Type 1' },
      responsible_authority: { id: 1, code: 'PATONG', name: 'Patong Municipality' },
      status: 'DRAFT',
      current_stage: 'APPLICANT_PREPARATION',
      applicant_action_required: false,
      waiting_since: null,
      requirements: { required: 5, approved: 0, current_uploads: 2, complete_for_submission: false },
      updated_at: '2026-09-19T05:00:00Z',
    },
    {
      id: 2,
      reference_number: 'HTL-2026-00002',
      property_name: 'Approved stay',
      property_type: { id: 1, code: 'TYPE_1', name: 'Accommodation Type 1' },
      responsible_authority: { id: 1, code: 'PATONG', name: 'Patong Municipality' },
      status: 'APPROVED',
      current_stage: 'COMPLETED',
      applicant_action_required: false,
      waiting_since: null,
      requirements: { required: 5, approved: 5, current_uploads: 5, complete_for_submission: true },
      updated_at: '2026-09-18T05:00:00Z',
    },
  ],
}

describe('applicant dashboard', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows identity, summary counts, classification and action-first filtering', async () => {
    i18n.global.locale.value = 'en'
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      email: 'applicant@example.test',
      display_name: 'Demo applicant',
      role: 'APPLICANT',
      local_authority: null,
    }
    auth.initialized = true
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/applications', name: 'application-list', component: ApplicationListView },
        { path: '/classification/:step', name: 'classification-step', component: Page },
        { path: '/applications/:id/documents', name: 'application-documents', component: Page },
        { path: '/applications/:id/edit', name: 'application-edit', component: Page },
        { path: '/applications/:id/review', name: 'application-review', component: Page },
        { path: '/applications/:id/tracking', name: 'application-tracking', component: Page },
      ],
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue(response),
      }),
    )
    await router.push('/applications')
    await router.isReady()
    const wrapper = mount(ApplicationListView, { global: { plugins: [pinia, i18n, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Welcome, Demo applicant')
    expect(wrapper.text()).toContain('Patong Municipality')
    expect(wrapper.text()).toContain('Current documents: 2 of 5 required')
    expect(wrapper.text()).toContain('Edit accommodation details')
    expect(wrapper.text()).not.toContain('Approved stay')

    await wrapper.get('select#application-filter').setValue('all')
    await flushPromises()
    expect(wrapper.text()).toContain('Approved stay')
    wrapper.unmount()
  })
})
