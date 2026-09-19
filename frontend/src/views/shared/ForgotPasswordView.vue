<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { ApiError, api } from '@/services/api'

const { t } = useI18n()
const email = ref('')
const invalid = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const errorKey = ref('')

async function submit(): Promise<void> {
  invalid.value = !email.value.trim()
  errorKey.value = ''
  if (invalid.value) {
    await nextTick()
    document.getElementById('reset-email')?.focus()
    return
  }
  submitting.value = true
  try {
    await api.post('/api/v1/auth/password-reset/', { email: email.value.trim() })
    submitted.value = true
  } catch (caught) {
    errorKey.value = caught instanceof ApiError && caught.status === 429 ? 'auth.rateLimited' : 'common.genericError'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-narrow max-w-xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('auth.resetRequestTitle') }}</h1>
    <p class="page-intro">{{ t('auth.resetRequestIntro') }}</p>

    <InlineAlert v-if="submitted" tone="success" live="polite" class="mt-7">
      {{ t('auth.resetRequestSuccess') }}
    </InlineAlert>
    <InlineAlert v-if="errorKey" tone="error" class="mt-7">{{ t(errorKey) }}</InlineAlert>

    <form v-if="!submitted" class="card mt-7" novalidate @submit.prevent="submit">
      <label class="field-label" for="reset-email">{{ t('auth.email') }} ({{ t('common.required') }})</label>
      <input
        id="reset-email"
        v-model="email"
        type="email"
        autocomplete="email"
        inputmode="email"
        class="field-input"
        :aria-invalid="invalid"
        :aria-describedby="invalid ? 'reset-email-error' : undefined"
      />
      <p v-if="invalid" id="reset-email-error" class="field-error" role="alert">{{ t('auth.emailRequired') }}</p>
      <button type="submit" class="button-primary mt-7" :disabled="submitting">
        {{ t(submitting ? 'auth.resetRequestSubmitting' : 'auth.resetRequestSubmit') }}
      </button>
    </form>

    <RouterLink class="mt-6 inline-block font-bold" :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</RouterLink>
  </div>
</template>
