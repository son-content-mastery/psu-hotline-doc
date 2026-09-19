import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import CentralOverviewView from '@/views/central/CentralOverviewView.vue'

const summary = {
  generated_at: '2026-09-19T05:00:00Z',
  totals: {
    applications: 3,
    waiting_review: 1,
    waiting_for_applicant_revision: 1,
    approved: 1,
  },
  by_property_type: [{ code: 'TYPE_1', name: 'Type 1', count: 3 }],
  by_local_authority: [{
    id: 1,
    code: 'PATONG',
    name: 'Patong Municipality',
    count: 3,
    totals: {
      applications: 3,
      waiting_review: 1,
      waiting_for_applicant_revision: 1,
      approved: 1,
    },
    by_property_type: [{ code: 'TYPE_1', name: 'Type 1', count: 3 }],
    by_current_stage: [{ stage: 'LOCAL_OFFICER_REVIEW', count: 3 }],
  }],
  authority_zeroes_included: true,
  by_current_stage: [{ stage: 'LOCAL_OFFICER_REVIEW', count: 1 }],
}

describe('central overview', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('orders aggregate sections and announces a completed refresh', async () => {
    i18n.global.locale.value = 'en'
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue(summary),
      }),
    )
    const wrapper = mount(CentralOverviewView, { attachTo: document.body, global: { plugins: [i18n] } })
    await flushPromises()

    expect(wrapper.findAll('caption').map((caption) => caption.text())).toEqual([
      'Applications by property type',
      'Applications by local authority',
      'Applications by current stage',
    ])
    expect(wrapper.get('#authority-heat-title').text()).toContain('19 local authorities')
    expect(wrapper.text()).toContain('Patong Municipality')

    await wrapper.get('button.button-secondary').trigger('click')
    await flushPromises()
    expect(wrapper.get('[aria-live="polite"][aria-atomic="true"]').text()).toContain('Summary refreshed')

    await wrapper.get('#authority-tile-1').trigger('click')
    await flushPromises()
    expect(wrapper.get('#authority-detail-heading').text()).toBe('Patong Municipality')
    expect(document.activeElement).toBe(wrapper.get('#authority-detail-heading').element)
    expect(wrapper.get('#authority-detail').text()).toContain('By property type')
    expect(wrapper.get('#authority-detail').text()).toContain('By current stage')
    wrapper.unmount()
  })
})
