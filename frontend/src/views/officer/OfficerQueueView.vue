<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { OfficerQueueItem, Paginated, PropertyType } from '@/types/api'
import { formatDate, fullDaysSince } from '@/utils/format'

const { locale, t } = useI18n()
const auth = useAuthStore()
const items = ref<OfficerQueueItem[]>([])
const propertyTypes = ref<PropertyType[]>([])
const initialCount = ref(0)
const resubmittedCount = ref(0)
const filter = ref<'actionable' | 'initial' | 'resubmitted' | 'all'>('actionable')
const propertyType = ref('')
const ordering = ref<'submitted_at' | '-submitted_at' | 'property_type'>('submitted_at')
const loading = ref(true)
const error = ref(false)
const nextPage = ref<string | null>(null)
const previousPage = ref<string | null>(null)

async function load(url?: string): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const params = new URLSearchParams({ ordering: ordering.value })
    const statusFilters = {
      actionable: 'SUBMITTED,RESUBMITTED,UNDER_REVIEW',
      initial: 'SUBMITTED',
      resubmitted: 'RESUBMITTED',
      all: '',
    }
    if (statusFilters[filter.value]) params.set('status', statusFilters[filter.value])
    if (propertyType.value) params.set('property_type', propertyType.value)
    const [response, initialResponse, resubmittedResponse] = await Promise.all([
      api.get<Paginated<OfficerQueueItem>>(url ?? `/api/v1/officer/applications/?${params.toString()}`),
      api.get<Paginated<OfficerQueueItem>>('/api/v1/officer/applications/?status=SUBMITTED'),
      api.get<Paginated<OfficerQueueItem>>('/api/v1/officer/applications/?status=RESUBMITTED'),
    ])
    items.value = response.results
    nextPage.value = response.next
    previousPage.value = response.previous
    initialCount.value = initialResponse.count
    resubmittedCount.value = resubmittedResponse.count
  } catch {
    error.value = true
    items.value = []
  } finally {
    loading.value = false
  }
}

async function loadPropertyTypes(): Promise<void> {
  try {
    const response = await api.get<Paginated<PropertyType>>('/api/v1/property-types/')
    propertyTypes.value = response.results
  } catch {
    propertyTypes.value = []
  }
}

function urgencyClass(item: OfficerQueueItem): string {
  const days = fullDaysSince(item.waiting_since) ?? 0
  if (days >= 7) return 'border-red-700 bg-red-50 text-red-900'
  if (days >= 3) return 'border-amber-700 bg-amber-50 text-amber-950'
  return 'border-slate-400 bg-slate-50 text-slate-800'
}

watch([filter, propertyType, ordering], () => load())
watch(locale, () => Promise.all([load(), loadPropertyTypes()]))
onMounted(() => Promise.all([load(), loadPropertyTypes()]))
</script>

<template>
  <div>
    <div class="max-w-3xl">
      <h1 data-page-heading tabindex="-1" class="page-title">{{ t('officer.queueTitle') }}</h1>
      <p v-if="auth.user?.local_authority" class="page-intro">
        {{ t('officer.authority', { name: auth.user.local_authority.name }) }}
      </p>
    </div>

    <InlineAlert v-if="!auth.user?.local_authority" tone="error" class="mt-7 max-w-3xl">
      {{ t('officer.unassigned') }}
    </InlineAlert>

    <template v-else>
      <section class="mt-7 grid gap-4 sm:grid-cols-2" :aria-label="t('officer.countsLabel')">
        <div class="card">
          <p class="text-3xl font-black">{{ initialCount }}</p>
          <p class="mt-1 font-bold">{{ t('officer.initialCount', { count: initialCount }) }}</p>
        </div>
        <div class="card">
          <p class="text-3xl font-black">{{ resubmittedCount }}</p>
          <p class="mt-1 font-bold">{{ t('officer.resubmittedCount', { count: resubmittedCount }) }}</p>
        </div>
      </section>

      <div class="mt-7 grid gap-4 rounded-3xl border border-slate-200 bg-white p-5 md:grid-cols-3">
        <div>
          <label for="queue-filter" class="field-label">{{ t('officer.filterLabel') }}</label>
          <select id="queue-filter" v-model="filter" class="field-input">
            <option value="actionable">{{ t('officer.filterActionable') }}</option>
            <option value="initial">{{ t('officer.filterInitial') }}</option>
            <option value="resubmitted">{{ t('officer.filterResubmitted') }}</option>
            <option value="all">{{ t('officer.filterAll') }}</option>
          </select>
        </div>
        <div>
          <label for="property-type-filter" class="field-label">{{ t('officer.typeFilterLabel') }}</label>
          <select id="property-type-filter" v-model="propertyType" class="field-input">
            <option value="">{{ t('officer.typeFilterAll') }}</option>
            <option v-for="item in propertyTypes" :key="item.code" :value="item.code">{{ item.name }}</option>
            <option value="UNCONFIRMED">{{ t('central.classificationPending') }}</option>
          </select>
        </div>
        <div>
          <label for="queue-ordering" class="field-label">{{ t('officer.sortLabel') }}</label>
          <select id="queue-ordering" v-model="ordering" class="field-input">
            <option value="submitted_at">{{ t('officer.sortOldest') }}</option>
            <option value="-submitted_at">{{ t('officer.sortNewest') }}</option>
            <option value="property_type">{{ t('officer.sortType') }}</option>
          </select>
        </div>
      </div>

      <p v-if="loading" class="mt-7" aria-live="polite">{{ t('officer.queueLoading') }}</p>
      <InlineAlert v-else-if="error" tone="error" class="mt-7 max-w-3xl">
        {{ t('officer.queueError') }}
        <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
      </InlineAlert>
      <InlineAlert v-else-if="items.length === 0" tone="info" class="mt-7 max-w-3xl">
        {{ t('officer.queueEmpty') }}
      </InlineAlert>

      <template v-else>
        <div class="mt-7 hidden overflow-x-auto rounded-2xl border border-slate-300 bg-white md:block">
          <table class="w-full border-collapse text-left text-base">
            <caption class="p-4 text-left text-xl font-black">{{ t('officer.queueCaption') }}</caption>
            <thead class="bg-slate-100">
              <tr>
                <th scope="col" class="p-4">{{ t('officer.reference') }}</th>
                <th scope="col" class="p-4">{{ t('officer.property') }}</th>
                <th scope="col" class="p-4">{{ t('officer.type') }}</th>
                <th scope="col" class="p-4">{{ t('officer.status') }}</th>
                <th scope="col" class="p-4">{{ t('officer.submitted') }}</th>
                <th scope="col" class="p-4"><span class="sr-only">{{ t('common.actions.continue') }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in items"
                :key="item.id"
                class="border-t border-slate-200 align-top"
                data-testid="officer-queue-row"
                :data-application-id="item.id"
              >
                <th scope="row" class="p-4 font-extrabold">{{ item.reference_number }}</th>
                <td class="p-4">{{ item.property_name }}</td>
                <td class="p-4">{{ item.property_type?.name ?? t('central.classificationPending') }}</td>
                <td class="p-4">
                  <StatusBadge :status="item.status" />
                  <p :class="['mt-2 inline-flex rounded-full border px-3 py-1 text-sm font-bold', urgencyClass(item)]">
                    {{ t('tracking.waitingDays', fullDaysSince(item.waiting_since) ?? 0) }}
                  </p>
                  <p class="mt-2 text-sm font-semibold text-slate-700">
                    {{ t('officer.documentsPending', { count: item.documents_pending_review }) }}
                  </p>
                </td>
                <td class="p-4">{{ formatDate(item.resubmitted_at ?? item.submitted_at, locale) }}</td>
                <td class="p-4">
                  <RouterLink class="font-bold" :to="{ name: 'officer-review', params: { id: item.id } }">
                    {{ t('officer.reviewLink', { reference: item.reference_number }) }}
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <ul class="mt-7 space-y-4 md:hidden" role="list">
          <li
            v-for="item in items"
            :key="item.id"
            class="card"
            data-testid="officer-queue-row"
            :data-application-id="item.id"
          >
            <p class="select-all text-lg font-black">{{ item.reference_number }}</p>
            <h2 class="mt-2 text-xl font-black">{{ item.property_name }}</h2>
            <p class="mt-1 text-slate-700">{{ item.property_type?.name ?? t('central.classificationPending') }}</p>
            <div class="mt-3"><StatusBadge :status="item.status" /></div>
            <p :class="['mt-3 inline-flex rounded-full border px-3 py-1 text-sm font-bold', urgencyClass(item)]">
              {{ t('tracking.waitingDays', fullDaysSince(item.waiting_since) ?? 0) }}
            </p>
            <p class="mt-3 font-semibold text-slate-700">
              {{ t('officer.documentsPending', { count: item.documents_pending_review }) }}
            </p>
            <dl class="definition-grid mt-4">
              <dt>{{ t('officer.submitted') }}</dt>
              <dd>{{ formatDate(item.resubmitted_at ?? item.submitted_at, locale) }}</dd>
            </dl>
            <RouterLink class="button-primary mt-5" :to="{ name: 'officer-review', params: { id: item.id } }">
              {{ t('officer.reviewLink', { reference: item.reference_number }) }}
            </RouterLink>
          </li>
        </ul>
        <nav v-if="previousPage || nextPage" class="mt-7 flex items-center justify-between gap-3" :aria-label="t('common.pagination')">
          <button type="button" class="button-secondary" :disabled="!previousPage || loading" @click="previousPage && load(previousPage)">{{ t('common.actions.back') }}</button>
          <button type="button" class="button-secondary" :disabled="!nextPage || loading" @click="nextPage && load(nextPage)">{{ t('common.actions.next') }}</button>
        </nav>
      </template>
    </template>
  </div>
</template>
