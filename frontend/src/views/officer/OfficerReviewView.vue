<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { api, ApiError } from '@/services/api'
import type {
  DocumentStatus,
  License,
  OfficerAllowedAction,
  OfficerApplication,
  OfficerDocument,
  RequirementCategory,
  Role,
} from '@/types/api'
import { applicationStatusKey, documentStatusKey } from '@/utils/domain'
import { formatDate, fullDaysSince } from '@/utils/format'

type ReviewOutcome = Extract<DocumentStatus, 'APPROVED' | 'REVISION_REQUIRED' | 'REJECTED'>
type ApplicationDecision = 'revision' | 'approve' | 'reject'

interface ReviewFormState {
  outcome: ReviewOutcome | ''
  reason: string
  errorKey: string
  submitting: boolean
}

const route = useRoute()
const { locale, t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const application = ref<OfficerApplication | null>(null)
const loading = ref(true)
const loadError = ref('')
const reviewForms = reactive<Record<number, ReviewFormState>>({})
const announcement = ref('')
const decision = ref<ApplicationDecision | null>(null)
const decisionReason = ref('')
const decisionErrorKey = ref('')
const decisionWorking = ref(false)
const issuedLicense = ref<Pick<License, 'license_number' | 'artifact_kind'> | null>(null)

const sortedDocuments = computed(() =>
  [...(application.value?.documents ?? [])].sort((a, b) => {
    const reviewPriority = Number(b.status === 'UPLOADED') - Number(a.status === 'UPLOADED')
    if (reviewPriority) return reviewPriority
    const categoryOrder: Record<RequirementCategory, number> = { OPERATOR_PREPARED: 0, EXTERNAL_AGENCY: 1 }
    const categoryPriority = categoryOrder[a.category] - categoryOrder[b.category]
    if (categoryPriority) return categoryPriority
    return a.document_type.name.localeCompare(b.document_type.name, locale.value)
  }),
)

const documentCategoryCounts = computed(() => ({
  pending: application.value?.documents.filter((item) => item.status === 'UPLOADED').length ?? 0,
  operator: application.value?.documents.filter((item) => item.category === 'OPERATOR_PREPARED').length ?? 0,
  external: application.value?.documents.filter((item) => item.category === 'EXTERNAL_AGENCY').length ?? 0,
}))

const allowedActions = computed(() => new Set(application.value?.allowed_actions ?? []))
const canReviewDocuments = computed(() => allowedActions.value.has('REVIEW_DOCUMENTS'))
const hasApplicationDecision = computed(() =>
  (['REQUEST_REVISION', 'APPROVE', 'REJECT'] as OfficerAllowedAction[]).some((action) =>
    allowedActions.value.has(action),
  ),
)
const isNotificationApplication = computed(
  () => application.value?.classification.property_type?.issues_license === false,
)

function classificationLabel(): string {
  const serverName = application.value?.classification.property_type?.name
  if (serverName) return serverName
  if (application.value?.classification.outcome === 'TYPE_1') return t('classification.result.outcomes.type1.title')
  if (application.value?.classification.outcome === 'TYPE_2') return t('classification.result.outcomes.type2.title')
  return t('common.statusUnavailable')
}

function ensureForm(document: OfficerDocument): ReviewFormState {
  let form = reviewForms[document.id]
  if (!form) {
    form = { outcome: '', reason: '', errorKey: '', submitting: false }
    reviewForms[document.id] = form
  }
  return form
}

async function load(keepAnnouncement = false): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    application.value = await api.get<OfficerApplication>(
      `/api/v1/officer/applications/${applicationId.value}/`,
    )
    application.value.documents.forEach(ensureForm)
    if (!keepAnnouncement) announcement.value = ''
  } catch (caught) {
    loadError.value =
      caught instanceof ApiError && [403, 404].includes(caught.status)
        ? t('officer.reviewLoadError')
        : t('common.genericError')
  } finally {
    loading.value = false
  }
}

async function reviewDocument(document: OfficerDocument): Promise<void> {
  const form = ensureForm(document)
  form.errorKey = ''
  if (!form.outcome) {
    form.errorKey = 'officer.outcomeRequired'
    return
  }
  if (form.outcome !== 'APPROVED' && !form.reason.trim()) {
    form.errorKey = 'officer.reasonRequired'
    void nextTick(() => documentGetReason(document.id)?.focus())
    return
  }

  form.submitting = true
  try {
    await api.post(`/api/v1/officer/documents/${document.id}/review/`, {
      outcome: form.outcome,
      reason: form.reason.trim() || undefined,
    })
    announcement.value = t('officer.reviewSuccess', {
      name: document.document_type.name,
      version: document.version,
    })
    await load(true)
  } catch (caught) {
    if (caught instanceof ApiError && ['DOCUMENT_VERSION_NOT_CURRENT', 'DOCUMENT_ALREADY_REVIEWED'].includes(caught.code)) {
      form.errorKey = 'officer.staleVersion'
      await load(true)
    } else {
      form.errorKey = 'officer.reviewError'
    }
  } finally {
    form.submitting = false
  }
}

function documentGetReason(id: number): HTMLTextAreaElement | null {
  return document.querySelector<HTMLTextAreaElement>(`#document-reason-${id}`)
}

function selectDecision(value: ApplicationDecision): void {
  decision.value = value
  decisionErrorKey.value = ''
  decisionReason.value = ''
  issuedLicense.value = null
  void nextTick(() => document.getElementById('application-decision-reason')?.focus())
}

async function submitDecision(): Promise<void> {
  if (!decision.value) return
  const reasonRequired = decision.value !== 'approve'
  if (reasonRequired && !decisionReason.value.trim()) {
    decisionErrorKey.value = 'officer.reasonRequired'
    document.getElementById('application-decision-reason')?.focus()
    return
  }
  decisionWorking.value = true
  decisionErrorKey.value = ''
  try {
    const endpoint =
      decision.value === 'approve'
        ? 'approve'
        : decision.value === 'revision'
          ? 'request-revision'
          : 'reject'
    const payload =
      decision.value === 'approve'
        ? { note: decisionReason.value.trim() }
        : { reason: decisionReason.value.trim() }
    const response = await api.post<{ license?: Pick<License, 'license_number' | 'artifact_kind'> }>(
      `/api/v1/officer/applications/${applicationId.value}/${endpoint}/`,
      payload,
    )
    if (response.license) issuedLicense.value = response.license
    const successKey =
      decision.value === 'approve'
        ? isNotificationApplication.value
          ? 'officer.decisionSuccessNotification'
          : 'officer.decisionSuccessApproved'
        : decision.value === 'revision'
          ? 'officer.decisionSuccessRevision'
          : 'officer.decisionSuccessRejected'
    announcement.value = t(successKey)
    decision.value = null
    decisionReason.value = ''
    await load(true)
  } catch (caught) {
    if (caught instanceof ApiError && ['INVALID_STATUS_TRANSITION', 'APPROVAL_NOT_ALLOWED'].includes(caught.code)) {
      decisionErrorKey.value = 'officer.staleDecision'
      await load(true)
    } else {
      decisionErrorKey.value = 'officer.decisionError'
    }
  } finally {
    decisionWorking.value = false
  }
}

function categoryLabel(category: RequirementCategory): string {
  return t(category === 'OPERATOR_PREPARED' ? 'documents.groups.operator' : 'documents.groups.external')
}

function roleLabel(role: Role): string {
  const keys: Record<Role, string> = {
    APPLICANT: 'common.roles.applicant',
    LOCAL_OFFICER: 'common.roles.localOfficer',
    CENTRAL_OFFICER: 'common.roles.centralOfficer',
    SUPER_ADMIN: 'common.roles.superAdmin',
  }
  return t(keys[role])
}

function uploaderLabel(documentItem: OfficerDocument): string {
  return `${documentItem.uploaded_by.display_name} · ${roleLabel(documentItem.uploaded_by.role ?? documentItem.uploader_role)}`
}

watch(locale, () => load(true))
onMounted(load)
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'officer-queue' }">{{ t('officer.backToQueue') }}</RouterLink>
    <h1 data-page-heading tabindex="-1" class="page-title mt-5">
      {{ t('officer.reviewTitle', { reference: application?.reference_number ?? '' }) }}
    </h1>

    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="loadError" tone="error" class="mt-7 max-w-3xl">
      {{ loadError }}
      <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else-if="application">
      <p class="sr-only" aria-live="polite">{{ announcement }}</p>
      <InlineAlert v-if="announcement" tone="success" class="mt-6 max-w-3xl">{{ announcement }}</InlineAlert>

      <section class="card mt-7 max-w-4xl" aria-labelledby="officer-summary-heading">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <h2 id="officer-summary-heading" class="text-2xl font-black">{{ t('officer.summaryTitle') }}</h2>
          <StatusBadge :status="application.status" />
        </div>
        <dl class="definition-grid mt-5">
          <dt>{{ t('officer.property') }}</dt>
          <dd>{{ application.property.name }}</dd>
          <dt>{{ t('officer.type') }}</dt>
          <dd>{{ classificationLabel() }}</dd>
          <dt>{{ t('application.authority') }}</dt>
          <dd>{{ application.property.local_authority?.name ?? t('common.notAvailable') }}</dd>
          <dt>{{ t('officer.status') }}</dt>
          <dd>{{ t(applicationStatusKey(application.status)) }}</dd>
          <dt v-if="application.waiting_since">{{ t('officer.waiting') }}</dt>
          <dd v-if="application.waiting_since">
            {{ t('tracking.waitingDays', fullDaysSince(application.waiting_since) ?? 0) }}
          </dd>
          <dt v-if="application.submitted_at">{{ t('officer.submitted') }}</dt>
          <dd v-if="application.submitted_at">{{ formatDate(application.submitted_at, locale) }}</dd>
          <dt v-if="application.resubmitted_at">{{ t('officer.resubmitted') }}</dt>
          <dd v-if="application.resubmitted_at">{{ formatDate(application.resubmitted_at, locale) }}</dd>
        </dl>
      </section>

      <section v-if="application.history?.length" class="card mt-7 max-w-4xl" aria-labelledby="officer-history-heading">
        <h2 id="officer-history-heading" class="text-2xl font-black">{{ t('officer.historyTitle') }}</h2>
        <ol class="mt-5 space-y-4" role="list">
          <li v-for="event in application.history" :key="event.id" class="border-l-4 border-sky-700 pl-4">
            <p class="font-black">{{ t(applicationStatusKey(event.to_status)) }}</p>
            <p v-if="event.reason" class="mt-1 text-slate-700">{{ t('officer.historyReason', { reason: event.reason }) }}</p>
            <time class="mt-1 block text-sm text-slate-600" :datetime="event.occurred_at">{{ formatDate(event.occurred_at, locale) }}</time>
          </li>
        </ol>
      </section>

      <section class="mt-9" aria-labelledby="documents-review-heading">
        <h2 id="documents-review-heading" class="text-2xl font-black">{{ t('officer.documentTitle') }}</h2>
        <div v-if="application.documents.length" class="mt-4 flex flex-wrap gap-2" :aria-label="t('officer.documentGroupsLabel')">
          <span class="rounded-full border border-amber-700 bg-amber-50 px-3 py-1 text-sm font-bold text-amber-950">
            {{ t('officer.pendingGroup', { count: documentCategoryCounts.pending }) }}
          </span>
          <span class="rounded-full border border-brand-700 bg-brand-50 px-3 py-1 text-sm font-bold text-brand-900">
            {{ t('officer.operatorGroup', { count: documentCategoryCounts.operator }) }}
          </span>
          <span class="rounded-full border border-slate-500 bg-slate-100 px-3 py-1 text-sm font-bold text-slate-900">
            {{ t('officer.externalGroup', { count: documentCategoryCounts.external }) }}
          </span>
        </div>
        <p v-if="application.documents.length" class="mt-3 text-sm text-slate-600">{{ t('officer.documentSortHelp') }}</p>
        <InlineAlert v-if="application.documents.length === 0" tone="warning" class="mt-5 max-w-3xl">
          {{ t('officer.noDocuments') }}
        </InlineAlert>

        <ul v-else class="mt-5 space-y-5" role="list">
          <li v-for="documentItem in sortedDocuments" :key="documentItem.id" class="card max-w-4xl">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 class="text-xl font-black">{{ documentItem.document_type.name }}</h3>
                <p class="mt-1 font-extrabold text-brand-800">{{ t('common.current') }}</p>
                <p class="mt-1 text-slate-600">
                  {{ t('documents.version', { version: documentItem.version }) }} ·
                  {{ documentItem.original_filename ?? t('common.notAvailable') }}
                </p>
              </div>
              <StatusBadge :status="documentItem.status" kind="document" />
            </div>

            <dl class="definition-grid mt-4">
              <dt>{{ t('officer.documentCategory') }}</dt>
              <dd>{{ categoryLabel(documentItem.category) }}</dd>
              <dt v-if="documentItem.uploaded_at">{{ t('officer.uploadedAt') }}</dt>
              <dd v-if="documentItem.uploaded_at">{{ formatDate(documentItem.uploaded_at, locale) }}</dd>
              <dt v-if="documentItem.uploaded_by">{{ t('officer.uploadedBy') }}</dt>
              <dd v-if="documentItem.uploaded_by">{{ uploaderLabel(documentItem) }}</dd>
            </dl>

            <a
              v-if="documentItem.download_url"
              class="mt-4 inline-block font-bold"
              :href="documentItem.download_url"
              target="_blank"
              rel="noopener"
            >
              {{ t('officer.download', { name: documentItem.document_type.name, version: documentItem.version }) }}
              <span class="sr-only">({{ t('common.newWindow') }})</span>
            </a>

            <details
              v-if="documentItem.reviews?.length || documentItem.versions?.length"
              class="mt-5 rounded-xl bg-slate-50 p-4"
            >
              <summary class="min-h-12 cursor-pointer py-2 font-bold">{{ t('officer.priorReviews') }}</summary>
              <section v-if="documentItem.reviews?.length" class="mt-3" :aria-label="t('officer.currentReviews')">
                <h4 class="font-black">{{ t('officer.currentReviews') }}</h4>
                <ul class="mt-2 space-y-3" role="list">
                  <li v-for="review in documentItem.reviews" :key="review.id" class="border-t border-slate-200 pt-3">
                    <p class="font-bold">{{ t(documentStatusKey(review.outcome)) }}</p>
                    <p v-if="review.reason">{{ review.reason }}</p>
                    <p v-if="review.reviewed_by" class="text-sm text-slate-600">
                      {{ t('officer.reviewedBy', { name: review.reviewed_by.display_name }) }}
                    </p>
                    <time class="text-sm text-slate-600" :datetime="review.reviewed_at">
                      {{ formatDate(review.reviewed_at, locale) }}
                    </time>
                  </li>
                </ul>
              </section>

              <section v-if="documentItem.versions?.length" class="mt-5" :aria-label="t('officer.priorVersions')">
                <h4 class="font-black">{{ t('officer.priorVersions') }}</h4>
                <ul class="mt-2 space-y-4" role="list">
                  <li
                    v-for="priorVersion in documentItem.versions"
                    :key="priorVersion.id"
                    class="rounded-xl border border-slate-300 bg-white p-4"
                  >
                    <div class="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p class="font-extrabold text-slate-800">
                          {{ t('common.previous') }} · {{ t('documents.version', { version: priorVersion.version }) }}
                        </p>
                        <p class="mt-1 break-all text-slate-600">
                          {{ priorVersion.original_filename ?? t('common.notAvailable') }}
                        </p>
                      </div>
                      <StatusBadge :status="priorVersion.status" kind="document" />
                    </div>
                    <dl class="definition-grid mt-3">
                      <dt>{{ t('officer.documentCategory') }}</dt>
                      <dd>{{ categoryLabel(priorVersion.category) }}</dd>
                      <dt v-if="priorVersion.uploaded_at">{{ t('officer.uploadedAt') }}</dt>
                      <dd v-if="priorVersion.uploaded_at">{{ formatDate(priorVersion.uploaded_at, locale) }}</dd>
                      <dt v-if="priorVersion.uploaded_by">{{ t('officer.uploadedBy') }}</dt>
                      <dd v-if="priorVersion.uploaded_by">{{ uploaderLabel(priorVersion) }}</dd>
                    </dl>
                    <a
                      v-if="priorVersion.download_url"
                      class="mt-3 inline-block font-bold"
                      :href="priorVersion.download_url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ t('officer.download', { name: priorVersion.document_type.name, version: priorVersion.version }) }}
                      <span class="sr-only">({{ t('common.newWindow') }})</span>
                    </a>
                    <ul v-if="priorVersion.reviews?.length" class="mt-3 space-y-2" role="list">
                      <li v-for="review in priorVersion.reviews" :key="review.id" class="border-t border-slate-200 pt-2">
                        <p class="font-bold">{{ t(documentStatusKey(review.outcome)) }}</p>
                        <p v-if="review.reason">{{ review.reason }}</p>
                        <time class="text-sm text-slate-600" :datetime="review.reviewed_at">
                          {{ formatDate(review.reviewed_at, locale) }}
                        </time>
                      </li>
                    </ul>
                  </li>
                </ul>
              </section>
            </details>

            <form
              v-if="canReviewDocuments && documentItem.is_current && documentItem.status === 'UPLOADED'"
              class="mt-6 border-t border-slate-200 pt-5"
              data-testid="document-review-form"
              :data-document-id="documentItem.id"
              :data-document-type-id="documentItem.document_type.id"
              @submit.prevent="reviewDocument(documentItem)"
            >
              <fieldset
                :aria-describedby="
                  !ensureForm(documentItem).outcome && ensureForm(documentItem).errorKey
                    ? `document-outcome-error-${documentItem.id}`
                    : undefined
                "
              >
                <legend class="text-lg font-black">
                  {{ t('officer.reviewOutcome', { name: documentItem.document_type.name, version: documentItem.version }) }}
                </legend>
                <div class="mt-3 grid gap-3">
                  <label v-for="option in [
                    { value: 'APPROVED', key: 'officer.outcomes.approved' },
                    { value: 'REVISION_REQUIRED', key: 'officer.outcomes.revision' },
                    { value: 'REJECTED', key: 'officer.outcomes.rejected' },
                  ] as const" :key="option.value" class="flex min-h-12 items-center gap-3 rounded-xl border border-slate-400 p-3">
                    <input
                      v-model="ensureForm(documentItem).outcome"
                      type="radio"
                      :name="`review-${documentItem.id}`"
                      :value="option.value"
                      class="h-5 w-5 text-brand-700 focus:ring-brand-700"
                      @change="ensureForm(documentItem).errorKey = ''"
                    />
                    <span class="font-bold">{{ t(option.key) }}</span>
                  </label>
                </div>
              </fieldset>
              <p
                v-if="!ensureForm(documentItem).outcome && ensureForm(documentItem).errorKey"
                :id="`document-outcome-error-${documentItem.id}`"
                class="field-error"
                role="alert"
              >
                {{ t(ensureForm(documentItem).errorKey) }}
              </p>

              <div v-if="ensureForm(documentItem).outcome" class="mt-5">
                <label class="field-label" :for="`document-reason-${documentItem.id}`">
                  {{ t('officer.reason') }}
                  <span v-if="ensureForm(documentItem).outcome !== 'APPROVED'" class="text-base font-normal">({{ t('common.required') }})</span>
                </label>
                <textarea
                  :id="`document-reason-${documentItem.id}`"
                  v-model="ensureForm(documentItem).reason"
                  class="field-input min-h-28"
                  :aria-invalid="Boolean(ensureForm(documentItem).errorKey)"
                  :aria-describedby="`document-reason-help-${documentItem.id}${ensureForm(documentItem).errorKey ? ` document-error-${documentItem.id}` : ''}`"
                  @input="ensureForm(documentItem).errorKey = ''"
                />
                <p :id="`document-reason-help-${documentItem.id}`" class="mt-2 text-slate-600">{{ t('officer.reasonHelp') }}</p>
                <p v-if="ensureForm(documentItem).errorKey" :id="`document-error-${documentItem.id}`" class="field-error" role="alert">
                  {{ t(ensureForm(documentItem).errorKey) }}
                </p>
                <button type="submit" class="button-primary mt-4" :disabled="ensureForm(documentItem).submitting">
                  {{ t(ensureForm(documentItem).submitting ? 'officer.reviewing' : 'officer.confirmReview') }}
                </button>
              </div>
            </form>
          </li>
        </ul>
      </section>

      <section v-if="hasApplicationDecision" class="card mt-9 max-w-4xl" aria-labelledby="application-decision-heading">
        <h2 id="application-decision-heading" class="text-2xl font-black">{{ t('officer.decisionTitle') }}</h2>
        <p class="mt-3 text-slate-700">{{ t('officer.decisionIntro') }}</p>

        <div class="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <button
            v-if="allowedActions.has('REQUEST_REVISION')"
            type="button"
            class="button-secondary"
            @click="selectDecision('revision')"
          >
            {{ t('officer.requestRevision') }}
          </button>
          <button v-if="allowedActions.has('APPROVE')" type="button" class="button-primary" @click="selectDecision('approve')">
            {{ t(isNotificationApplication ? 'officer.approveNotification' : 'officer.approve') }}
          </button>
          <button v-if="allowedActions.has('REJECT')" type="button" class="button-danger" @click="selectDecision('reject')">
            {{ t('officer.reject') }}
          </button>
        </div>

        <form v-if="decision" class="mt-6 rounded-2xl border-2 border-slate-400 p-5" @submit.prevent="submitDecision">
          <label class="field-label" for="application-decision-reason">
            {{ t(decision === 'approve' ? 'officer.approveNote' : 'officer.applicationReason') }}
            <span v-if="decision !== 'approve'" class="text-base font-normal">({{ t('common.required') }})</span>
          </label>
          <textarea
            id="application-decision-reason"
            v-model="decisionReason"
            class="field-input min-h-28"
            :aria-invalid="Boolean(decisionErrorKey)"
            :aria-describedby="decisionErrorKey ? 'application-decision-error' : undefined"
            @input="decisionErrorKey = ''"
          />
          <p v-if="decisionErrorKey" id="application-decision-error" class="field-error" role="alert">
            {{ t(decisionErrorKey) }}
          </p>
          <div class="mt-5 flex flex-col-reverse gap-3 sm:flex-row">
            <button type="button" class="button-secondary" @click="decision = null">{{ t('common.actions.cancel') }}</button>
            <button
              type="submit"
              :class="decision === 'reject' ? 'button-danger' : 'button-primary'"
              :disabled="decisionWorking"
            >
              {{
                t(
                  decisionWorking
                    ? 'officer.decisionWorking'
                    : decision === 'approve'
                      ? isNotificationApplication
                        ? 'officer.approveNotificationConfirm'
                        : 'officer.approveConfirm'
                      : decision === 'revision'
                        ? 'officer.revisionConfirm'
                        : 'officer.rejectConfirm',
                )
              }}
            </button>
          </div>
        </form>
      </section>

      <InlineAlert v-if="issuedLicense" tone="success" class="mt-6 max-w-4xl">
        {{
          t(
            issuedLicense.artifact_kind === 'NOTIFICATION_ACKNOWLEDGEMENT'
              ? 'officer.decisionSuccessNotification'
              : 'officer.decisionSuccessApproved',
          )
        }}
        {{ issuedLicense.license_number }}
      </InlineAlert>
    </template>
  </div>
</template>
