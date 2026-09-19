import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import CentralOverviewView from '@/views/central/CentralOverviewView.vue'

function authority(id: number, name: string, count: number) {
  return {
    id,
    code: `AUTH-${id}`,
    name,
    count,
    totals: {
      applications: count,
      waiting_review: 1,
      waiting_for_applicant_revision: 1,
      approved: 1,
    },
    by_property_type: [{ code: 'TYPE_1', name: 'Type 1', count }],
    by_current_stage: [{ stage: 'LOCAL_OFFICER_REVIEW', count }],
  }
}

const summary = {
  generated_at: '2026-09-19T05:00:00Z',
  totals: {
    applications: 3,
    waiting_review: 1,
    waiting_for_applicant_revision: 1,
    approved: 1,
  },
  by_property_type: [{ code: 'TYPE_1', name: 'Type 1', count: 3 }],
  by_local_authority: [
    authority(1, 'Patong Municipality', 3),
    authority(2, 'Chalong Municipality', 2),
    authority(3, 'Kathu Municipality', 2),
    authority(4, 'Karon Municipality', 1),
    authority(5, 'Rawai Municipality', 1),
    authority(6, 'Wichit Municipality', 1),
  ],
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
    expect(wrapper.findAll('#authority-table tbody tr')).toHaveLength(5)

    await wrapper.get('#authority-list-toggle').trigger('click')
    expect(wrapper.findAll('#authority-table tbody tr')).toHaveLength(6)

    await wrapper.get('button.button-secondary').trigger('click')
    await flushPromises()
    expect(wrapper.get('[aria-live="polite"][aria-atomic="true"]').text()).toContain('Summary refreshed')

    await wrapper.get('#authority-tile-1').trigger('click')
    await flushPromises()
    const dialogHeading = document.getElementById('authority-dialog-heading')
    const dialog = document.getElementById('authority-detail-dialog')
    expect(dialogHeading?.textContent).toBe('Patong Municipality')
    expect(document.activeElement).toBe(dialogHeading)
    expect(dialog?.textContent).toContain('By property type')
    expect(dialog?.textContent).toContain('By current stage')

    ;(document.getElementById('close-authority-dialog') as HTMLButtonElement).click()
    await flushPromises()
    expect(document.getElementById('authority-detail-dialog')).toBeNull()
    expect(document.activeElement).toBe(wrapper.get('#authority-tile-1').element)

    await wrapper.get('#authority-tile-1').trigger('click')
    await flushPromises()
    document.getElementById('authority-dialog-heading')?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    )
    await flushPromises()
    expect(document.getElementById('authority-detail-dialog')).toBeNull()
    wrapper.unmount()
  })
})
