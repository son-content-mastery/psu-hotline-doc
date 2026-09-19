<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { ApplicationListItem, Paginated } from '@/types/api'
import { applicantApplicationDestination } from '@/utils/domain'
import { formatDate } from '@/utils/format'

const { locale, t } = useI18n()
const auth = useAuthStore()
const applications = ref<ApplicationListItem[]>([])
const filter = ref<'action' | 'in_progress' | 'completed' | 'all'>('action')
const loading = ref(true)
const error = ref(false)

function needsAction(application: ApplicationListItem): boolean {
  return application.applicant_action_required || ['DRAFT', 'READY_TO_SUBMIT'].includes(application.status)
}

function inProgress(application: ApplicationListItem): boolean {
  return ['SUBMITTED', 'UNDER_REVIEW', 'RESUBMITTED'].includes(application.status)
}

function completed(application: ApplicationListItem): boolean {
  return ['APPROVED', 'REJECTED'].includes(application.status)
}

const counters = computed(() => [
  { key: 'action', label: t('application.dashboard.needsAction'), value: applications.value.filter(needsAction).length },
  { key: 'in_progress', label: t('application.dashboard.inProgress'), value: applications.value.filter(inProgress).length },
  { key: 'approved', label: t('application.dashboard.approved'), value: applications.value.filter((item) => item.status === 'APPROVED').length },
  { key: 'all', label: t('application.dashboard.total'), value: applications.value.length },
])

const visibleApplications = computed(() =>
  applications.value
    .filter((application) => {
      if (filter.value === 'action') return needsAction(application)
      if (filter.value === 'in_progress') return inProgress(application)
      if (filter.value === 'completed') return completed(application)
      return true
    })
    .sort((a, b) => {
      const actionDifference = Number(needsAction(b)) - Number(needsAction(a))
      if (actionDifference) return actionDifference
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    }),
)

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const response = await api.get<Paginated<ApplicationListItem>>('/api/v1/applications/')
    applications.value = response.results
  } catch {
    applications.value = []
    error.value = true
  } finally {
    loading.value = false
  }
}

function actionRoute(application: ApplicationListItem) {
  return {
    name: applicantApplicationDestination(application.status),
    params: { id: application.id },
  }
}

function actionLabel(application: ApplicationListItem): string {
  return t(
    ['DRAFT', 'READY_TO_SUBMIT'].includes(application.status)
      ? 'application.continueApplication'
      : 'application.trackApplication',
  )
}

watch(locale, load)
onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-5xl">
    <section class="rounded-3xl bg-brand-900 p-5 text-white sm:p-7" aria-labelledby="applicant-dashboard-title">
      <div class="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p class="text-sm font-bold uppercase tracking-wide text-brand-100">{{ t('application.dashboard.eyebrow') }}</p>
          <h1 id="applicant-dashboard-title" data-page-heading tabindex="-1" class="mt-2 text-3xl font-black text-white sm:text-4xl">
            {{ t('application.dashboard.welcome', { name: auth.user?.display_name ?? t('common.roles.applicant') }) }}
          </h1>
          <p class="mt-2 text-brand-100">{{ auth.user?.email }}</p>
        </div>
        <RouterLink class="button-secondary border-white bg-white" :to="{ name: 'classification-step', params: { step: '1' } }">
          {{ t('application.startNew') }}
        </RouterLink>
      </div>
    </section>

    <h2 class="mt-8 text-2xl font-black">{{ t('application.listTitle') }}</h2>
    <p class="page-intro">{{ t('application.listIntro') }}</p>

    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('application.listLoading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7">
      {{ t('application.listError') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else>
      <InlineAlert v-if="applications.length === 0" tone="info" class="mt-7">
        {{ t('application.listEmpty') }}
      </InlineAlert>

      <section v-if="applications.length" class="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4" :aria-label="t('application.dashboard.summaryLabel')">
        <div v-for="counter in counters" :key="counter.key" class="rounded-2xl border border-slate-200 bg-white p-4">
          <p class="text-3xl font-black text-brand-800">{{ counter.value }}</p>
          <p class="mt-1 text-sm font-bold text-slate-700">{{ counter.label }}</p>
        </div>
      </section>

      <div v-if="applications.length" class="mt-7 max-w-md">
        <label for="application-filter" class="field-label">{{ t('application.dashboard.filterLabel') }}</label>
        <select id="application-filter" v-model="filter" class="field-input">
          <option value="action">{{ t('application.dashboard.filterAction') }}</option>
          <option value="in_progress">{{ t('application.dashboard.filterInProgress') }}</option>
          <option value="completed">{{ t('application.dashboard.filterCompleted') }}</option>
          <option value="all">{{ t('application.dashboard.filterAll') }}</option>
        </select>
      </div>

      <InlineAlert v-if="applications.length && visibleApplications.length === 0" tone="info" class="mt-7">
        {{ t('application.dashboard.filterEmpty') }}
      </InlineAlert>

      <ul v-else-if="visibleApplications.length" class="mt-7 grid gap-5 lg:grid-cols-2" role="list">
        <li
          v-for="application in visibleApplications"
          :key="application.id"
          class="card flex flex-col"
          data-testid="application-card"
          :data-application-id="application.id"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="select-all font-extrabold text-brand-800">
                {{ application.reference_number ?? t('application.referencePending') }}
              </p>
              <h2 class="mt-2 text-2xl font-black">{{ application.property_name }}</h2>
            </div>
            <StatusBadge :status="application.status" />
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <span class="rounded-full bg-brand-50 px-3 py-1 text-sm font-bold text-brand-900">
              {{ application.property_type?.name ?? t('central.classificationPending') }}
            </span>
            <span v-if="application.responsible_authority" class="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-800">
              {{ application.responsible_authority.name }}
            </span>
          </div>
          <p v-if="needsAction(application)" class="mt-4 rounded-xl bg-amber-50 p-3 font-bold text-amber-950">
            {{
              t(
                application.status === 'REVISION_REQUIRED'
                  ? 'application.dashboard.nextRevision'
                  : application.status === 'READY_TO_SUBMIT'
                    ? 'application.dashboard.nextSubmit'
                    : 'application.dashboard.nextPrepare',
              )
            }}
          </p>
          <p v-if="needsAction(application)" class="mt-3 text-sm font-semibold text-slate-700">
            {{ t('application.dashboard.documentProgress', {
              current: application.requirements.current_uploads,
              total: application.requirements.required,
            }) }}
          </p>
          <p class="mt-3 text-slate-600">{{ t('application.updated', { date: formatDate(application.updated_at, locale) }) }}</p>
          <RouterLink class="button-primary mt-5 lg:mt-auto lg:pt-3" :to="actionRoute(application)">
            {{ actionLabel(application) }}
          </RouterLink>
          <RouterLink
            v-if="['DRAFT', 'READY_TO_SUBMIT', 'REVISION_REQUIRED'].includes(application.status)"
            class="button-secondary mt-3"
            :to="{ name: 'application-edit', params: { id: application.id } }"
          >
            {{ t('application.edit') }}
          </RouterLink>
        </li>
      </ul>
    </template>
  </div>
</template>
