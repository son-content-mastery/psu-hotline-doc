import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ApplicationDiscussion from '@/components/ApplicationDiscussion.vue'
import { i18n } from '@/i18n'

describe('application discussion', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads immutable messages and sends a trimmed message', async () => {
    i18n.global.locale.value = 'en'
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ results: [] }),
      })
      .mockResolvedValueOnce({
        status: 201,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({
          id: 1,
          sender_category: 'APPLICANT',
          body: 'Please check page two.',
          created_at: '2026-09-20T01:00:00Z',
        }),
      })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(ApplicationDiscussion, {
      props: { endpoint: '/api/v1/applications/4/discussion/', canPost: true },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    await wrapper.get('textarea').setValue('  Please check page two.  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const sendRequest = fetchMock.mock.calls.at(1)
    expect(sendRequest).toBeDefined()
    expect(JSON.parse(String((sendRequest?.[1] as RequestInit).body))).toEqual({ body: 'Please check page two.' })
    expect(wrapper.text()).toContain('Please check page two.')
    expect(wrapper.text()).toContain('Applicant')
  })
})
