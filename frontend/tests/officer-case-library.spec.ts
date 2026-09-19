import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import OfficerCaseLibraryView from '@/views/officer/OfficerCaseLibraryView.vue'

function response(payload: unknown) {
  return {
    status: 200,
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(payload),
  }
}

describe('officer case library', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('searches structured de-identified cases and shows database FAQs', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/property-types/')) {
        return Promise.resolve(response({
          count: 1,
          next: null,
          previous: null,
          results: [{ id: 1, code: 'TYPE_1', name: 'Accommodation Type 1', issues_license: true }],
        }))
      }
      return Promise.resolve(response({
        count: 1,
        next: null,
        previous: null,
        results: [{
          case_reference: 'CASE-ABC1234567',
          decision: 'APPROVED',
          property_type: { id: 1, code: 'TYPE_1', name: 'Accommodation Type 1', issues_license: true },
          classification: { rooms: 20, guests: 40, has_restaurant: false, outcome: 'TYPE_1' },
          revision_rounds: 1,
          processing_days: 5,
          decided_at: '2026-09-20T06:00:00Z',
          documents: { required: 5, current_approved: 5, versions_reviewed: 6 },
        }],
        faqs: [{
          slug: 'similar-cases',
          question: 'Can a similar case replace review?',
          answer: 'No. Review the current facts and documents.',
          updated_at: '2026-09-20T06:00:00Z',
        }],
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/officer/cases', name: 'officer-case-library', component: OfficerCaseLibraryView },
        { path: '/officer/applications', name: 'officer-queue', component: { template: '<div />' } },
      ],
    })
    await router.push('/officer/cases')
    await router.isReady()
    const wrapper = mount(OfficerCaseLibraryView, { global: { plugins: [i18n, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('CASE-ABC1234567')
    expect(wrapper.text()).toContain('20 rooms / 40 guests')
    expect(wrapper.text()).toContain('Similar cases are reference material only')
    expect(wrapper.get('summary').text()).toBe('Can a similar case replace review?')
    expect(wrapper.text()).not.toContain('Applicant')
    expect(wrapper.text()).not.toContain('Address')

    await wrapper.get('#case-query').setValue('Type 1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('q=Type+1'),
      expect.objectContaining({ credentials: 'include' }),
    )
  })
})
