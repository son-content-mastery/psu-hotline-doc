<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import StatusBadge from '@/components/StatusBadge.vue'
import type { RequirementCategory, RequirementGroup, RequirementItem } from '@/types/api'

const props = withDefaults(
  defineProps<{
    groups: RequirementGroup[]
    showStatus?: boolean
    hideEmptyGroups?: boolean
  }>(),
  { showStatus: false, hideEmptyGroups: false },
)

defineSlots<{
  action(props: { item: RequirementItem }): unknown
}>()

const { t } = useI18n()
const categories: RequirementCategory[] = ['OPERATOR_PREPARED', 'EXTERNAL_AGENCY']

const orderedGroups = computed(() =>
  categories.map((category) => ({
    category,
    items: props.groups.find((group) => group.category === category)?.items ?? [],
  })),
)

function groupTitle(category: RequirementCategory): string {
  return t(category === 'OPERATOR_PREPARED' ? 'documents.groups.operator' : 'documents.groups.external')
}

function contactValue(item: RequirementItem): string | null {
  const guidance = item.guidance
  return guidance?.contact ?? guidance?.contact_phone ?? guidance?.contact_email ?? null
}

function contactHref(item: RequirementItem): string | undefined {
  const value = contactValue(item)
  if (!value) return undefined
  if (/^https?:\/\//i.test(value)) return value
  if (value.includes('@')) return `mailto:${value}`
  const phone = value.replace(/[^+\d]/g, '')
  return phone ? `tel:${phone}` : undefined
}
</script>

<template>
  <section
    v-for="group in orderedGroups"
    v-show="!hideEmptyGroups || group.items.length > 0"
    :key="group.category"
    class="mt-8"
    :aria-labelledby="`requirements-${group.category}`"
  >
    <h2 :id="`requirements-${group.category}`" class="text-2xl font-black">
      {{ groupTitle(group.category) }}
    </h2>

    <p v-if="group.items.length === 0" class="mt-4 rounded-2xl border border-dashed border-slate-400 p-5">
      {{ t('documents.groups.empty') }}
    </p>

    <ul v-else class="mt-4 space-y-4" role="list">
      <li v-for="item in group.items" :key="item.requirement_id ?? item.document_type.id" class="card">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 class="text-xl font-extrabold">{{ item.document_type.name }}</h3>
            <p class="mt-1 font-semibold text-slate-600">
              {{ t(item.required ? 'documents.requiredItem' : 'documents.optionalItem') }}
            </p>
          </div>
          <StatusBadge v-if="showStatus" :status="item.status" kind="document" />
        </div>

        <p v-if="item.description || item.document_type.description" class="mt-3 text-slate-700">
          {{ item.description ?? item.document_type.description }}
        </p>
        <p v-if="item.instructions" class="mt-3 text-slate-700">{{ item.instructions }}</p>

        <p
          v-if="showStatus && item.latest_review_reason"
          class="mt-4 rounded-xl border border-amber-400 bg-amber-50 p-3 font-semibold text-amber-950"
        >
          {{ t('documents.reason', { reason: item.latest_review_reason }) }}
        </p>

        <details v-if="group.category === 'EXTERNAL_AGENCY'" class="mt-5 rounded-xl bg-slate-50 p-4">
          <summary class="min-h-12 cursor-pointer py-2 font-bold text-brand-800">
            {{ t('documents.guidance.show', { name: item.document_type.name }) }}
          </summary>
          <dl v-if="item.guidance" class="definition-grid mt-3">
            <template v-if="item.guidance.issuing_agency?.name">
              <dt>{{ t('documents.guidance.agency') }}</dt>
              <dd>{{ item.guidance.issuing_agency.name }}</dd>
            </template>
            <template v-if="item.guidance.responsible_local_authority?.name">
              <dt>{{ t('documents.guidance.authority') }}</dt>
              <dd>{{ item.guidance.responsible_local_authority.name }}</dd>
            </template>
            <template v-if="contactValue(item)">
              <dt>{{ t('documents.guidance.contact') }}</dt>
              <dd>
                <a v-if="contactHref(item)" :href="contactHref(item)">{{ contactValue(item) }}</a>
                <span v-else>{{ contactValue(item) }}</span>
              </dd>
            </template>
            <template v-if="item.guidance.required_supporting_items?.length">
              <dt>{{ t('documents.guidance.supporting') }}</dt>
              <dd>
                <ul class="list-disc pl-5">
                  <li v-for="supportingItem in item.guidance.required_supporting_items" :key="supportingItem">
                    {{ supportingItem }}
                  </li>
                </ul>
              </dd>
            </template>
            <template v-if="item.guidance.approximate_processing_days != null">
              <dt>{{ t('documents.guidance.instructions') }}</dt>
              <dd>
                {{
                  t('documents.guidance.processing', {
                    days: item.guidance.approximate_processing_days,
                  })
                }}
              </dd>
            </template>
            <template v-if="item.guidance.instructions">
              <dt>{{ t('documents.guidance.instructions') }}</dt>
              <dd>{{ item.guidance.instructions }}</dd>
            </template>
          </dl>
          <p v-else class="mt-3 text-slate-700">{{ t('documents.guidance.unavailable') }}</p>
        </details>

        <div v-if="$slots.action" class="mt-5 border-t border-slate-200 pt-5">
          <slot name="action" :item="item" />
        </div>
      </li>
    </ul>
  </section>
</template>
