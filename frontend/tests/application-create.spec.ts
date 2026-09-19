import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import { useClassificationStore } from '@/stores/classification'
import ApplicationCreateView from '@/views/applicant/ApplicationCreateView.vue'

const Page = { template: '<div />' }
const jsonResponse = (body: unknown) => ({
  status: 200,
  ok: true,
  headers: new Headers({ 'content-type': 'application/json' }),
  json: vi.fn().mockResolvedValue(body),
})

describe('application address creation', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.sessionStorage.clear()
  })

  it('submits a stable subdistrict code and never sends independently typed location values', async () => {
    i18n.global.locale.value = 'en'
    const pinia = createPinia()
    setActivePinia(pinia)
    const classification = useClassificationStore()
    classification.updateRooms('20')
    classification.updateGuests('40')
    classification.updateRestaurant(false)

    const locationCatalog = {
      province: { code: '83', name: 'Phuket' },
      districts: [{
        code: '8302',
        name: 'Kathu',
        subdistricts: [{ code: '830202', name: 'Patong', postal_code: '83150' }],
      }],
    }
    const authority = { id: 4, code: 'PATONG_MUNICIPALITY', name: 'Patong Municipality' }
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST') {
        return Promise.resolve(jsonResponse({ id: 9, status: 'DRAFT' }))
      }
      if (url.includes('/locations/phuket/')) return Promise.resolve(jsonResponse(locationCatalog))
      return Promise.resolve(jsonResponse({ count: 1, next: null, previous: null, results: [authority] }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/applications/new', name: 'application-create', component: ApplicationCreateView },
        { path: '/applications/:id/documents', name: 'application-documents', component: Page },
      ],
    })
    await router.push('/applications/new')
    await router.isReady()
    const wrapper = mount(ApplicationCreateView, { global: { plugins: [pinia, i18n, router] } })
    await flushPromises()

    expect(wrapper.get('#create-address-province').attributes('readonly')).toBeDefined()
    expect(wrapper.get('#create-address-postal-code').attributes('readonly')).toBeDefined()
    await wrapper.get('#name').setValue('Demo stay')
    await wrapper.get('#address_line').setValue('93 Demo Road')
    await wrapper.get('#create-address-district').setValue('8302')
    await wrapper.get('#create-address-subdistrict').setValue('830202')
    await wrapper.get('#local-authority').setValue('4')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const postCall = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === 'POST')
    const body = JSON.parse(String((postCall?.[1] as RequestInit).body))
    expect(body.property).toEqual({
      name: 'Demo stay',
      address_line: '93 Demo Road',
      subdistrict_code: '830202',
      local_authority_id: 4,
    })
    expect(body.classification_answers).toEqual({ rooms: 20, guests: 40, has_restaurant: false })
    expect(router.currentRoute.value.name).toBe('application-documents')
    wrapper.unmount()
  })
})
