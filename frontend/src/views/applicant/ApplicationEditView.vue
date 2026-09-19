<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import PhuketAddressFields from '@/components/PhuketAddressFields.vue'
import { ApiError, api } from '@/services/api'
import type { Application, LocalAuthority, Paginated, ThaiLocationCatalog } from '@/types/api'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const application = ref<Application | null>(null)
const authorities = ref<LocalAuthority[]>([])
const locations = ref<ThaiLocationCatalog | null>(null)
const loading = ref(true)
const loadError = ref(false)
const locationsStale = ref(false)
const saving = ref(false)
const saveError = ref(false)
const form = reactive({
  name: '', address_line: '', district_code: '', subdistrict_code: '',
  local_authority_id: '', rooms: '', guests: '', has_restaurant: false,
})
const errors = reactive<Record<string, boolean>>({})
const propertyFields = ['name', 'address_line'] as const
const canChangeRouting = computed(() => ['DRAFT', 'READY_TO_SUBMIT'].includes(application.value?.status ?? ''))

function fieldLabel(field: typeof propertyFields[number]): string {
  const keys = { name: 'name', address_line: 'addressLine' }
  return t(`application.${keys[field]}`)
}

async function loadLocations(): Promise<ThaiLocationCatalog> {
  return api.get<ThaiLocationCatalog>('/api/v1/locations/phuket/')
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    const [record, authorityPage, locationCatalog] = await Promise.all([
      api.get<Application>(`/api/v1/applications/${route.params.id}/`),
      api.get<Paginated<LocalAuthority>>('/api/v1/local-authorities/'),
      loadLocations(),
    ])
    if (!['DRAFT', 'READY_TO_SUBMIT', 'REVISION_REQUIRED'].includes(record.status)) {
      await router.replace({ name: 'application-tracking', params: { id: record.id } })
      return
    }
    application.value = record
    authorities.value = authorityPage.results
    locations.value = locationCatalog
    Object.assign(form, {
      name: record.property.name,
      address_line: record.property.address_line ?? '',
      district_code: record.property.district_code ?? '',
      subdistrict_code: record.property.subdistrict_code ?? '',
      local_authority_id: String(record.responsible_authority?.id ?? record.property.local_authority?.id ?? ''),
      rooms: String(record.classification.answers.rooms),
      guests: String(record.classification.answers.guests),
      has_restaurant: record.classification.answers.has_restaurant,
    })
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function validate(): boolean {
  propertyFields.forEach((field) => { errors[field] = !String(form[field]).trim() })
  errors.district_code = !form.district_code
  errors.subdistrict_code = !form.subdistrict_code
  if (canChangeRouting.value) {
    errors.local_authority_id = !form.local_authority_id
    errors.rooms = !Number.isInteger(Number(form.rooms)) || Number(form.rooms) < 1
    errors.guests = !Number.isInteger(Number(form.guests)) || Number(form.guests) < 1
  }
  const valid = !Object.values(errors).some(Boolean)
  if (!valid) void nextTick(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
  return valid
}

async function save(): Promise<void> {
  saveError.value = false
  if (!validate() || !application.value) return
  saving.value = true
  const property: Record<string, unknown> = Object.fromEntries(
    propertyFields.map((field) => [field, String(form[field]).trim()]),
  )
  property.subdistrict_code = form.subdistrict_code
  if (canChangeRouting.value) property.local_authority_id = Number(form.local_authority_id)
  const payload: Record<string, unknown> = { property }
  if (canChangeRouting.value) {
    payload.classification_answers = {
      rooms: Number(form.rooms), guests: Number(form.guests), has_restaurant: form.has_restaurant,
    }
  }
  try {
    await api.patch(`/api/v1/applications/${application.value.id}/`, payload)
    await router.replace({ name: 'application-documents', params: { id: application.value.id } })
  } catch (caught) {
    saveError.value = true
    if (caught instanceof ApiError && caught.code === 'APPLICATION_NOT_EDITABLE') await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
watch(locale, async () => {
  if (!locations.value) return
  try {
    locations.value = await loadLocations()
    locationsStale.value = false
  } catch {
    locationsStale.value = true
  }
})
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('application.editTitle') }}</h1>
    <p class="page-intro">{{ t('application.editIntro') }}</p>
    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('application.editLoading') }}</p>
    <InlineAlert v-else-if="loadError" tone="error" class="mt-7">
      {{ t('application.editError') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>
    <form v-else-if="application" class="card mt-7" novalidate @submit.prevent="save">
      <InlineAlert v-if="saveError" tone="error" class="mb-6">{{ t('application.saveError') }}</InlineAlert>
      <InlineAlert v-if="locationsStale" tone="warning" class="mb-6">
        {{ t('application.locationsStale') }}
        <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
      </InlineAlert>
      <InlineAlert v-if="!canChangeRouting" tone="info" class="mb-6">{{ t('application.revisionLocked') }}</InlineAlert>
      <div v-for="field in propertyFields" :key="field" class="mb-6">
        <label class="field-label" :for="`edit-${field}`">{{ fieldLabel(field) }} ({{ t('common.required') }})</label>
        <input :id="`edit-${field}`" v-model="form[field]" class="field-input" :aria-invalid="Boolean(errors[field])" />
        <p v-if="errors[field]" class="field-error" role="alert">{{ t('application.requiredError') }}</p>
      </div>
      <PhuketAddressFields
        v-model:district-code="form.district_code"
        v-model:subdistrict-code="form.subdistrict_code"
        :catalog="locations"
        :disabled="!locations"
        :district-invalid="Boolean(errors.district_code)"
        :subdistrict-invalid="Boolean(errors.subdistrict_code)"
        id-prefix="edit-address"
      />
      <div v-if="canChangeRouting" class="mb-6">
        <label class="field-label" for="edit-authority">{{ t('application.authority') }} ({{ t('common.required') }})</label>
        <select id="edit-authority" v-model="form.local_authority_id" class="field-input" :aria-invalid="Boolean(errors.local_authority_id)">
          <option value="">{{ t('application.selectAuthority') }}</option>
          <option v-for="authority in authorities" :key="authority.id" :value="String(authority.id)">{{ authority.name }}</option>
        </select>
      </div>
      <fieldset v-if="canChangeRouting" class="mt-8 border-t border-slate-200 pt-6">
        <legend class="text-xl font-black">{{ t('application.classificationFields') }}</legend>
        <InlineAlert tone="warning" class="mt-4">{{ t('application.classificationChangeWarning') }}</InlineAlert>
        <div class="mt-5 grid gap-5 sm:grid-cols-2">
          <label class="field-label">{{ t('application.rooms') }}<input v-model="form.rooms" class="field-input mt-2" type="number" min="1" :aria-invalid="Boolean(errors.rooms)" /></label>
          <label class="field-label">{{ t('application.guests') }}<input v-model="form.guests" class="field-input mt-2" type="number" min="1" :aria-invalid="Boolean(errors.guests)" /></label>
        </div>
        <label class="mt-5 flex items-center gap-3 font-bold"><input v-model="form.has_restaurant" type="checkbox" class="h-6 w-6" />{{ t('application.hasRestaurant') }}</label>
      </fieldset>
      <button type="submit" class="button-primary mt-8" :disabled="saving || !locations">{{ t(saving ? 'application.saving' : 'application.save') }}</button>
    </form>
  </div>
</template>
