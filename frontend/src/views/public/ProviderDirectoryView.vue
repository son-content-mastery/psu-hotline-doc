<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { ProviderDirectoryEntry, ProviderServiceCode } from '@/types/api'

const { locale, t } = useI18n()
const providers = ref<ProviderDirectoryEntry[]>([])
const disclaimer = ref('')
const service = ref<ProviderServiceCode | ''>('')
const loading = ref(true)
const error = ref(false)
const services: ProviderServiceCode[] = ['APPLICATION_SUPPORT', 'TECHNICAL_DRAWING', 'FIRE_SAFETY', 'LEGAL_ADVICE']

function money(value: string | null, currency: string): string {
  if (value === null) return t('common.notAvailable')
  return new Intl.NumberFormat(locale.value, { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(value))
}

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const query = service.value ? `?service=${service.value}` : ''
    const response = await api.get<{ disclaimer: string; results: ProviderDirectoryEntry[] }>(`/api/v1/public/providers/${query}`)
    providers.value = response.results
    disclaimer.value = response.disclaimer
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(locale, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="max-w-3xl">
      <p class="text-sm font-black uppercase tracking-wide text-brand-700">{{ t('providers.eyebrow') }}</p>
      <h1 data-page-heading tabindex="-1" class="page-title mt-2">{{ t('providers.title') }}</h1>
      <p class="page-intro">{{ t('providers.intro') }}</p>
    </div>
    <InlineAlert v-if="disclaimer" tone="warning" class="mt-6 max-w-4xl">{{ disclaimer }}</InlineAlert>
    <form class="mt-7 max-w-xl" @submit.prevent="load">
      <label class="field-label" for="provider-service">{{ t('providers.filterLabel') }}</label>
      <div class="flex flex-col gap-3 sm:flex-row">
        <select id="provider-service" v-model="service" class="field-input">
          <option value="">{{ t('providers.allServices') }}</option>
          <option v-for="item in services" :key="item" :value="item">{{ t(`providers.services.${item}`) }}</option>
        </select>
        <button type="submit" class="button-secondary">{{ t('providers.applyFilter') }}</button>
      </div>
    </form>
    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7 max-w-3xl">{{ t('providers.error') }}</InlineAlert>
    <p v-else-if="providers.length === 0" class="mt-7 text-slate-600">{{ t('providers.empty') }}</p>
    <ul v-else class="mt-7 grid gap-5 md:grid-cols-2" role="list">
      <li v-for="provider in providers" :key="provider.id" class="card">
        <h2 class="text-xl font-black">{{ provider.name }}</h2>
        <p class="mt-2 text-sm font-bold text-slate-600">{{ t(`providers.source.${provider.source_status}`) }}</p>
        <ul class="mt-4 flex flex-wrap gap-2" role="list">
          <li v-for="item in provider.services" :key="item" class="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold">
            {{ t(`providers.services.${item}`) }}
          </li>
        </ul>
        <p class="mt-5 font-black">
          {{ t('providers.priceRange', { min: money(provider.price.min, provider.price.currency), max: money(provider.price.max, provider.price.currency) }) }}
        </p>
        <p v-if="provider.price.note" class="mt-2 text-sm text-slate-600">{{ provider.price.note }}</p>
        <a v-if="provider.contact_url" class="mt-5 inline-block font-bold" :href="provider.contact_url" target="_blank" rel="noopener noreferrer">
          {{ t('providers.contact') }} <span class="sr-only">({{ t('common.newWindow') }})</span>
        </a>
      </li>
    </ul>
  </div>
</template>
