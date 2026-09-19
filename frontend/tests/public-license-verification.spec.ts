import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { i18n } from '@/i18n'
import LicenseView from '@/views/applicant/LicenseView.vue'
import PublicLicenseVerificationView from '@/views/public/PublicLicenseVerificationView.vue'

const token = '11111111-1111-4111-8111-111111111111'

function response(payload: unknown) {
  return {
    status: 200,
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(payload),
  }
}

const publicRecord = {
  status: 'VALID',
  artifact_kind: 'HOTEL_LICENSE',
  license_number: 'LIC-2026-00001',
  property: { name: 'Public Test Stay' },
  property_type: { id: 1, code: 'HOTEL_TYPE_1', name: 'Hotel type 1', issues_license: true },
  issuing_authority: { id: 1, code: 'PATONG', name: 'Patong Municipality' },
  issued_at: '2026-09-20T05:00:00Z',
  expires_at: '2031-09-19',
  checked_at: '2026-09-20T06:00:00Z',
}

describe('public licence verification', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the minimum public record without authentication or private fields', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(publicRecord)))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/verify/:token', component: PublicLicenseVerificationView }],
    })
    await router.push(`/verify/${token}`)
    await router.isReady()
    const wrapper = mount(PublicLicenseVerificationView, { global: { plugins: [i18n, router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Valid')
    expect(wrapper.text()).toContain('LIC-2026-00001')
    expect(wrapper.text()).toContain('Public Test Stay')
    expect(wrapper.text()).toContain('Patong Municipality')
    expect(wrapper.text()).not.toContain('Applicant')
    expect(wrapper.text()).not.toContain('Application reference')
    expect(fetch).toHaveBeenCalledWith(
      `/api/v1/public/licenses/${token}/`,
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('prints a QR verification link on the private licence record', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
      ...publicRecord,
      id: 1,
      application_reference_number: 'HD-2026-00001',
      property: { name: 'Public Test Stay', address: 'Private address' },
      fee: null,
      public_verification: {
        verification_url: `http://localhost:5173/verify/${token}`,
        qr_code_url: `/api/v1/public/licenses/${token}/qr/`,
      },
    })))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/applications/:id/license', name: 'application-license', component: LicenseView },
        { path: '/applications/:id/tracking', name: 'application-tracking', component: { template: '<div />' } },
      ],
    })
    await router.push('/applications/1/license')
    await router.isReady()
    const wrapper = mount(LicenseView, { global: { plugins: [i18n, router] } })
    await flushPromises()

    expect(wrapper.get('img').attributes('src')).toBe(`/api/v1/public/licenses/${token}/qr/`)
    expect(wrapper.get(`a[href="http://localhost:5173/verify/${token}"]`).text()).toContain('/verify/')
  })
})
