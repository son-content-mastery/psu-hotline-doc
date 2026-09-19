<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import DocumentPreflight from '@/components/DocumentPreflight.vue'
import RequirementList from '@/components/RequirementList.vue'
import { api, ApiError } from '@/services/api'
import type {
  Application,
  ApplicationDocument,
  Paginated,
  RequirementGroup,
  RequirementItem,
  RequirementStep,
  RequirementStepCode,
  RequirementsResponse,
} from '@/types/api'
import { formatDate, formatFileSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const application = ref<Application | null>(null)
const requirements = ref<RequirementsResponse | null>(null)
const documents = ref<ApplicationDocument[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadErrorKey = ref('')
const stale = ref(false)
const selectedFiles = reactive<Record<number, File[]>>({})
const fileErrors = reactive<Record<number, string>>({})
const uploadingTypeId = ref<number | null>(null)
const announcement = ref('')
const activeStepCode = ref<RequirementStepCode | null>(null)
let dataRequest = 0

const steps = computed(() => requirements.value?.steps ?? [])
const allItems = computed(() =>
  steps.value.length
    ? steps.value.flatMap((step) => step.items)
    : (requirements.value?.groups.flatMap((group) => group.items) ?? []),
)
const requiredCount = computed(() => allItems.value.filter((item) => item.required).length)
const currentUploadCount = computed(
  () =>
    allItems.value.filter(
      (item) => item.required && ['UPLOADED', 'APPROVED'].includes(item.status ?? 'MISSING'),
    ).length,
)
const actionCount = computed(
  () =>
    allItems.value.filter(
      (item) => item.required && ['MISSING', 'REVISION_REQUIRED', 'REJECTED'].includes(item.status ?? 'MISSING'),
    ).length,
)
const progressPercent = computed(() =>
  requiredCount.value ? Math.round((currentUploadCount.value / requiredCount.value) * 100) : 0,
)
const complete = computed(() => Boolean(requirements.value?.complete_for_submission))
const activeStep = computed<RequirementStep | null>(
  () => steps.value.find((step) => step.code === activeStepCode.value) ?? steps.value[0] ?? null,
)
const activeStepIndex = computed(() =>
  activeStep.value ? steps.value.findIndex((step) => step.code === activeStep.value?.code) : -1,
)
const activeStepGroups = computed<RequirementGroup[]>(() => {
  const items = activeStep.value?.items ?? []
  return [
    { category: 'OPERATOR_PREPARED', items: items.filter((item) => item.document_type.category === 'OPERATOR_PREPARED') },
    { category: 'EXTERNAL_AGENCY', items: items.filter((item) => item.document_type.category === 'EXTERNAL_AGENCY') },
  ]
})

function currentDocuments(item: RequirementItem): ApplicationDocument[] {
  return documents.value
    .filter((document) => document.document_type.id === item.document_type.id && document.is_current)
    .sort((a, b) => a.attachment_index - b.attachment_index)
}

function previousDocuments(item: RequirementItem): ApplicationDocument[] {
  return documents.value
    .filter((document) => document.document_type.id === item.document_type.id && !document.is_current)
    .sort((a, b) => b.version - a.version || a.attachment_index - b.attachment_index)
}

function canUpload(item: RequirementItem): boolean {
  if (!application.value) return false
  if (application.value.status === 'REVISION_REQUIRED') return item.status === 'REVISION_REQUIRED'
  return ['DRAFT', 'READY_TO_SUBMIT'].includes(application.value.status) && item.status !== 'APPROVED'
}

function firstActionStep(): RequirementStep | undefined {
  return steps.value.find((step) => step.action_required > 0) ?? steps.value[0]
}

async function selectStep(code: RequirementStepCode, focus = true): Promise<void> {
  activeStepCode.value = code
  await router.replace({ query: { ...route.query, step: code } })
  if (focus) {
    await nextTick()
    document.getElementById('active-step-heading')?.focus({ preventScroll: true })
  }
}

function initializeStep(): void {
  const queryStep = String(route.query.step ?? '') as RequirementStepCode
  const requested = steps.value.find((step) => step.code === queryStep)
  activeStepCode.value = requested?.code ?? firstActionStep()?.code ?? null
}

async function loadData(keepAnnouncement = false, preserveExisting = false): Promise<void> {
  const request = ++dataRequest
  const hasExisting = application.value !== null && requirements.value !== null
  if (preserveExisting && hasExisting) refreshing.value = true
  else loading.value = true
  if (!hasExisting) loadErrorKey.value = ''
  try {
    const [applicationResponse, requirementResponse, documentResponse] = await Promise.all([
      api.get<Application>(`/api/v1/applications/${applicationId.value}/`),
      api.get<RequirementsResponse>(`/api/v1/applications/${applicationId.value}/requirements/`),
      api.get<Paginated<ApplicationDocument>>(
        `/api/v1/applications/${applicationId.value}/documents/?include_versions=true&page_size=500`,
      ),
    ])
    if (request !== dataRequest) return
    application.value = applicationResponse
    requirements.value = requirementResponse
    documents.value = documentResponse.results
    loadErrorKey.value = ''
    stale.value = false
    if (!activeStepCode.value || !requirementResponse.steps.some((step) => step.code === activeStepCode.value)) {
      initializeStep()
    }
    if (!keepAnnouncement) announcement.value = ''
  } catch (caught) {
    if (request !== dataRequest) return
    if (hasExisting) stale.value = true
    else {
      loadErrorKey.value =
        caught instanceof ApiError && [403, 404].includes(caught.status)
          ? 'common.neutralNotFound'
          : 'documents.loadError'
    }
  } finally {
    if (request === dataRequest) {
      loading.value = false
      refreshing.value = false
    }
  }
}

function validateFiles(item: RequirementItem, files: File[]): string {
  if (!files.length) return 'documents.fileRequiredError'
  if (files.length > 10) return 'documents.fileCountError'
  if (files.length > 1 && !item.document_type.allows_multiple_files) return 'documents.singleFileOnlyError'
  const allowedExtensions = ['pdf', 'jpg', 'jpeg', 'png']
  const allowedMimeTypes = ['application/pdf', 'image/jpeg', 'image/png']
  for (const file of files) {
    const extension = file.name.toLowerCase().split('.').pop()
    if (!extension || !allowedExtensions.includes(extension) || (file.type && !allowedMimeTypes.includes(file.type))) {
      return 'documents.fileTypeError'
    }
    if (file.size > 10 * 1024 * 1024) return 'documents.fileSizeError'
  }
  return ''
}

async function selectFiles(item: RequirementItem, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  const typeId = item.document_type.id
  selectedFiles[typeId] = files
  fileErrors[typeId] = validateFiles(item, files)
  if (fileErrors[typeId] || uploadingTypeId.value !== null) {
    input.value = ''
    return
  }
  await upload(item, files)
  input.value = ''
}

async function upload(item: RequirementItem, files: File[]): Promise<void> {
  const typeId = item.document_type.id
  fileErrors[typeId] = validateFiles(item, files)
  if (fileErrors[typeId]) return

  uploadingTypeId.value = typeId
  try {
    const body = new FormData()
    body.append('document_type_id', String(typeId))
    if (files.length === 1) body.append('file', files[0] as File)
    else files.forEach((file) => body.append('files', file))
    const uploaded = await api.post<ApplicationDocument>(
      `/api/v1/applications/${applicationId.value}/documents/`,
      body,
    )
    selectedFiles[typeId] = []
    announcement.value = t('documents.uploadBundleSuccess', {
      name: item.document_type.name,
      count: uploaded.bundle_count ?? files.length,
      version: uploaded.version,
    })
    await loadData(true)
  } catch (caught) {
    if (caught instanceof ApiError) {
      const errorKeys: Record<string, string> = {
        FILE_TOO_LARGE: 'documents.fileSizeError',
        UNSUPPORTED_FILE_TYPE: 'documents.fileTypeError',
        MULTIPLE_FILES_NOT_ALLOWED: 'documents.singleFileOnlyError',
        DOCUMENT_NOT_OPEN_FOR_REVISION: 'documents.uploadStateChanged',
        APPLICATION_NOT_EDITABLE: 'documents.uploadStateChanged',
        NOT_FOUND: 'documents.uploadStateChanged',
      }
      fileErrors[typeId] = errorKeys[caught.code] ?? 'documents.uploadError'
      if (['DOCUMENT_NOT_OPEN_FOR_REVISION', 'APPLICATION_NOT_EDITABLE', 'NOT_FOUND'].includes(caught.code)) {
        await loadData(true, true)
      }
    } else {
      fileErrors[typeId] = 'documents.uploadError'
    }
  } finally {
    uploadingTypeId.value = null
  }
}

async function retryUpload(item: RequirementItem): Promise<void> {
  const files = selectedFiles[item.document_type.id] ?? []
  if (files.length) await upload(item, files)
}

async function focusFirstAction(): Promise<void> {
  const targetStep = firstActionStep()
  if (!targetStep) return
  if (activeStepCode.value !== targetStep.code) await selectStep(targetStep.code, false)
  const first = targetStep.items.find(
    (item) => item.required && ['MISSING', 'REVISION_REQUIRED', 'REJECTED'].includes(item.status ?? 'MISSING'),
  )
  await nextTick()
  if (first) document.getElementById(`file-${first.document_type.id}`)?.focus()
}

async function moveStep(offset: number): Promise<void> {
  const target = steps.value[activeStepIndex.value + offset]
  if (target) await selectStep(target.code)
}

function stepStatusKey(step: RequirementStep): string {
  if (step.complete) return 'documents.stepStatus.complete'
  if (step.action_required > 0 && step.completed > 0) return 'documents.stepStatus.inProgress'
  if (step.action_required > 0) return 'documents.stepStatus.notStarted'
  return 'documents.stepStatus.complete'
}

watch(locale, () => loadData(true, true))
onMounted(loadData)
</script>

<template>
  <div>
    <div class="mx-auto max-w-6xl">
      <h1 data-page-heading tabindex="-1" class="page-title">{{ t('documents.applicationTitle') }}</h1>
      <p v-if="application" class="page-intro">{{ t('documents.property', { name: application.property.name }) }}</p>

      <p v-if="loading" class="mt-7" aria-live="polite">{{ t('documents.loading') }}</p>
      <InlineAlert v-else-if="loadErrorKey" tone="error" class="mt-7">
        {{ t(loadErrorKey) }}
        <button type="button" class="ml-2 font-bold underline" @click="loadData()">
          {{ t('common.actions.retry') }}
        </button>
      </InlineAlert>

      <template v-else-if="application && requirements">
        <InlineAlert v-if="stale" tone="warning" live="polite" class="mt-7">
          {{ t('documents.localizedReloadError') }}
          <button type="button" class="ml-2 font-bold underline" @click="loadData(true, true)">
            {{ t('common.actions.retry') }}
          </button>
        </InlineAlert>
        <InlineAlert tone="warning" class="mt-7">
          {{ requirements.disclaimer || t('documents.demoNotice') }}
        </InlineAlert>

        <section class="mt-7 rounded-3xl border border-slate-300 bg-white p-5 sm:p-7" aria-labelledby="completion-heading">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 id="completion-heading" class="text-2xl font-black">{{ t('documents.completion') }}</h2>
              <p class="mt-2 text-lg font-bold">
                {{ t('documents.progressSummary', { completed: currentUploadCount, required: requiredCount }) }}
              </p>
              <p class="mt-1 text-slate-700">{{ t('documents.actionCount', { count: actionCount }) }}</p>
            </div>
            <p class="rounded-full bg-emerald-50 px-4 py-2 text-xl font-black text-emerald-900">{{ progressPercent }}%</p>
          </div>
          <div
            class="mt-5 h-4 overflow-hidden rounded-full bg-slate-200"
            role="progressbar"
            :aria-label="t('documents.overallProgress')"
            :aria-valuenow="progressPercent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div class="h-full rounded-full bg-emerald-600 transition-[width]" :style="{ width: `${progressPercent}%` }"></div>
          </div>
          <button v-if="!complete" type="button" class="mt-4 font-bold text-brand-800 underline underline-offset-4" @click="focusFirstAction">
            {{ t('documents.continueNextAction') }}
          </button>
        </section>

        <nav class="mt-7" :aria-label="t('documents.stepsLabel')">
          <ol class="flex gap-2 overflow-x-auto pb-3 lg:grid lg:grid-cols-5 lg:overflow-visible" role="list">
            <li v-for="(step, index) in steps" :key="step.code" class="min-w-48 lg:min-w-0">
              <button
                type="button"
                class="flex min-h-20 w-full items-center gap-3 rounded-2xl border-2 px-3 py-3 text-left no-underline transition"
                :class="
                  step.code === activeStep?.code
                    ? 'border-sky-700 bg-sky-50 shadow-sm'
                    : step.complete
                      ? 'border-emerald-300 bg-emerald-50'
                      : 'border-slate-300 bg-white hover:border-slate-500'
                "
                :aria-current="step.code === activeStep?.code ? 'step' : undefined"
                @click="selectStep(step.code)"
              >
                <span
                  class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-base font-black"
                  :class="
                    step.complete
                      ? 'border-emerald-700 bg-emerald-700 text-white'
                      : step.code === activeStep?.code
                        ? 'border-sky-700 bg-sky-700 text-white'
                        : 'border-slate-400 bg-white text-slate-800'
                  "
                  aria-hidden="true"
                >
                  {{ step.complete ? '✓' : index + 1 }}
                </span>
                <span class="min-w-0">
                  <span class="block font-black leading-tight">{{ t(`documents.steps.${step.code.toLowerCase()}.title`) }}</span>
                  <span class="mt-1 block text-sm font-semibold text-slate-600">
                    {{ t('documents.stepCompactProgress', { completed: step.completed, required: step.required }) }}
                  </span>
                  <span class="sr-only">{{ t(stepStatusKey(step), { completed: step.completed, required: step.required }) }}</span>
                </span>
              </button>
            </li>
          </ol>
        </nav>

        <p class="sr-only" aria-live="polite">{{ announcement }}</p>

        <section v-if="activeStep" class="mt-8" :aria-busy="refreshing" aria-labelledby="active-step-heading">
          <div class="rounded-3xl border-l-8 border-sky-700 bg-sky-50 p-5 sm:p-6">
            <p class="font-bold text-sky-900">{{ t('documents.stepNumber', { current: activeStepIndex + 1, total: steps.length }) }}</p>
            <h2 id="active-step-heading" tabindex="-1" class="mt-1 text-3xl font-black text-slate-950">
              {{ t(`documents.steps.${activeStep.code.toLowerCase()}.title`) }}
            </h2>
            <p class="mt-3 max-w-3xl text-lg text-slate-700">
              {{ t(`documents.steps.${activeStep.code.toLowerCase()}.description`) }}
            </p>
            <p class="mt-4 font-bold text-sky-950">
              {{ t('documents.stepProgress', { completed: activeStep.completed, required: activeStep.required }) }}
            </p>
          </div>

          <RequirementList :groups="activeStepGroups" show-status hide-empty-groups>
            <template #action="{ item }">
              <div v-if="currentDocuments(item).length" class="mb-5">
                <p class="font-bold">{{ t('documents.currentBundle', { count: currentDocuments(item).length }) }}</p>
                <ul class="mt-3 space-y-3" role="list">
                  <li v-for="documentItem in currentDocuments(item)" :key="documentItem.id" class="rounded-xl bg-slate-50 p-3">
                    <p class="font-semibold">
                      {{ t('documents.filePosition', { index: documentItem.attachment_index }) }} · {{ documentItem.original_filename }}
                    </p>
                    <p v-if="documentItem.uploaded_at" class="mt-1 text-sm text-slate-600">
                      {{ t('documents.version', { version: documentItem.version }) }} ·
                      {{ t('documents.uploadedAt', { date: formatDate(documentItem.uploaded_at, locale) }) }}
                    </p>
                    <a v-if="documentItem.download_url" class="mt-2 inline-block font-bold" :href="documentItem.download_url" target="_blank" rel="noopener">
                      {{ t('documents.viewFile', { name: item.document_type.name, version: documentItem.version }) }}
                      <span class="sr-only">({{ t('common.newWindow') }})</span>
                    </a>
                    <DocumentPreflight v-if="documentItem.preflight" :preflight="documentItem.preflight" />
                  </li>
                </ul>
              </div>

              <details v-if="previousDocuments(item).length" class="mb-5 rounded-xl bg-slate-50 p-4">
                <summary class="min-h-12 cursor-pointer py-2 font-bold">{{ t('documents.history') }}</summary>
                <ul class="mt-3 space-y-3" role="list">
                  <li v-for="documentItem in previousDocuments(item)" :key="documentItem.id" class="border-t border-slate-200 pt-3">
                    <p>
                      {{ t('documents.version', { version: documentItem.version }) }} ·
                      {{ t('documents.filePosition', { index: documentItem.attachment_index }) }} · {{ documentItem.original_filename }}
                    </p>
                    <p v-if="documentItem.latest_review_reason" class="text-slate-700">
                      {{ t('documents.reason', { reason: documentItem.latest_review_reason }) }}
                    </p>
                  </li>
                </ul>
              </details>

              <div v-if="canUpload(item)">
                <input
                  :id="`file-${item.document_type.id}`"
                  class="peer sr-only"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                  :multiple="item.document_type.allows_multiple_files"
                  :disabled="uploadingTypeId !== null"
                  :aria-describedby="`file-help-${item.document_type.id}${fileErrors[item.document_type.id] ? ` file-error-${item.document_type.id}` : ''}`"
                  :aria-invalid="Boolean(fileErrors[item.document_type.id])"
                  @change="selectFiles(item, $event)"
                />
                <label
                  class="inline-flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed border-slate-500 bg-white px-4 py-3 font-bold text-slate-900 hover:border-sky-700 hover:bg-sky-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-60 peer-focus-visible:outline peer-focus-visible:outline-4 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-amber-500"
                  :for="`file-${item.document_type.id}`"
                >
                  <svg class="h-6 w-6 text-sky-800" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M12 16V4m0 0L7 9m5-5 5 5" />
                    <path d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" />
                  </svg>
                  {{ t(item.status === 'MISSING' ? 'documents.chooseAndUpload' : 'documents.replaceAndUpload') }}
                </label>
                <p :id="`file-help-${item.document_type.id}`" class="mt-2 text-slate-600">
                  {{ t(item.document_type.allows_multiple_files ? 'documents.multiFileHelp' : 'documents.fileHelp') }}
                </p>
                <div v-if="uploadingTypeId === item.document_type.id" class="mt-3 rounded-xl border border-sky-300 bg-sky-50 p-3" aria-live="polite">
                  <p class="font-bold text-sky-950">{{ t('documents.uploading', { name: item.document_type.name }) }}</p>
                  <ul class="mt-2 space-y-1" role="list">
                    <li v-for="file in selectedFiles[item.document_type.id]" :key="`${file.name}-${file.size}`" class="font-semibold">
                      {{ t('documents.selectedFile', { name: file.name, size: formatFileSize(file.size) }) }}
                    </li>
                  </ul>
                </div>
                <p v-if="fileErrors[item.document_type.id]" :id="`file-error-${item.document_type.id}`" class="field-error" role="alert">
                  {{ t(fileErrors[item.document_type.id] ?? '') }}
                </p>
                <div v-if="fileErrors[item.document_type.id] && selectedFiles[item.document_type.id]?.length" class="mt-3">
                  <p class="font-semibold text-slate-700">{{ t('documents.selectionPreserved') }}</p>
                  <button
                    type="button"
                    class="button-secondary mt-3"
                    :disabled="uploadingTypeId !== null || !canUpload(item)"
                    @click="retryUpload(item)"
                  >
                    {{ t('documents.retryUpload') }}
                  </button>
                </div>
              </div>
            </template>
          </RequirementList>

          <div class="mt-10 flex flex-col gap-3 border-t border-slate-300 pt-6 sm:flex-row sm:justify-between">
            <button v-if="activeStepIndex > 0" type="button" class="button-secondary" @click="moveStep(-1)">{{ t('documents.previousStep') }}</button>
            <span v-else></span>
            <button v-if="activeStepIndex < steps.length - 1" type="button" class="button-primary" @click="moveStep(1)">{{ t('documents.nextStep') }}</button>
            <RouterLink v-else-if="complete" class="button-primary" :to="{ name: 'application-review', params: { id: applicationId } }">
              {{ t('documents.reviewBeforeSubmit') }}
            </RouterLink>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
