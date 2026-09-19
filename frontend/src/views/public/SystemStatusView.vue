<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { SystemStatus } from '@/types/api'
import { formatDate } from '@/utils/format'

const { locale, t } = useI18n()
const status = ref<SystemStatus | null>(null)
const loading = ref(true)
const error = ref(false)

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    status.value = await api.get<SystemStatus>('/api/v1/system/status/')
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
  <div class="max-w-3xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('maintenance.title') }}</h1>
    <p v-if="loading" class="mt-6" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-6">
      {{ t('maintenance.error') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>
    <section v-else-if="status?.maintenance" class="card mt-7" aria-labelledby="maintenance-notice-title">
      <h2 id="maintenance-notice-title" class="text-2xl font-black">{{ status.maintenance.title }}</h2>
      <p class="mt-4 whitespace-pre-line text-slate-800">{{ status.maintenance.message }}</p>
      <dl class="definition-grid mt-6">
        <dt>{{ t('maintenance.starts') }}</dt>
        <dd>{{ formatDate(status.maintenance.starts_at, locale) }}</dd>
        <dt>{{ t('maintenance.ends') }}</dt>
        <dd>{{ formatDate(status.maintenance.ends_at, locale) }}</dd>
      </dl>
    </section>
    <InlineAlert v-else tone="success" class="mt-7">{{ t('maintenance.none') }}</InlineAlert>
  </div>
</template>
