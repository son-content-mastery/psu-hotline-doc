<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import RequirementList from '@/components/RequirementList.vue'
import { api } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useClassificationStore } from '@/stores/classification'
import type { RequirementsResponse } from '@/types/api'

const { locale, t } = useI18n()
const auth = useAuthStore()
const classification = useClassificationStore()
const requirements = ref<RequirementsResponse | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref(false)
const stale = ref(false)
let requirementRequest = 0

const propertyType = computed(() => classification.evaluation?.property_type)
const itemCount = computed(() =>
  requirements.value?.groups.reduce((total, group) => total + group.items.length, 0) ?? 0,
)

async function loadRequirements(preserveExisting = false): Promise<void> {
  if (!propertyType.value?.id) {
    loading.value = false
    return
  }
  const request = ++requirementRequest
  const hasExisting = requirements.value !== null
  if (preserveExisting && hasExisting) refreshing.value = true
  else loading.value = true
  if (!hasExisting) loadError.value = false
  try {
    const response = await api.get<RequirementsResponse>(
      `/api/v1/property-types/${propertyType.value.id}/requirements/`,
    )
    if (request !== requirementRequest) return
    requirements.value = response
    loadError.value = false
    stale.value = false
  } catch {
    if (request !== requirementRequest) return
    if (hasExisting) stale.value = true
    else loadError.value = true
  } finally {
    if (request === requirementRequest) {
      loading.value = false
      refreshing.value = false
    }
  }
}

watch(locale, () => loadRequirements(true))
onMounted(loadRequirements)
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('documents.publicTitle') }}</h1>
    <p v-if="propertyType" class="page-intro">
      {{ t('documents.classificationSummary', { name: requirements?.property_type?.name ?? propertyType.name }) }}
      <RouterLink class="ml-2 font-bold" :to="{ name: 'classification-step', params: { step: '1' } }">
        {{ t('classification.result.editAnswers') }}
      </RouterLink>
    </p>

    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('documents.loading') }}</p>

    <template v-else-if="requirements">
      <InlineAlert v-if="stale" tone="warning" live="polite" class="mt-7">
        {{ t('documents.localizedReloadError') }}
        <button type="button" class="ml-2 font-bold underline" @click="loadRequirements(true)">
          {{ t('common.actions.retry') }}
        </button>
      </InlineAlert>
      <InlineAlert tone="warning" class="mt-7">
        {{ requirements.disclaimer || t('documents.demoNotice') }}
      </InlineAlert>
      <p class="mt-6 text-xl font-bold">{{ t('documents.count', { count: itemCount }) }}</p>

      <section v-if="requirements.steps.length" class="mt-7" :aria-label="t('documents.stepsLabel')">
        <ol class="grid gap-3 sm:grid-cols-2" role="list">
          <li v-for="(step, index) in requirements.steps" :key="step.code" class="rounded-2xl border border-slate-300 bg-white p-5">
            <p class="text-sm font-bold text-slate-600">
              {{ t('documents.stepNumber', { current: index + 1, total: requirements.steps.length }) }}
            </p>
            <h2 class="mt-1 text-xl font-black">{{ t(`documents.steps.${step.code.toLowerCase()}.title`) }}</h2>
            <p class="mt-2 text-slate-700">{{ t(`documents.steps.${step.code.toLowerCase()}.description`) }}</p>
            <p class="mt-3 font-bold">{{ t('documents.requiredCount', { count: step.required }) }}</p>
          </li>
        </ol>
      </section>

      <InlineAlert v-if="itemCount === 0" tone="error" class="mt-6">{{ t('documents.empty') }}</InlineAlert>
      <div :aria-busy="refreshing"><RequirementList :groups="requirements.groups" /></div>

      <div v-if="itemCount > 0" class="mt-9 rounded-3xl bg-brand-900 p-6 text-white">
        <p class="text-lg">{{ t('documents.preserved') }}</p>
        <RouterLink
          class="mt-5 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-white px-5 py-3 font-bold text-brand-900 no-underline hover:bg-brand-50 sm:w-auto"
          :to="
            auth.authenticated
              ? { name: 'application-create' }
              : { name: 'login', query: { intent: 'applicant', redirect: '/applications/new' } }
          "
        >
          {{ t('documents.publicCta') }}
        </RouterLink>
      </div>
    </template>

    <template v-else-if="loadError">
      <InlineAlert tone="error" class="mt-7">{{ t('documents.loadError') }}</InlineAlert>
      <button type="button" class="button-primary mt-6" @click="loadRequirements()">
        {{ t('common.actions.retry') }}
      </button>
    </template>
  </div>
</template>
