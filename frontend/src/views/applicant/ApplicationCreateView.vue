<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { api, ApiError } from '@/services/api'
import { useClassificationStore } from '@/stores/classification'
import type { Application, LocalAuthority, Paginated } from '@/types/api'

const router = useRouter()
const { locale, t } = useI18n()
const classification = useClassificationStore()

const form = reactive({
  name: '',
  address_line: '',
  subdistrict: '',
  district: '',
  province: '',
  postal_code: '',
  local_authority_id: '',
})
const errors = reactive<Record<keyof typeof form, string>>({
  name: '',
  address_line: '',
  subdistrict: '',
  district: '',
  province: '',
  postal_code: '',
  local_authority_id: '',
})
const authorities = ref<LocalAuthority[]>([])
const authoritiesLoading = ref(true)
const authoritiesRefreshing = ref(false)
const authoritiesError = ref(false)
const authoritiesStale = ref(false)
const submitting = ref(false)
const submitErrorKey = ref('')
let authorityRequest = 0

async function loadAuthorities(preserveExisting = false): Promise<void> {
  const request = ++authorityRequest
  const hasExisting = authorities.value.length > 0
  if (preserveExisting && hasExisting) authoritiesRefreshing.value = true
  else authoritiesLoading.value = true
  if (!hasExisting) authoritiesError.value = false
  try {
    const response = await api.get<Paginated<LocalAuthority>>('/api/v1/local-authorities/?page_size=100')
    if (request !== authorityRequest) return
    authorities.value = response.results
    authoritiesError.value = false
    authoritiesStale.value = false
  } catch {
    if (request !== authorityRequest) return
    if (hasExisting) authoritiesStale.value = true
    else authoritiesError.value = true
  } finally {
    if (request === authorityRequest) {
      authoritiesLoading.value = false
      authoritiesRefreshing.value = false
    }
  }
}

function validationKey(key: keyof typeof form): string {
  if (!String(form[key]).trim()) {
    return key === 'local_authority_id' ? 'application.authorityError' : 'application.requiredError'
  }
  if (key === 'postal_code' && !/^\d{5}$/.test(form.postal_code.trim())) {
    return 'application.postalCodeError'
  }
  return ''
}

function validate(): boolean {
  let valid = true
  ;(Object.keys(errors) as Array<keyof typeof form>).forEach((key) => {
    errors[key] = validationKey(key)
    if (errors[key]) valid = false
  })
  if (!valid) {
    void nextTick(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
  }
  return valid
}

async function createApplication(): Promise<void> {
  submitErrorKey.value = ''
  if (!validate()) return
  submitting.value = true
  try {
    const application = await api.post<Application>('/api/v1/applications/', {
      property: {
        name: form.name.trim(),
        address_line: form.address_line.trim(),
        subdistrict: form.subdistrict.trim(),
        district: form.district.trim(),
        province: form.province.trim(),
        postal_code: form.postal_code.trim(),
        local_authority_id: Number(form.local_authority_id),
      },
      classification_answers: classification.answerPayload(),
    })
    classification.clearAfterApplicationCreated()
    await router.replace({ name: 'application-documents', params: { id: String(application.id) } })
  } catch (caught) {
    submitErrorKey.value =
      caught instanceof ApiError && ['NO_ACTIVE_CLASSIFICATION_RULE', 'OUT_OF_SCOPE'].includes(caught.code)
        ? 'application.classificationChanged'
        : 'application.createError'
  } finally {
    submitting.value = false
  }
}

watch(locale, () => loadAuthorities(true))
onMounted(loadAuthorities)
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('application.createTitle') }}</h1>
    <p class="page-intro">{{ t('application.createIntro') }}</p>

    <InlineAlert v-if="submitErrorKey" tone="error" class="mt-6">{{ t(submitErrorKey) }}</InlineAlert>
    <InlineAlert v-if="authoritiesError" tone="error" class="mt-6">
      {{ t('application.authoritiesError') }}
      <button type="button" class="ml-2 font-bold underline" @click="loadAuthorities()">
        {{ t('common.actions.retry') }}
      </button>
    </InlineAlert>
    <InlineAlert v-else-if="authoritiesStale" tone="warning" live="polite" class="mt-6">
      {{ t('application.authoritiesStale') }}
      <button type="button" class="ml-2 font-bold underline" @click="loadAuthorities(true)">
        {{ t('common.actions.retry') }}
      </button>
    </InlineAlert>

    <form class="card mt-7" novalidate @submit.prevent="createApplication">
      <div v-for="field in ['name', 'address_line', 'subdistrict', 'district', 'province', 'postal_code'] as const" :key="field" class="mb-6">
        <label class="field-label" :for="field">
          {{ t(`application.${field === 'address_line' ? 'addressLine' : field === 'postal_code' ? 'postalCode' : field === 'subdistrict' ? 'subdistrict' : field === 'district' ? 'district' : field === 'province' ? 'province' : 'name'}`) }}
          <span class="text-base font-normal">({{ t('common.required') }})</span>
        </label>
        <input
          :id="field"
          v-model="form[field]"
          class="field-input"
          type="text"
          :inputmode="field === 'postal_code' ? 'numeric' : undefined"
          :autocomplete="field === 'postal_code' ? 'postal-code' : field === 'address_line' ? 'street-address' : undefined"
          :aria-invalid="Boolean(errors[field])"
          :aria-describedby="errors[field] ? `${field}-error` : undefined"
        />
        <p v-if="errors[field]" :id="`${field}-error`" class="field-error" role="alert">{{ t(errors[field]) }}</p>
      </div>

      <div>
        <label class="field-label" for="local-authority">
          {{ t('application.authority') }} <span class="text-base font-normal">({{ t('common.required') }})</span>
        </label>
        <select
          id="local-authority"
          v-model="form.local_authority_id"
          class="field-input"
          :disabled="authoritiesLoading || (authoritiesError && authorities.length === 0)"
          :aria-busy="authoritiesRefreshing"
          :aria-invalid="Boolean(errors.local_authority_id)"
          :aria-describedby="errors.local_authority_id ? 'authority-help authority-error' : 'authority-help'"
        >
          <option value="">{{ t(authoritiesLoading ? 'application.authoritiesLoading' : 'application.selectAuthority') }}</option>
          <option v-for="authority in authorities" :key="authority.id" :value="String(authority.id)">
            {{ authority.name }}
          </option>
        </select>
        <p id="authority-help" class="mt-2 text-slate-600">{{ t('application.authorityHelp') }}</p>
        <p v-if="errors.local_authority_id" id="authority-error" class="field-error">
          {{ t(errors.local_authority_id) }}
        </p>
      </div>

      <button
        type="submit"
        class="button-primary mt-8"
        :disabled="submitting || authoritiesLoading || (authoritiesError && authorities.length === 0)"
      >
        {{ t(submitting ? 'application.creating' : 'application.create') }}
      </button>
    </form>
  </div>
</template>
