<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { CentralSummary } from '@/types/api'
import { stageKey } from '@/utils/domain'
import { formatDate, formatNumber } from '@/utils/format'

const { locale, t } = useI18n()
const summary = ref<CentralSummary | null>(null)
const initialLoading = ref(true)
const refreshing = ref(false)
const error = ref(false)
const stale = ref(false)
const incomplete = ref(false)
const refreshAnnouncement = ref('')
const selectedAuthorityId = ref<number | null>(null)

const counters = computed(() => {
  if (!summary.value) return []
  return [
    { key: 'applications', label: t('central.totals.applications'), value: summary.value.totals.applications },
    { key: 'waiting_review', label: t('central.totals.waitingReview'), value: summary.value.totals.waiting_review },
    {
      key: 'waiting_revision',
      label: t('central.totals.waitingRevision'),
      value: summary.value.totals.waiting_for_applicant_revision,
    },
    { key: 'approved', label: t('central.totals.approved'), value: summary.value.totals.approved },
  ]
})
const sortedAuthorities = computed(() =>
  [...(summary.value?.by_local_authority ?? [])].sort(
    (a, b) => b.count - a.count || a.name.localeCompare(b.name, locale.value),
  ),
)
const isEmpty = computed(() => summary.value?.totals.applications === 0)
const maxAuthorityCount = computed(() =>
  Math.max(0, ...(summary.value?.by_local_authority.map((item) => item.count) ?? [0])),
)
const selectedAuthority = computed(
  () => summary.value?.by_local_authority.find((item) => item.id === selectedAuthorityId.value) ?? null,
)

function heatClass(count: number): string {
  if (count === 0 || maxAuthorityCount.value === 0) return 'border-dashed border-slate-400 bg-white text-slate-800'
  const level = Math.max(1, Math.ceil((count / maxAuthorityCount.value) * 4))
  if (level === 1) return 'border-brand-100 bg-brand-50 text-brand-900'
  if (level === 2) return 'border-brand-600 bg-brand-100 text-brand-900'
  if (level === 3) return 'border-brand-700 bg-brand-600 text-white'
  return 'border-brand-900 bg-brand-800 text-white'
}

function counterClass(key: string): string {
  const classes: Record<string, string> = {
    applications: 'border-l-brand-800',
    waiting_review: 'border-l-sky-700',
    waiting_revision: 'border-l-amber-700',
    approved: 'border-l-emerald-700',
  }
  return classes[key] ?? 'border-l-slate-500'
}

function barWidth(count: number, values: Array<{ count: number }>): string {
  const maximum = Math.max(0, ...values.map((item) => item.count))
  return maximum ? `${Math.max(4, Math.round((count / maximum) * 100))}%` : '0%'
}

function isCompleteResponse(value: CentralSummary): boolean {
  return (
    Boolean(value.generated_at) &&
    ['applications', 'waiting_review', 'waiting_for_applicant_revision', 'approved'].every(
      (key) => typeof value.totals?.[key as keyof CentralSummary['totals']] === 'number',
    ) &&
    Array.isArray(value.by_property_type) &&
    Array.isArray(value.by_local_authority) &&
    value.by_local_authority.every(
      (item) =>
        typeof item.totals?.applications === 'number' &&
        Array.isArray(item.by_property_type) &&
        Array.isArray(item.by_current_stage),
    ) &&
    value.authority_zeroes_included === true &&
    Array.isArray(value.by_current_stage)
  )
}

async function load(isRefresh = false): Promise<void> {
  if (isRefresh) {
    refreshing.value = true
    refreshAnnouncement.value = t('central.refreshing')
  }
  else initialLoading.value = true
  error.value = false
  try {
    const response = await api.get<CentralSummary>('/api/v1/central/summary/')
    incomplete.value = !isCompleteResponse(response)
    if (!incomplete.value) {
      summary.value = response
      if (isRefresh) {
        refreshAnnouncement.value = t('central.refreshComplete', {
          date: formatDate(response.generated_at, locale.value),
        })
      }
    }
    stale.value = false
  } catch {
    if (summary.value) stale.value = true
    else error.value = true
    if (isRefresh) refreshAnnouncement.value = t('central.refreshFailed')
  } finally {
    initialLoading.value = false
    refreshing.value = false
  }
}

function propertyLabel(item: CentralSummary['by_property_type'][number]): string {
  if (item.name) return item.name
  if (['UNCONFIRMED', 'REQUIRES_LICENSE_REVIEW'].includes(item.code)) return t('central.classificationPending')
  return t('central.unknownCategory')
}

async function selectAuthority(authorityId: number): Promise<void> {
  selectedAuthorityId.value = authorityId
  await nextTick()
  document.getElementById('authority-detail-heading')?.focus()
}

async function closeAuthorityDetails(): Promise<void> {
  const previousAuthorityId = selectedAuthorityId.value
  selectedAuthorityId.value = null
  await nextTick()
  if (previousAuthorityId !== null) {
    document.getElementById(`authority-tile-${previousAuthorityId}`)?.focus()
  }
}

watch(locale, () => load(true))
onMounted(() => load())
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end justify-between gap-5">
      <div class="max-w-3xl">
        <h1 data-page-heading tabindex="-1" class="page-title">{{ t('central.title') }}</h1>
        <p class="page-intro">{{ t('central.intro') }}</p>
      </div>
      <button v-if="summary" type="button" class="button-secondary" :disabled="refreshing" @click="load(true)">
        {{ t(refreshing ? 'central.refreshing' : 'central.refresh') }}
      </button>
    </div>

    <p v-if="initialLoading" class="mt-7" aria-live="polite">{{ t('central.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7 max-w-3xl">
      {{ t('central.error') }}
      <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
    </InlineAlert>
    <InlineAlert v-else-if="incomplete" tone="error" class="mt-7 max-w-3xl">
      {{ t('central.incomplete') }}
      <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else-if="summary">
      <p class="mt-6 font-semibold">{{ t('central.asOf', { date: formatDate(summary.generated_at, locale) }) }}</p>
      <p class="sr-only" aria-live="polite" aria-atomic="true">{{ refreshAnnouncement }}</p>
      <InlineAlert v-if="stale" tone="warning" class="mt-5 max-w-3xl">
        {{ t('central.stale', { date: formatDate(summary.generated_at, locale) }) }}
      </InlineAlert>

      <section class="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" :aria-label="t('central.measuresLabel')">
        <div v-for="counter in counters" :key="counter.key" :class="['card border-l-8', counterClass(counter.key)]">
          <p class="text-4xl font-black text-brand-800">{{ formatNumber(counter.value, locale) }}</p>
          <h2 class="mt-2 text-lg font-bold">{{ counter.label }}</h2>
        </div>
      </section>

      <InlineAlert v-if="isEmpty" tone="info" class="mt-7 max-w-3xl">{{ t('central.empty') }}</InlineAlert>

      <section class="mt-9 rounded-3xl bg-slate-900 p-5 text-white sm:p-7" aria-labelledby="authority-heat-title">
        <div class="max-w-3xl">
          <p class="text-sm font-bold uppercase tracking-wide text-brand-100">{{ t('central.heatEyebrow') }}</p>
          <h2 id="authority-heat-title" class="mt-2 text-2xl font-black text-white sm:text-3xl">
            {{ t('central.heatTitle') }}
          </h2>
          <p class="mt-3 text-slate-200">{{ t('central.heatIntro') }}</p>
        </div>
        <div class="mt-6 flex flex-wrap items-center gap-3 text-sm font-semibold" :aria-label="t('central.heatLegend')">
          <span>{{ t('central.heatLow') }}</span>
          <span class="h-6 w-8 rounded border border-brand-100 bg-brand-50" aria-hidden="true"></span>
          <span class="h-6 w-8 rounded border border-brand-600 bg-brand-100" aria-hidden="true"></span>
          <span class="h-6 w-8 rounded border border-brand-700 bg-brand-600" aria-hidden="true"></span>
          <span class="h-6 w-8 rounded border border-brand-900 bg-brand-800" aria-hidden="true"></span>
          <span>{{ t('central.heatHigh') }}</span>
          <span class="ml-2 rounded border border-dashed border-slate-300 bg-white px-2 py-1 text-slate-900">0</span>
        </div>
        <ol class="mt-6 grid grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] gap-3" role="list">
          <li v-for="authority in summary.by_local_authority" :key="authority.id">
            <button
              :id="`authority-tile-${authority.id}`"
              type="button"
              :class="[
                'min-h-32 w-full rounded-2xl border-2 p-4 text-left transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-amber-400',
                heatClass(authority.count),
                selectedAuthorityId === authority.id ? 'ring-4 ring-amber-400 ring-offset-2 ring-offset-slate-900' : '',
              ]"
              :aria-expanded="selectedAuthorityId === authority.id"
              aria-controls="authority-detail"
              :aria-label="t('central.heatAction', { name: authority.name, count: authority.count })"
              @click="selectAuthority(authority.id)"
            >
              <span class="block text-3xl font-black">{{ formatNumber(authority.count, locale) }}</span>
              <span class="mt-2 block font-bold leading-snug">{{ authority.name }}</span>
              <span class="mt-2 block text-sm font-semibold">{{ t('central.heatApplications', { count: authority.count }) }}</span>
              <span class="mt-3 inline-flex items-center gap-1 text-sm font-black underline underline-offset-4">
                {{ t('central.viewArea') }}
                <span aria-hidden="true">→</span>
              </span>
            </button>
          </li>
        </ol>
        <p class="mt-5 text-sm text-slate-200">{{ t('central.heatBoundaryNote') }}</p>
      </section>

      <section
        v-if="selectedAuthority"
        id="authority-detail"
        class="mt-6 rounded-3xl border-2 border-sky-700 bg-sky-50 p-5 sm:p-7"
        aria-labelledby="authority-detail-heading"
      >
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="max-w-3xl">
            <p class="text-sm font-black uppercase tracking-wide text-sky-800">{{ t('central.detailEyebrow') }}</p>
            <h2 id="authority-detail-heading" tabindex="-1" class="mt-2 text-2xl font-black text-slate-950 sm:text-3xl">
              {{ selectedAuthority.name }}
            </h2>
            <p class="mt-2 text-slate-700">{{ t('central.detailIntro') }}</p>
          </div>
          <button type="button" class="button-secondary" @click="closeAuthorityDetails">
            {{ t('central.closeDetail') }}
          </button>
        </div>

        <div class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" :aria-label="t('central.detailMeasures')">
          <div class="rounded-2xl border border-slate-300 bg-white p-4">
            <p class="text-3xl font-black text-brand-800">{{ formatNumber(selectedAuthority.totals.applications, locale) }}</p>
            <p class="mt-1 font-bold">{{ t('central.totals.applications') }}</p>
          </div>
          <div class="rounded-2xl border border-slate-300 bg-white p-4">
            <p class="text-3xl font-black text-sky-800">{{ formatNumber(selectedAuthority.totals.waiting_review, locale) }}</p>
            <p class="mt-1 font-bold">{{ t('central.totals.waitingReview') }}</p>
          </div>
          <div class="rounded-2xl border border-slate-300 bg-white p-4">
            <p class="text-3xl font-black text-amber-800">{{ formatNumber(selectedAuthority.totals.waiting_for_applicant_revision, locale) }}</p>
            <p class="mt-1 font-bold">{{ t('central.totals.waitingRevision') }}</p>
          </div>
          <div class="rounded-2xl border border-slate-300 bg-white p-4">
            <p class="text-3xl font-black text-emerald-800">{{ formatNumber(selectedAuthority.totals.approved, locale) }}</p>
            <p class="mt-1 font-bold">{{ t('central.totals.approved') }}</p>
          </div>
        </div>

        <div class="mt-6 grid gap-6 lg:grid-cols-2">
          <section class="rounded-2xl border border-slate-300 bg-white p-5" :aria-labelledby="`authority-types-${selectedAuthority.id}`">
            <h3 :id="`authority-types-${selectedAuthority.id}`" class="text-xl font-black">{{ t('central.detailTypes') }}</h3>
            <ul v-if="selectedAuthority.by_property_type.length" class="mt-3 divide-y divide-slate-200" role="list">
              <li v-for="item in selectedAuthority.by_property_type" :key="item.code" class="flex justify-between gap-4 py-3">
                <span class="font-semibold">{{ propertyLabel(item) }}</span>
                <span class="font-black">{{ formatNumber(item.count, locale) }}</span>
              </li>
            </ul>
            <p v-else class="mt-3 text-slate-600">{{ t('central.detailEmpty') }}</p>
          </section>

          <section class="rounded-2xl border border-slate-300 bg-white p-5" :aria-labelledby="`authority-stages-${selectedAuthority.id}`">
            <h3 :id="`authority-stages-${selectedAuthority.id}`" class="text-xl font-black">{{ t('central.detailStages') }}</h3>
            <ul v-if="selectedAuthority.by_current_stage.length" class="mt-3 divide-y divide-slate-200" role="list">
              <li v-for="item in selectedAuthority.by_current_stage" :key="item.stage" class="flex justify-between gap-4 py-3">
                <span class="font-semibold">{{ t(stageKey(item.stage)) }}</span>
                <span class="font-black">{{ formatNumber(item.count, locale) }}</span>
              </li>
            </ul>
            <p v-else class="mt-3 text-slate-600">{{ t('central.detailEmpty') }}</p>
          </section>
        </div>
      </section>

      <div class="mt-9 grid gap-7 xl:grid-cols-2">
        <section class="rounded-3xl border border-slate-300 bg-white p-5 sm:p-7">
          <table class="w-full border-collapse text-left">
            <caption class="mb-4 text-left text-2xl font-black">{{ t('central.propertyCaption') }}</caption>
            <thead>
              <tr class="border-b-2 border-slate-300">
                <th scope="col" class="py-3 pr-3">{{ t('central.category') }}</th>
                <th scope="col" class="py-3 text-right">{{ t('central.count') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in summary.by_property_type" :key="item.code" class="border-b border-slate-200">
                <th scope="row" class="py-3 pr-3 font-semibold">
                  {{ propertyLabel(item) }}
                  <span class="mt-2 block h-2 rounded-full bg-slate-100" aria-hidden="true">
                    <span class="block h-2 rounded-full bg-brand-600" :style="{ width: barWidth(item.count, summary.by_property_type) }"></span>
                  </span>
                </th>
                <td class="py-3 text-right font-bold">{{ formatNumber(item.count, locale) }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="rounded-3xl border border-slate-300 bg-white p-5 sm:p-7">
          <table class="w-full border-collapse text-left">
            <caption class="mb-4 text-left text-2xl font-black">{{ t('central.authorityCaption') }}</caption>
            <thead>
              <tr class="border-b-2 border-slate-300">
                <th scope="col" class="py-3 pr-3">{{ t('central.category') }}</th>
                <th scope="col" class="py-3 text-right">{{ t('central.count') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in sortedAuthorities" :key="item.id" class="border-b border-slate-200">
                <th scope="row" class="py-3 pr-3 font-semibold">{{ item.name }}</th>
                <td class="py-3 text-right font-bold">{{ formatNumber(item.count, locale) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="mt-4 text-sm text-slate-600">{{ t('central.zeroConvention') }}</p>
        </section>

        <section class="rounded-3xl border border-slate-300 bg-white p-5 sm:p-7 xl:col-span-2">
          <table class="w-full border-collapse text-left">
            <caption class="mb-4 text-left text-2xl font-black">{{ t('central.stageCaption') }}</caption>
            <thead>
              <tr class="border-b-2 border-slate-300">
                <th scope="col" class="py-3 pr-3">{{ t('central.category') }}</th>
                <th scope="col" class="py-3 text-right">{{ t('central.count') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in summary.by_current_stage" :key="item.stage" class="border-b border-slate-200">
                <th scope="row" class="py-3 pr-3 font-semibold">
                  {{ t(stageKey(item.stage)) }}
                  <span class="mt-2 block h-2 rounded-full bg-slate-100" aria-hidden="true">
                    <span class="block h-2 rounded-full bg-sky-700" :style="{ width: barWidth(item.count, summary.by_current_stage) }"></span>
                  </span>
                </th>
                <td class="py-3 text-right font-bold">{{ formatNumber(item.count, locale) }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </template>
  </div>
</template>
