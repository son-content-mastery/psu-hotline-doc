import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import OfficerReviewView from '@/views/officer/OfficerReviewView.vue'

const Page = { template: '<div />' }

describe('officer application review', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses server allowed actions and separates current and previous file versions', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/officer/applications', name: 'officer-queue', component: Page, meta: { titleKey: 'routes.officerQueue' } },
        {
          path: '/officer/applications/:id',
          name: 'officer-review',
          component: OfficerReviewView,
          meta: { titleKey: 'routes.officerReview' },
        },
      ],
    })
    await router.push('/officer/applications/9')
    await router.isReady()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({
          id: 9,
          reference_number: 'HTL-TEST-0009',
          status: 'UNDER_REVIEW',
          waiting_since: '2026-09-18T05:00:00Z',
          submitted_at: '2026-09-17T05:00:00Z',
          resubmitted_at: '2026-09-18T05:00:00Z',
          property: { name: 'Demo Stay', local_authority: { id: 1, code: 'PATONG', name: 'Patong' } },
          classification: { outcome: 'TYPE_1', property_type: { code: 'TYPE_1', name: 'Type 1' }, answers: { rooms: 10, guests: 20, has_restaurant: false } },
          all_required_documents_approved: false,
          allowed_actions: ['REQUEST_REVISION', 'REJECT'],
          documents: [
            {
              id: 22,
              document_type: { id: 3, code: 'IDENTITY', name: 'Identity evidence' },
              version: 2,
              status: 'REVISION_REQUIRED',
              is_current: true,
              version_label: 'CURRENT',
              category: 'OPERATOR_PREPARED',
              original_filename: 'identity-v2.pdf',
              uploaded_at: '2026-09-18T04:00:00Z',
              uploaded_by: { id: 1, display_name: 'Demo applicant', role: 'APPLICANT' },
              uploader_role: 'APPLICANT',
              reviews: [],
              versions: [
                {
                  id: 21,
                  document_type: { id: 3, code: 'IDENTITY', name: 'Identity evidence' },
                  version: 1,
                  status: 'REJECTED',
                  is_current: false,
                  version_label: 'PRIOR',
                  category: 'OPERATOR_PREPARED',
                  original_filename: 'identity-v1.pdf',
                  uploaded_at: '2026-09-17T04:00:00Z',
                  uploaded_by: { id: 1, display_name: 'Demo applicant', role: 'APPLICANT' },
                  uploader_role: 'APPLICANT',
                  reviews: [],
                },
              ],
            },
          ],
        }),
      }),
    )

    const wrapper = mount(OfficerReviewView, { global: { plugins: [i18n, router] } })
    await flushPromises()
    const text = wrapper.text()

    expect(text).toContain('Current')
    expect(text).toContain('Previous · Version 1')
    expect(text).toContain('Demo applicant · Applicant')
    expect(wrapper.findAll('button').some((button) => button.text().includes('Return application for correction'))).toBe(true)
    expect(wrapper.findAll('button').some((button) => button.text().includes('Reject application'))).toBe(true)
    expect(text).not.toContain('Approve and issue licence')
    expect(text).not.toContain('Record document review')
    wrapper.unmount()
  })
})
