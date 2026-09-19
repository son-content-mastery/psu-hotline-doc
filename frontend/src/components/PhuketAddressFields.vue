<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ThaiLocationCatalog } from '@/types/api'

const props = withDefaults(defineProps<{
  catalog: ThaiLocationCatalog | null
  districtCode: string
  subdistrictCode: string
  disabled?: boolean
  districtInvalid?: boolean
  subdistrictInvalid?: boolean
  idPrefix?: string
}>(), {
  disabled: false,
  districtInvalid: false,
  subdistrictInvalid: false,
  idPrefix: 'address',
})

const emit = defineEmits<{
  'update:districtCode': [value: string]
  'update:subdistrictCode': [value: string]
}>()

const { t } = useI18n()
const selectedDistrict = computed(() =>
  props.catalog?.districts.find((district) => district.code === props.districtCode) ?? null,
)
const selectedSubdistrict = computed(() =>
  selectedDistrict.value?.subdistricts.find((subdistrict) => subdistrict.code === props.subdistrictCode) ?? null,
)

function updateDistrict(event: Event): void {
  const districtCode = (event.target as HTMLSelectElement).value
  const district = props.catalog?.districts.find((item) => item.code === districtCode)
  emit('update:districtCode', districtCode)
  if (!district?.subdistricts.some((item) => item.code === props.subdistrictCode)) {
    emit('update:subdistrictCode', '')
  }
}

function updateSubdistrict(event: Event): void {
  emit('update:subdistrictCode', (event.target as HTMLSelectElement).value)
}
</script>

<template>
  <fieldset :disabled="disabled" class="contents">
    <legend class="sr-only">{{ t('application.locationGroup') }}</legend>

    <div class="mb-6">
      <label class="field-label" :for="`${idPrefix}-province`">{{ t('application.province') }}</label>
      <input
        :id="`${idPrefix}-province`"
        class="field-input bg-slate-100 text-slate-700"
        type="text"
        :value="catalog?.province.name ?? ''"
        readonly
        aria-readonly="true"
      />
      <p class="mt-2 text-slate-600">{{ t('application.provinceFixedHelp') }}</p>
    </div>

    <div class="mb-6">
      <label class="field-label" :for="`${idPrefix}-district`">
        {{ t('application.district') }} <span class="text-base font-normal">({{ t('common.required') }})</span>
      </label>
      <select
        :id="`${idPrefix}-district`"
        class="field-input"
        :value="districtCode"
        :aria-invalid="districtInvalid"
        :aria-describedby="districtInvalid ? `${idPrefix}-district-error` : undefined"
        @change="updateDistrict"
      >
        <option value="">{{ t('application.selectDistrict') }}</option>
        <option v-for="district in catalog?.districts ?? []" :key="district.code" :value="district.code">
          {{ district.name }}
        </option>
      </select>
      <p v-if="districtInvalid" :id="`${idPrefix}-district-error`" class="field-error" role="alert">
        {{ t('application.requiredError') }}
      </p>
    </div>

    <div class="mb-6">
      <label class="field-label" :for="`${idPrefix}-subdistrict`">
        {{ t('application.subdistrict') }} <span class="text-base font-normal">({{ t('common.required') }})</span>
      </label>
      <select
        :id="`${idPrefix}-subdistrict`"
        class="field-input"
        :value="subdistrictCode"
        :disabled="disabled || !selectedDistrict"
        :aria-invalid="subdistrictInvalid"
        :aria-describedby="subdistrictInvalid ? `${idPrefix}-subdistrict-error` : undefined"
        @change="updateSubdistrict"
      >
        <option value="">
          {{ t(selectedDistrict ? 'application.selectSubdistrict' : 'application.selectDistrictFirst') }}
        </option>
        <option v-for="subdistrict in selectedDistrict?.subdistricts ?? []" :key="subdistrict.code" :value="subdistrict.code">
          {{ subdistrict.name }}
        </option>
      </select>
      <p v-if="subdistrictInvalid" :id="`${idPrefix}-subdistrict-error`" class="field-error" role="alert">
        {{ t('application.requiredError') }}
      </p>
    </div>

    <div class="mb-6">
      <label class="field-label" :for="`${idPrefix}-postal-code`">{{ t('application.postalCode') }}</label>
      <input
        :id="`${idPrefix}-postal-code`"
        class="field-input bg-slate-100 text-slate-700"
        type="text"
        :value="selectedSubdistrict?.postal_code ?? ''"
        readonly
        inputmode="numeric"
        autocomplete="postal-code"
        aria-readonly="true"
      />
      <p class="mt-2 text-slate-600">{{ t('application.postalCodeDerivedHelp') }}</p>
    </div>
  </fieldset>
</template>
