import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import ApplicationDocumentsView from '@/views/applicant/ApplicationDocumentsView.vue'

const Page = { template: '<div />' }

function jsonResponse(payload: unknown) {
  return {
    status: 200,
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(payload),
  }
}

describe('step-based applicant document flow', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows exact overall and per-step progress and keeps steps non-linear', async () => {
    i18n.global.locale.value = 'en'
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/applications/:id/documents', name: 'application-documents', component: ApplicationDocumentsView },
        { path: '/applications/:id/review', name: 'application-review', component: Page },
      ],
    })
    await router.push('/applications/7/documents')
    await router.isReady()

    const identity = {
      requirement_id: 1,
      document_type: {
        id: 11,
        code: 'APPLICANT_ID_CARD',
        name: 'Applicant identity card',
        category: 'OPERATOR_PREPARED',
        allows_multiple_files: false,
      },
      required: true,
      step_code: 'APPLICANT',
      status: 'MISSING',
      current_document_ids: [],
      guidance: null,
    }
    const parking = {
      requirement_id: 2,
      document_type: {
        id: 12,
        code: 'PARKING_PHOTOS',
        name: 'Parking photographs',
        category: 'OPERATOR_PREPARED',
        allows_multiple_files: true,
      },
      required: true,
      step_code: 'FACILITIES',
      status: 'UPLOADED',
      current_document_ids: [51, 52],
      guidance: null,
    }
    const requirements = {
      application_id: 7,
      property_type: { id: 1, code: 'TYPE_1', name: 'Type 1', issues_license: true },
      is_legally_validated_checklist: false,
      disclaimer: 'Confirm the checklist with the authority.',
      complete_for_submission: false,
      groups: [{ category: 'OPERATOR_PREPARED', items: [identity, parking] }, { category: 'EXTERNAL_AGENCY', items: [] }],
      steps: [
        { code: 'APPLICANT', order: 1, required: 1, completed: 0, action_required: 1, complete: false, items: [identity] },
        { code: 'FACILITIES', order: 2, required: 1, completed: 1, action_required: 0, complete: true, items: [parking] },
      ],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/documents/') && init?.method === 'POST') {
          return Promise.resolve(jsonResponse({
            id: 99,
            document_type: identity.document_type,
            version: 1,
            bundle_count: 1,
            attachment_index: 1,
            status: 'UPLOADED',
            is_current: true,
            original_filename: 'identity.pdf',
          }))
        }
        if (url.includes('/requirements/')) return Promise.resolve(jsonResponse(requirements))
        if (url.includes('/documents/')) {
          return Promise.resolve(jsonResponse({
            count: 2,
            next: null,
            previous: null,
            results: [
              {
                id: 51,
                document_type: parking.document_type,
                version: 1,
                attachment_index: 1,
                status: 'UPLOADED',
                is_current: true,
                original_filename: 'parking-1.png',
                preflight: {
                  status: 'WARNING',
                  issue_codes: ['POSSIBLY_BLURRY'],
                  analyzer_version: 'quality-v1',
                  type_check_status: 'NOT_APPLICABLE',
                  detected_family: null,
                  type_analyzer_version: 'ocr-family-v1',
                  analyzed_at: '2026-09-19T05:00:00Z',
                },
              },
              { id: 52, document_type: parking.document_type, version: 1, attachment_index: 2, status: 'UPLOADED', is_current: true, original_filename: 'parking-2.png' },
            ],
          }))
        }
        return Promise.resolve(jsonResponse({
          id: 7,
          reference_number: null,
          status: 'DRAFT',
          property: { name: 'Demo stay' },
          classification: { outcome: 'TYPE_1', property_type: { code: 'TYPE_1', name: 'Type 1' }, answers: { rooms: 20, guests: 40, has_restaurant: false } },
        }))
      }),
    )

    const wrapper = mount(ApplicationDocumentsView, { global: { plugins: [i18n, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('1 of 2 items ready')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('50')
    expect(wrapper.text()).toContain('Applicant and business')
    expect(wrapper.text()).toContain('Applicant identity card')
    expect(wrapper.text()).toContain('0/1 items')
    expect(wrapper.text()).not.toContain('Upload selected files')

    const identityInput = wrapper.get('input[type="file"]')
    Object.defineProperty(identityInput.element, 'files', {
      configurable: true,
      value: [new File(['demo'], 'identity.pdf', { type: 'application/pdf' })],
    })
    await identityInput.trigger('change')
    await flushPromises()
    const uploadCalls = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(uploadCalls).toHaveLength(1)

    const facilitiesButton = wrapper.findAll('nav button').find((button) => button.text().includes('Rooms and facilities'))
    expect(facilitiesButton).toBeTruthy()
    await facilitiesButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Parking photographs')
    expect(wrapper.get('input[type="file"]').attributes('multiple')).toBeDefined()
    expect(wrapper.text()).toContain('Current evidence bundle: 2 file(s)')
    expect(wrapper.text()).toContain('Check this file before submitting')
    expect(wrapper.text()).toContain('may be blurred or out of focus')
    expect(wrapper.text()).toContain('OCR is not applicable to this photo')
    wrapper.unmount()
  })
})
