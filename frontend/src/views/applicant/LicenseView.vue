<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { License } from '@/types/api'
import { formatDate, formatMoney } from '@/utils/format'

const route = useRoute()
const { locale, t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const license = ref<License | null>(null)
const loading = ref(true)
const error = ref(false)
const isAcknowledgement = computed(() => license.value?.artifact_kind === 'NOTIFICATION_ACKNOWLEDGEMENT')

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    license.value = await api.get<License>(`/api/v1/applications/${applicationId.value}/license/`)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function printPage(): void {
  window.print()
}

watch(locale, load)
onMounted(load)
</script>

<template>
  <div class="page-narrow">
    <div class="no-print mb-6">
      <RouterLink :to="{ name: 'application-tracking', params: { id: applicationId } }">
        {{ t('license.backToTracking') }}
      </RouterLink>
    </div>
    <h1 data-page-heading tabindex="-1" class="page-title text-center">
      {{ t(isAcknowledgement ? 'license.acknowledgementTitle' : 'license.title') }}
    </h1>
    <p class="mt-3 text-center text-slate-700">{{ t('license.printNotice') }}</p>

    <p v-if="loading" class="mt-7 text-center" aria-live="polite">{{ t('license.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7">
      {{ t('license.unavailable') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <article v-else-if="license" class="mt-7 rounded-3xl border-4 border-double border-brand-800 bg-white p-6 sm:p-10">
      <p class="text-center text-sm font-bold uppercase tracking-[0.2em] text-brand-800">{{ t('common.serviceName') }}</p>
      <p class="mt-4 text-center text-sm font-bold text-slate-600">
        {{ t(isAcknowledgement ? 'license.acknowledgementNumber' : 'license.licenseNumber') }}
      </p>
      <p class="mt-1 select-all break-all text-center text-3xl font-black">{{ license.license_number }}</p>
      <dl class="definition-grid mt-9 border-t border-slate-300 pt-7">
        <dt>{{ t('license.applicationReference') }}</dt>
        <dd class="select-all font-bold">{{ license.application_reference_number }}</dd>
        <dt>{{ t('license.property') }}</dt>
        <dd>{{ license.property.name }}</dd>
        <dt>{{ t('license.address') }}</dt>
        <dd>{{ license.property.address }}</dd>
        <dt>{{ t('license.propertyType') }}</dt>
        <dd>{{ license.property_type.name }}</dd>
        <dt>{{ t('license.authority') }}</dt>
        <dd>{{ license.issuing_authority.name }}</dd>
        <dt>{{ t('license.issuedAt') }}</dt>
        <dd>{{ formatDate(license.issued_at, locale, false) }}</dd>
        <template v-if="license.expires_at">
          <dt>{{ t('license.expiresAt') }}</dt>
          <dd>{{ formatDate(license.expires_at, locale, false) }}</dd>
        </template>
        <template v-if="license.fee">
          <dt>{{ t('license.fee') }}</dt>
          <dd>{{ formatMoney(license.fee.amount_snapshot, license.fee.currency, locale) }}</dd>
        </template>
      </dl>
    </article>

    <button v-if="license" type="button" class="button-primary no-print mt-7" @click="printPage">
      {{ t('license.print') }}
    </button>
  </div>
</template>
