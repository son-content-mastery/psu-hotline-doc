<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api, ApiError } from '@/services/api'
import type { Application, RequirementsResponse } from '@/types/api'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const application = ref<Application | null>(null)
const requirements = ref<RequirementsResponse | null>(null)
const confirmed = ref(false)
const loading = ref(true)
const refreshing = ref(false)
const loadErrorKey = ref('')
const stale = ref(false)
const submitting = ref(false)
const submitErrorKey = ref('')
let dataRequest = 0

const complete = computed(() => Boolean(requirements.value?.complete_for_submission))
const isResubmission = computed(() => application.value?.status === 'REVISION_REQUIRED')
const canSubmit = computed(
  () => complete.value && ['READY_TO_SUBMIT', 'REVISION_REQUIRED'].includes(application.value?.status ?? ''),
)
const uploadedCount = computed(
  () =>
    requirements.value?.groups
      .flatMap((group) => group.items)
      .filter(
        (item) =>
          item.required &&
          item.status &&
          !['MISSING', 'REVISION_REQUIRED', 'REJECTED'].includes(item.status),
      ).length ?? 0,
)
const requiredCount = computed(
  () => requirements.value?.groups.flatMap((group) => group.items).filter((item) => item.required).length ?? 0,
)

async function loadData(preserveExisting = false): Promise<void> {
  const request = ++dataRequest
  const hasExisting = application.value !== null && requirements.value !== null
  if (preserveExisting && hasExisting) refreshing.value = true
  else loading.value = true
  if (!hasExisting) loadErrorKey.value = ''
  try {
    const [applicationResponse, requirementsResponse] = await Promise.all([
      api.get<Application>(`/api/v1/applications/${applicationId.value}/`),
      api.get<RequirementsResponse>(`/api/v1/applications/${applicationId.value}/requirements/`),
    ])
    if (request !== dataRequest) return
    application.value = applicationResponse
    requirements.value = requirementsResponse
    loadErrorKey.value = ''
    stale.value = false
  } catch (caught) {
    if (request !== dataRequest) return
    if (hasExisting) stale.value = true
    else {
      loadErrorKey.value =
        caught instanceof ApiError && [403, 404].includes(caught.status)
          ? 'common.neutralNotFound'
          : 'common.genericError'
    }
  } finally {
    if (request === dataRequest) {
      loading.value = false
      refreshing.value = false
    }
  }
}

async function submitApplication(): Promise<void> {
  if (!confirmed.value || !canSubmit.value) return
  submitting.value = true
  submitErrorKey.value = ''
  try {
    await api.post(`/api/v1/applications/${applicationId.value}/submit/`, {
      confirm_information_is_correct: true,
    })
    await router.replace({ name: 'application-submitted', params: { id: applicationId.value } })
  } catch {
    submitErrorKey.value = 'submission.submitError'
    await loadData()
  } finally {
    submitting.value = false
  }
}

watch(locale, () => loadData(true))
onMounted(loadData)
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('submission.reviewTitle') }}</h1>
    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="loadErrorKey" tone="error" class="mt-7">{{ t(loadErrorKey) }}</InlineAlert>

    <template v-else-if="application && requirements">
      <InlineAlert v-if="stale" tone="warning" live="polite" class="mt-6">
        {{ t('documents.localizedReloadError') }}
        <button type="button" class="ml-2 font-bold underline" @click="loadData(true)">
          {{ t('common.actions.retry') }}
        </button>
      </InlineAlert>
      <InlineAlert v-if="submitErrorKey" tone="error" class="mt-6">{{ t(submitErrorKey) }}</InlineAlert>

      <section class="card mt-7" aria-labelledby="review-property" :aria-busy="refreshing">
        <h2 id="review-property" class="text-2xl font-black">{{ t('submission.propertyTitle') }}</h2>
        <dl class="definition-grid mt-4">
          <dt>{{ t('application.name') }}</dt>
          <dd>{{ application.property.name }}</dd>
          <dt>{{ t('application.addressLine') }}</dt>
          <dd>
            {{ application.property.address_line }} {{ application.property.subdistrict }}
            {{ application.property.district }} {{ application.property.province }}
            {{ application.property.postal_code }}
          </dd>
        </dl>
      </section>

      <section class="card mt-5" aria-labelledby="review-classification">
        <h2 id="review-classification" class="text-2xl font-black">{{ t('submission.classificationTitle') }}</h2>
        <p class="mt-4 text-lg font-bold">
          {{ application.classification.property_type?.name ?? t('common.statusUnavailable') }}
        </p>
      </section>

      <section class="card mt-5" aria-labelledby="review-documents">
        <h2 id="review-documents" class="text-2xl font-black">{{ t('submission.documentsTitle') }}</h2>
        <p class="mt-4">
          {{ t('documents.completedCount', { count: uploadedCount }) }} / {{ t('documents.requiredCount', { count: requiredCount }) }}
        </p>
        <InlineAlert :tone="complete ? 'success' : 'warning'" class="mt-4">
          {{ t(complete ? 'submission.complete' : 'submission.incomplete') }}
        </InlineAlert>
        <RouterLink class="mt-4 inline-block font-bold" :to="{ name: 'application-documents', params: { id: applicationId } }">
          {{ t('common.actions.edit') }}
        </RouterLink>
      </section>

      <section class="card mt-5" aria-labelledby="review-authority">
        <h2 id="review-authority" class="text-2xl font-black">{{ t('submission.authorityTitle') }}</h2>
        <p class="mt-4 text-lg font-bold">
          {{ application.responsible_authority?.name ?? application.property.local_authority?.name ?? t('common.notAvailable') }}
        </p>
        <div class="mt-4"><StatusBadge :status="application.status" /></div>
      </section>

      <div class="mt-7 rounded-2xl border-2 border-slate-400 bg-white p-5">
        <label class="flex cursor-pointer items-start gap-4">
          <input v-model="confirmed" type="checkbox" class="mt-1 h-6 w-6 rounded text-brand-700 focus:ring-brand-700" />
          <span class="font-bold">{{ t('submission.confirmation') }}</span>
        </label>
      </div>

      <button
        type="button"
        class="button-primary mt-7"
        :disabled="!confirmed || !canSubmit || submitting"
        @click="submitApplication"
      >
        {{
          t(
            submitting
              ? 'submission.submitting'
              : isResubmission
                ? 'submission.resubmit'
                : 'submission.submit',
          )
        }}
      </button>
      <p v-if="!complete" class="mt-3 text-slate-700">{{ t('submission.incomplete') }}</p>
    </template>
  </div>
</template>
