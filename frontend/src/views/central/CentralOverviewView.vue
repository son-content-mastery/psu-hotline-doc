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
const showAllAuthorities = ref(false)
const authorityPreviewLimit = 5
const dialogElement = ref<HTMLElement | null>(null)

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
const visibleAuthorities = computed(() =>
  showAllAuthorities.value ? sortedAuthorities.value : sortedAuthorities.value.slice(0, authorityPreviewLimit),
)
const remainingAuthorityCount = computed(() => Math.max(0, sortedAuthorities.value.length - authorityPreviewLimit))
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
  if (level === 1) return 'border-sky-200 bg-sky-50 text-slate-900'
  if (level === 2) return 'border-sky-300 bg-sky-100 text-slate-950'
  if (level === 3) return 'border-teal-400 bg-teal-100 text-slate-950'
  return 'border-teal-600 bg-teal-700 text-white'
}

function counterAccentClass(key: string): string {
  const classes: Record<string, string> = {
    applications: 'bg-brand-700',
    waiting_review: 'bg-sky-600',
    waiting_revision: 'bg-amber-500',
    approved: 'bg-emerald-600',
  }
  return classes[key] ?? 'bg-slate-500'
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
    value.authority_count === value.by_local_authority.length &&
    value.expected_authority_count === 19 &&
    value.authority_count === value.expected_authority_count &&
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
  document.getElementById('authority-dialog-heading')?.focus()
}

async function closeAuthorityDetails(): Promise<void> {
  const previousAuthorityId = selectedAuthorityId.value
  selectedAuthorityId.value = null
  await nextTick()
  if (previousAuthorityId !== null) {
    document.getElementById(`authority-tile-${previousAuthorityId}`)?.focus()
  }
}

function handleDialogKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    void closeAuthorityDetails()
    return
  }
  if (event.key !== 'Tab' || !dialogElement.value) return
  const focusable = Array.from(
    dialogElement.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute('hidden'))
  if (!focusable.length) return
  const first = focusable.at(0)
  const last = focusable.at(-1)
  if (!first || !last) return
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
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

      <section class="mt-7 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm" :aria-label="t('central.measuresLabel')">
        <div class="grid divide-y divide-slate-200 sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
          <div
            v-for="counter in counters"
            :key="counter.key"
            class="min-h-36 px-5 py-5 sm:px-6"
            :data-testid="`central-counter-${counter.key}`"
          >
            <div class="flex items-center gap-2 text-sm font-bold text-slate-600">
              <span :class="['h-2.5 w-2.5 rounded-full', counterAccentClass(counter.key)]" aria-hidden="true"></span>
              <h2>{{ counter.label }}</h2>
            </div>
            <p class="mt-4 text-4xl font-black tracking-tight text-slate-950">{{ formatNumber(counter.value, locale) }}</p>
          </div>
        </div>
      </section>

      <InlineAlert v-if="isEmpty" tone="info" class="mt-7 max-w-3xl">{{ t('central.empty') }}</InlineAlert>

      <section class="mt-9 rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-sm sm:p-7" aria-labelledby="authority-heat-title">
        <div class="max-w-3xl">
          <p class="text-sm font-black uppercase tracking-wide text-brand-700">{{ t('central.heatEyebrow') }}</p>
          <h2 id="authority-heat-title" class="mt-2 text-2xl font-black text-slate-950 sm:text-3xl">
            {{ t('central.heatTitle') }}
          </h2>
          <p class="mt-3 text-slate-700">{{ t('central.heatIntro') }}</p>
          <p class="mt-2 text-sm font-semibold text-slate-600">{{ t('central.heatSelectPrompt') }}</p>
        </div>
        <div class="mt-6 flex flex-wrap items-center gap-3 text-sm font-semibold text-slate-700" :aria-label="t('central.heatLegend')">
          <span>{{ t('central.heatLow') }}</span>
          <span class="h-5 w-7 rounded border border-sky-200 bg-sky-50" aria-hidden="true"></span>
          <span class="h-5 w-7 rounded border border-sky-300 bg-sky-100" aria-hidden="true"></span>
          <span class="h-5 w-7 rounded border border-teal-400 bg-teal-100" aria-hidden="true"></span>
          <span class="h-5 w-7 rounded border border-teal-600 bg-teal-700" aria-hidden="true"></span>
          <span>{{ t('central.heatHigh') }}</span>
          <span class="ml-2 rounded border border-dashed border-slate-300 bg-white px-2 py-1 text-slate-900">0</span>
        </div>
        <ol class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5" role="list">
          <li v-for="authority in summary.by_local_authority" :key="authority.id">
            <button
              :id="`authority-tile-${authority.id}`"
              type="button"
              :class="[
                'relative min-h-36 w-full rounded-2xl border p-4 pr-10 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-sky-700',
                heatClass(authority.count),
                selectedAuthorityId === authority.id ? 'ring-2 ring-sky-700 ring-offset-2' : '',
              ]"
              aria-controls="authority-detail-dialog"
              aria-haspopup="dialog"
              :aria-label="t('central.heatAction', { name: authority.name, count: authority.count })"
              @click="selectAuthority(authority.id)"
            >
              <span class="absolute right-3 top-3 inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/70 text-current" aria-hidden="true">
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m7 4 6 6-6 6" />
                </svg>
              </span>
              <span class="block text-3xl font-black">{{ formatNumber(authority.count, locale) }}</span>
              <span class="mt-3 block font-bold leading-snug">{{ authority.name }}</span>
              <span class="mt-2 block text-sm font-semibold opacity-80">{{ t('central.heatApplications', { count: authority.count }) }}</span>
            </button>
          </li>
        </ol>
        <p class="mt-5 text-sm text-slate-600">{{ t('central.heatBoundaryNote') }}</p>
      </section>

      <Teleport to="body">
        <div
          v-if="selectedAuthority"
          class="fixed inset-0 z-50 flex items-end bg-slate-950/35 p-3 backdrop-blur-[1px] sm:items-center sm:justify-center sm:p-6"
          @click.self="closeAuthorityDetails"
        >
          <section
            id="authority-detail-dialog"
            ref="dialogElement"
            class="max-h-[calc(100dvh-1.5rem)] w-full max-w-4xl overflow-y-auto rounded-3xl bg-white p-5 shadow-2xl sm:max-h-[calc(100dvh-3rem)] sm:p-7"
            role="dialog"
            aria-modal="true"
            aria-labelledby="authority-dialog-heading"
            @keydown="handleDialogKeydown"
          >
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="max-w-3xl">
            <p class="text-sm font-black uppercase tracking-wide text-sky-800">{{ t('central.detailEyebrow') }}</p>
                <h2 id="authority-dialog-heading" tabindex="-1" class="mt-2 text-2xl font-black text-slate-950 sm:text-3xl">
                  {{ selectedAuthority.name }}
                </h2>
                <p class="mt-2 text-slate-700">{{ t('central.detailIntro') }}</p>
              </div>
              <button id="close-authority-dialog" type="button" class="button-secondary" @click="closeAuthorityDetails">
                <svg class="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="m5 5 10 10M15 5 5 15" />
                </svg>
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
        </div>
      </Teleport>

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
          <div class="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 class="text-2xl font-black">{{ t('central.authorityCaption') }}</h2>
              <p class="mt-1 text-sm text-slate-600">
                {{ t('central.authorityPreview', { shown: visibleAuthorities.length, total: sortedAuthorities.length }) }}
              </p>
            </div>
            <button
              v-if="remainingAuthorityCount"
              id="authority-list-toggle"
              type="button"
              class="button-secondary"
              :aria-expanded="showAllAuthorities"
              aria-controls="authority-table"
              @click="showAllAuthorities = !showAllAuthorities"
            >
              <span>{{ t(showAllAuthorities ? 'central.showFewerAuthorities' : 'central.showMoreAuthorities', { count: remainingAuthorityCount }) }}</span>
              <svg
                :class="['h-5 w-5 transition-transform', showAllAuthorities ? 'rotate-180' : '']"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <path d="m5 7 5 5 5-5" />
              </svg>
            </button>
          </div>
          <table id="authority-table" class="mt-5 w-full border-collapse text-left">
            <caption class="sr-only">{{ t('central.authorityCaption') }}</caption>
            <thead>
              <tr class="border-b-2 border-slate-300">
                <th scope="col" class="py-3 pr-3">{{ t('central.category') }}</th>
                <th scope="col" class="py-3 text-right">{{ t('central.count') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in visibleAuthorities" :key="item.id" class="border-b border-slate-200">
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
