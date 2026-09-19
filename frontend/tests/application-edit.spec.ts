import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import ApplicationEditView from '@/views/applicant/ApplicationEditView.vue'

const Page = { template: '<div />' }
const locationCatalog = {
  province: { code: '83', name: 'Phuket' },
  districts: [
    {
      code: '8302',
      name: 'Kathu',
      subdistricts: [
        { code: '830201', name: 'Kathu', postal_code: '83120' },
        { code: '830202', name: 'Patong', postal_code: '83150' },
      ],
    },
  ],
}
const jsonResponse = (body: unknown) => ({
  status: 200,
  ok: true,
  headers: new Headers({ 'content-type': 'application/json' }),
  json: vi.fn().mockResolvedValue(body),
})

describe('application editing', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads owned draft details and saves property plus classification changes', async () => {
    i18n.global.locale.value = 'en'
    const application = {
      id: 7,
      reference_number: null,
      status: 'DRAFT',
      property: {
        name: 'Old stay', address_line: '1 Road', subdistrict: 'Patong', district: 'Kathu',
        province: 'Phuket', postal_code: '83150', province_code: '83', district_code: '8302',
        subdistrict_code: '830202', local_authority: { id: 1, code: 'PATONG', name: 'Patong' },
      },
      responsible_authority: { id: 1, code: 'PATONG', name: 'Patong' },
      classification: { outcome: 'TYPE_1', property_type: { code: 'TYPE_1', name: 'Type 1' }, answers: { rooms: 20, guests: 40, has_restaurant: false } },
    }
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'PATCH') return Promise.resolve(jsonResponse(application))
      if (url.includes('/locations/phuket/')) return Promise.resolve(jsonResponse(locationCatalog))
      if (url.includes('/local-authorities/')) return Promise.resolve(jsonResponse({ count: 1, next: null, previous: null, results: [application.responsible_authority] }))
      return Promise.resolve(jsonResponse(application))
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/applications/:id/edit', name: 'application-edit', component: ApplicationEditView },
        { path: '/applications/:id/documents', name: 'application-documents', component: Page },
        { path: '/applications/:id/tracking', name: 'application-tracking', component: Page },
      ],
    })
    await router.push('/applications/7/edit')
    await router.isReady()
    const wrapper = mount(ApplicationEditView, { global: { plugins: [i18n, router] } })
    await flushPromises()

    await wrapper.get('#edit-name').setValue('Updated stay')
    await wrapper.get('#edit-address-subdistrict').setValue('830201')
    await wrapper.get('input[type="number"]').setValue('18')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const patchCall = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === 'PATCH')
    expect(patchCall?.[0]).toBe('/api/v1/applications/7/')
    expect(JSON.parse(String((patchCall?.[1] as RequestInit).body))).toMatchObject({
      property: { name: 'Updated stay', subdistrict_code: '830201', local_authority_id: 1 },
      classification_answers: { rooms: 18, guests: 40, has_restaurant: false },
    })
    expect(JSON.parse(String((patchCall?.[1] as RequestInit).body)).property).not.toHaveProperty('postal_code')
    expect(router.currentRoute.value.name).toBe('application-documents')
    wrapper.unmount()
  })
})
