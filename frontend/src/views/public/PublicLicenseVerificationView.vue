<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { PublicLicenseVerification } from '@/types/api'
import { formatDate } from '@/utils/format'

const route = useRoute()
const { locale, t } = useI18n()
const token = computed(() => String(route.params.token))
const record = ref<PublicLicenseVerification | null>(null)
const loading = ref(true)
const notFound = ref(false)

const statusTone = computed(() => (record.value?.status === 'EXPIRED' ? 'bg-amber-100 text-amber-950' : 'bg-emerald-100 text-emerald-950'))

async function load(): Promise<void> {
  loading.value = true
  notFound.value = false
  try {
    record.value = await api.get<PublicLicenseVerification>(`/api/v1/public/licenses/${token.value}/`)
  } catch {
    record.value = null
    notFound.value = true
  } finally {
    loading.value = false
  }
}

watch(locale, load)
onMounted(load)
</script>

<template>
  <main class="page-narrow">
    <p class="eyebrow">{{ t('verification.eyebrow') }}</p>
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('verification.title') }}</h1>
    <p class="page-lead">{{ t('verification.intro') }}</p>

    <p v-if="loading" class="mt-8" aria-live="polite">{{ t('verification.loading') }}</p>
    <InlineAlert v-else-if="notFound" tone="error" class="mt-8">
      {{ t('verification.notFound') }}
    </InlineAlert>

    <article v-else-if="record" class="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p class="text-sm font-bold text-slate-600">{{ t('verification.reference') }}</p>
          <p class="mt-1 select-all break-all text-2xl font-black">{{ record.license_number }}</p>
        </div>
        <p class="rounded-full px-4 py-2 text-sm font-bold" :class="statusTone" role="status">
          {{ t(`verification.status.${record.status.toLowerCase()}`) }}
        </p>
      </div>

      <dl class="definition-grid mt-8 border-t border-slate-200 pt-6">
        <dt>{{ t('verification.property') }}</dt>
        <dd>{{ record.property.name }}</dd>
        <dt>{{ t('verification.propertyType') }}</dt>
        <dd>{{ record.property_type.name }}</dd>
        <dt>{{ t('verification.authority') }}</dt>
        <dd>{{ record.issuing_authority.name }}</dd>
        <dt>{{ t('verification.issuedAt') }}</dt>
        <dd>{{ formatDate(record.issued_at, locale, false) }}</dd>
        <template v-if="record.expires_at">
          <dt>{{ t('verification.expiresAt') }}</dt>
          <dd>{{ formatDate(record.expires_at, locale, false) }}</dd>
        </template>
      </dl>
      <p class="mt-7 border-t border-slate-200 pt-5 text-sm text-slate-600">
        {{ t('verification.privacyNote') }}
      </p>
    </article>
  </main>
</template>
