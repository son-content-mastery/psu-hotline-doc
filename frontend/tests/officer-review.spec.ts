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
    const fetchMock = vi.fn().mockResolvedValue({
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
          allowed_actions: ['REVIEW_DOCUMENTS', 'REQUEST_REVISION', 'REJECT'],
          history: [
            { id: 1, from_status: 'SUBMITTED', to_status: 'UNDER_REVIEW', occurred_at: '2026-09-18T05:00:00Z', reason: 'Review started' },
          ],
          documents: [
            {
              id: 22,
              document_type: { id: 3, code: 'IDENTITY', name: 'Identity evidence' },
              version: 2,
              status: 'UPLOADED',
              is_current: true,
              version_label: 'CURRENT',
              category: 'OPERATOR_PREPARED',
              original_filename: 'identity-v2.pdf',
              uploaded_at: '2026-09-18T04:00:00Z',
              uploaded_by: { id: 1, display_name: 'Demo applicant', role: 'APPLICANT' },
              uploader_role: 'APPLICANT',
              preflight: {
                status: 'WARNING',
                issue_codes: ['LOW_RESOLUTION'],
                analyzer_version: 'quality-v1',
                analyzed_at: '2026-09-18T04:00:01Z',
              },
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
      })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OfficerReviewView, { global: { plugins: [i18n, router] } })
    await flushPromises()
    const text = wrapper.text()

    expect(text).toContain('Current')
    expect(text).toContain('Previous · Version 1')
    expect(text).toContain('Demo applicant · Applicant')
    expect(text).toContain('Application decision history')
    expect(text).toContain('Reason: Review started')
    expect(text).toContain('The image resolution may be too low')
    expect(wrapper.findAll('button').some((button) => button.text().includes('Return application for correction'))).toBe(true)
    expect(wrapper.findAll('button').some((button) => button.text().includes('Reject application'))).toBe(true)
    expect(text).not.toContain('Approve and issue licence')

    const reviewForm = wrapper.get('[data-testid="document-review-form"]')
    await reviewForm.get('input[value="REVISION_REQUIRED"]').setValue()
    expect(reviewForm.find('textarea').exists()).toBe(true)
    await reviewForm.get('textarea').setValue('Please replace the unclear page.')

    await reviewForm.get('input[value="APPROVED"]').setValue()
    expect(reviewForm.find('textarea').exists()).toBe(false)
    expect(reviewForm.text()).not.toContain('Reason the applicant will see')
    expect(reviewForm.text()).toContain('Record document review')

    await reviewForm.trigger('submit')
    await flushPromises()
    const reviewRequest = fetchMock.mock.calls.find(([url]) => url === '/api/v1/officer/documents/22/review/')
    expect(reviewRequest).toBeDefined()
    expect(JSON.parse(String((reviewRequest?.[1] as RequestInit).body))).toEqual({ outcome: 'APPROVED' })
    wrapper.unmount()
  })
})
