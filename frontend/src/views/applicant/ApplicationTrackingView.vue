<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api, ApiError } from '@/services/api'
import type { Application, HistoryEvent, HistoryResponse, License, RequirementItem, RequirementsResponse } from '@/types/api'
import { applicationStatusKey, stageKey } from '@/utils/domain'
import { formatDate, fullDaysSince } from '@/utils/format'

const route = useRoute()
const { locale, t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const application = ref<Application | null>(null)
const history = ref<HistoryResponse | null>(null)
const requirements = ref<RequirementsResponse | null>(null)
const license = ref<License | null>(null)
const initialLoading = ref(true)
const refreshing = ref(false)
const error = ref('')
const stale = ref(false)
const retrievedAt = ref<Date | null>(null)

const revisionItems = computed<RequirementItem[]>(() =>
  requirements.value?.groups
    .flatMap((group) => group.items)
    .filter((item) => item.status === 'REVISION_REQUIRED') ?? [],
)
const status = computed(() => application.value?.status)
const isTerminal = computed(() => ['APPROVED', 'REJECTED'].includes(status.value ?? ''))
const waitingDays = computed(() => fullDaysSince(application.value?.waiting_since ?? history.value?.waiting_since))
const isNotificationApplication = computed(
  () => application.value?.classification.property_type?.issues_license === false,
)

const actionKind = computed(() => {
  if (status.value === 'DRAFT') return 'documents'
  if (status.value === 'READY_TO_SUBMIT') return 'review'
  if (status.value === 'REVISION_REQUIRED') return 'revision'
  if (status.value === 'APPROVED') return 'license'
  if (status.value === 'REJECTED') return 'rejected'
  return 'none'
})

function eventFor(statuses: string[]): HistoryEvent | undefined {
  return history.value?.events.find((event) => statuses.includes(event.to_status))
}

const timeline = computed(() => {
  const submittedEvent = eventFor(['SUBMITTED'])
  const reviewEvent = eventFor(['UNDER_REVIEW', 'REVISION_REQUIRED', 'RESUBMITTED'])
  const decisionEvent = eventFor(['APPROVED', 'REJECTED'])
  const currentStatus = status.value
  return [
    {
      key: 'submitted',
      label: t('tracking.timeline.submitted'),
      complete: Boolean(submittedEvent),
      current: ['SUBMITTED'].includes(currentStatus ?? ''),
      date: submittedEvent?.occurred_at,
    },
    {
      key: 'review',
      label: t('tracking.timeline.review'),
      complete: Boolean(reviewEvent) || Boolean(decisionEvent),
      current: ['UNDER_REVIEW', 'REVISION_REQUIRED', 'RESUBMITTED'].includes(currentStatus ?? ''),
      date: reviewEvent?.occurred_at,
    },
    {
      key: 'decision',
      label:
        currentStatus && ['APPROVED', 'REJECTED'].includes(currentStatus)
          ? t(applicationStatusKey(currentStatus))
          : t('tracking.timeline.decision'),
      complete: Boolean(decisionEvent),
      current: ['APPROVED', 'REJECTED'].includes(currentStatus ?? ''),
      date: decisionEvent?.occurred_at,
    },
  ]
})

async function load(silent = false): Promise<void> {
  if (silent) refreshing.value = true
  else initialLoading.value = true
  error.value = ''
  try {
    const [applicationResponse, historyResponse] = await Promise.all([
      api.get<Application>(`/api/v1/applications/${applicationId.value}/`),
      api.get<HistoryResponse>(`/api/v1/applications/${applicationId.value}/history/`),
    ])
    application.value = applicationResponse
    history.value = historyResponse

    if (applicationResponse.status === 'REVISION_REQUIRED') {
      requirements.value = await api.get<RequirementsResponse>(
        `/api/v1/applications/${applicationId.value}/requirements/`,
      )
    } else {
      requirements.value = null
    }

    if (applicationResponse.status === 'APPROVED') {
      try {
        license.value = await api.get<License>(`/api/v1/applications/${applicationId.value}/license/`)
      } catch {
        license.value = null
      }
    } else {
      license.value = null
    }
    stale.value = false
    retrievedAt.value = new Date()
  } catch (caught) {
    if (application.value && silent) {
      stale.value = true
    } else {
      error.value =
        caught instanceof ApiError && [403, 404].includes(caught.status)
          ? t('common.neutralNotFound')
          : t('tracking.loadError')
    }
  } finally {
    initialLoading.value = false
    refreshing.value = false
  }
}

watch(locale, () => load(true))
onMounted(() => load())
</script>

<template>
  <div class="page-narrow">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 data-page-heading tabindex="-1" class="page-title">{{ t('tracking.title') }}</h1>
        <p v-if="application" class="mt-3 select-all break-all text-xl font-extrabold">
          {{
            application.reference_number
              ? t('tracking.reference', { reference: application.reference_number })
              : t('tracking.referencePending')
          }}
        </p>
        <p v-if="application" class="mt-1 text-slate-700">{{ application.property.name }}</p>
      </div>
      <button v-if="application" type="button" class="button-secondary" :disabled="refreshing" @click="load(true)">
        {{ t(refreshing ? 'common.loading' : 'common.actions.refresh') }}
      </button>
    </div>

    <p v-if="initialLoading" class="mt-7" aria-live="polite">{{ t('tracking.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7">
      {{ error }}
      <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else-if="application && history">
      <InlineAlert v-if="stale" tone="warning" class="mt-6">
        {{ t('tracking.stale', { date: formatDate(retrievedAt?.toISOString(), locale) }) }}
      </InlineAlert>

      <section class="mt-7 rounded-3xl border-2 border-brand-700 bg-brand-50 p-6" aria-labelledby="current-status-heading" aria-live="polite">
        <h2 id="current-status-heading" class="text-lg font-bold text-brand-900">{{ t('tracking.currentStatus') }}</h2>
        <p class="mt-2 text-2xl font-black sm:text-3xl">{{ t(applicationStatusKey(application.status)) }}</p>
        <div class="mt-4"><StatusBadge :status="application.status" /></div>
        <dl class="definition-grid mt-5">
          <dt>{{ t('tracking.responsibleStage') }}</dt>
          <dd>{{ t(stageKey(application.current_stage)) }}</dd>
          <dt v-if="isTerminal">{{ t('tracking.currentStatus') }}</dt>
          <dd v-if="isTerminal">
            {{ t('tracking.completedAt', { date: formatDate(history.events.at(-1)?.occurred_at, locale) }) }}
          </dd>
          <dt v-else-if="waitingDays !== null">{{ t('officer.waiting') }}</dt>
          <dd v-if="!isTerminal && waitingDays !== null">{{ t('tracking.waitingDays', waitingDays) }}</dd>
        </dl>
      </section>

      <section class="card mt-6" aria-labelledby="next-action-heading">
        <h2 id="next-action-heading" class="text-2xl font-black">{{ t('tracking.actionTitle') }}</h2>

        <template v-if="actionKind === 'revision'">
          <p class="mt-4 text-xl font-extrabold">{{ t('tracking.revisionCount', revisionItems.length) }}</p>
          <ul class="mt-4 space-y-3" role="list">
            <li v-for="item in revisionItems" :key="item.document_type.id" class="rounded-xl bg-amber-50 p-4">
              <p class="font-bold">{{ item.document_type.name }}</p>
              <p v-if="item.latest_review_reason" class="mt-1">{{ t('tracking.reason', { reason: item.latest_review_reason }) }}</p>
            </li>
          </ul>
          <RouterLink class="button-primary mt-5" :to="{ name: 'application-documents', params: { id: applicationId } }">
            {{ t('tracking.correctDocuments') }}
          </RouterLink>
        </template>

        <template v-else-if="actionKind === 'documents'">
          <RouterLink class="button-primary mt-5" :to="{ name: 'application-documents', params: { id: applicationId } }">
            {{ t('tracking.continuePreparing') }}
          </RouterLink>
        </template>

        <template v-else-if="actionKind === 'review'">
          <RouterLink class="button-primary mt-5" :to="{ name: 'application-review', params: { id: applicationId } }">
            {{ t('tracking.reviewAndSubmit') }}
          </RouterLink>
        </template>

        <template v-else-if="actionKind === 'license'">
          <RouterLink v-if="license" class="button-primary mt-5" :to="{ name: 'application-license', params: { id: applicationId } }">
            {{ t(isNotificationApplication ? 'tracking.openAcknowledgement' : 'tracking.openLicense') }}
          </RouterLink>
          <p v-else class="mt-4">
            {{ t(isNotificationApplication ? 'tracking.acknowledgementPending' : 'tracking.licensePending') }}
          </p>
        </template>

        <template v-else-if="actionKind === 'rejected'">
          <p class="mt-4 font-bold">{{ t('tracking.rejectedGuidance') }}</p>
          <p v-if="history.events.at(-1)?.reason" class="mt-3 rounded-xl bg-slate-100 p-4">
            {{ t('tracking.reason', { reason: history.events.at(-1)?.reason }) }}
          </p>
        </template>

        <template v-else>
          <p class="mt-4 text-xl font-extrabold">{{ t('tracking.noAction') }}</p>
          <p class="mt-2 text-slate-700">{{ t('tracking.noActionHelp') }}</p>
        </template>
      </section>

      <section class="mt-8" aria-labelledby="timeline-heading">
        <h2 id="timeline-heading" class="text-2xl font-black">{{ t('tracking.timelineTitle') }}</h2>
        <ol class="mt-5 space-y-4" role="list">
          <li
            v-for="item in timeline"
            :key="item.key"
            class="relative rounded-2xl border-2 bg-white p-5 pl-14"
            :class="item.current ? 'border-brand-700' : 'border-slate-300'"
            :aria-current="item.current ? 'step' : undefined"
          >
            <span class="absolute left-5 top-5 text-xl font-black" aria-hidden="true">
              {{ item.complete ? '✓' : item.current ? '●' : '○' }}
            </span>
            <p class="font-extrabold">{{ item.label }}</p>
            <p v-if="item.current" class="text-brand-800">{{ t('tracking.timeline.current') }}</p>
            <p class="text-slate-600">
              {{ item.date ? formatDate(item.date, locale) : t('tracking.timeline.notStarted') }}
            </p>
          </li>
        </ol>
      </section>

      <section class="mt-8" aria-labelledby="history-heading">
        <h2 id="history-heading" class="text-2xl font-black">{{ t('tracking.historyTitle') }}</h2>
        <InlineAlert v-if="history.events.length === 0" tone="warning" class="mt-4">
          {{ t('tracking.historyEmpty') }}
        </InlineAlert>
        <ol v-else class="mt-5 space-y-4" role="list">
          <li v-for="event in history.events" :key="event.id" class="card">
            <p class="font-extrabold">
              {{ t('tracking.event', { status: t(applicationStatusKey(event.to_status)) }) }}
            </p>
            <time class="mt-1 block text-slate-600" :datetime="event.occurred_at">
              {{ formatDate(event.occurred_at, locale) }}
            </time>
            <p v-if="event.reason" class="mt-3 rounded-xl bg-slate-100 p-3">
              {{ t('tracking.reason', { reason: event.reason }) }}
            </p>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>
