<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { Application } from '@/types/api'

const route = useRoute()
const { t } = useI18n()
const applicationId = computed(() => String(route.params.id))
const application = ref<Application | null>(null)
const loading = ref(true)
const error = ref(false)

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    application.value = await api.get<Application>(`/api/v1/applications/${applicationId.value}/`)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-narrow text-center">
    <h1 data-page-heading tabindex="-1" class="page-title">
      {{ t(application?.status === 'RESUBMITTED' ? 'submission.resubmitSuccessTitle' : 'submission.successTitle') }}
    </h1>
    <p v-if="loading" class="mt-7" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-7 text-left">
      {{ t('common.genericError') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>
    <template v-else-if="application">
      <InlineAlert tone="success" class="mt-7 text-left">{{ t('submission.successMessage') }}</InlineAlert>
      <section class="card mt-7" aria-labelledby="reference-heading">
        <h2 id="reference-heading" class="text-xl font-bold">{{ t('submission.referenceLabel') }}</h2>
        <p v-if="application.reference_number" class="mt-3 select-all break-all text-2xl font-black tracking-wide">
          {{ application.reference_number }}
        </p>
        <p v-else class="mt-3">{{ t('submission.referencePending') }}</p>
      </section>
      <RouterLink class="button-primary mt-7" :to="{ name: 'application-tracking', params: { id: applicationId } }">
        {{ t('submission.track') }}
      </RouterLink>
    </template>
  </div>
</template>
