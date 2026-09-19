import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import SystemStatusView from '@/views/public/SystemStatusView.vue'

describe('system status', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the localized active maintenance window', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        maintenance: {
          title: 'Scheduled maintenance',
          message: 'Uploads may be unavailable.',
          starts_at: '2026-09-20T01:00:00Z',
          ends_at: '2026-09-20T02:00:00Z',
        },
        checked_at: '2026-09-20T01:30:00Z',
      }),
    }))

    const wrapper = mount(SystemStatusView, { global: { plugins: [i18n] } })
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('System status and maintenance')
    expect(wrapper.text()).toContain('Scheduled maintenance')
    expect(wrapper.text()).toContain('Uploads may be unavailable.')
  })
})
