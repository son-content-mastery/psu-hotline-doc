import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import ProviderDirectoryView from '@/views/public/ProviderDirectoryView.vue'

describe('provider directory', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows source status, reference pricing, and the non-endorsement disclaimer', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        disclaimer: 'Listings are informational only and are not endorsed.',
        results: [{
          id: 1,
          name: 'Demo Provider',
          services: ['APPLICATION_SUPPORT'],
          price: { min: '2500.00', max: '8000.00', currency: 'THB', note: 'Fictional range.' },
          contact_url: 'https://provider.example.test',
          source_url: null,
          source_status: 'DEMO_ONLY',
          source_checked_at: '2026-09-20',
        }],
      }),
    }))
    const wrapper = mount(ProviderDirectoryView, { global: { plugins: [i18n] } })
    await flushPromises()
    expect(wrapper.text()).toContain('not endorsed')
    expect(wrapper.text()).toContain('Fictional demo listing—not a real provider')
    expect(wrapper.text()).toContain('Demo Provider')
    expect(wrapper.get('a').attributes('rel')).toContain('noopener')
  })
})
