import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RequirementList from '@/components/RequirementList.vue'
import { i18n } from '@/i18n'

describe('external document guidance', () => {
  it('labels processing time separately from instructions', () => {
    i18n.global.locale.value = 'en'
    const wrapper = mount(RequirementList, {
      props: {
        groups: [
          { category: 'OPERATOR_PREPARED', items: [] },
          {
            category: 'EXTERNAL_AGENCY',
            items: [
              {
                requirement_id: 1,
                required: true,
                step_code: 'PREMISES',
                document_type: {
                  id: 2,
                  code: 'BUILDING_PERMIT_O1',
                  name: 'Building permit',
                  category: 'EXTERNAL_AGENCY',
                },
                guidance: {
                  approximate_processing_days: 15,
                  instructions: 'Confirm the actual process with the responsible authority.',
                  required_supporting_items: ['Building plans'],
                },
              },
            ],
          },
        ],
      },
      global: { plugins: [i18n] },
    })

    expect(wrapper.text()).toContain('Processing time')
    expect(wrapper.text()).toContain('Approximate processing time: 15 days')
    expect(wrapper.text().match(/Instructions/g)).toHaveLength(1)
  })
})
