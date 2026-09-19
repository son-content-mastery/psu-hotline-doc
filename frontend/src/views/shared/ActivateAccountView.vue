<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { ApiError, api } from '@/services/api'

const route = useRoute()
const { t } = useI18n()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const state = ref<'loading' | 'success' | 'error'>('loading')
const email = ref('')
const emailInvalid = ref(false)
const resending = ref(false)
const resent = ref(false)
const resendErrorKey = ref('')

async function confirm(): Promise<void> {
  if (!token.value) {
    state.value = 'error'
    return
  }
  try {
    await api.post('/api/v1/auth/activation/confirm/', { token: token.value })
    state.value = 'success'
  } catch {
    state.value = 'error'
  }
}

async function resend(): Promise<void> {
  emailInvalid.value = !email.value.trim() || !email.value.includes('@')
  resendErrorKey.value = ''
  resent.value = false
  if (emailInvalid.value) {
    await nextTick()
    document.getElementById('activation-email')?.focus()
    return
  }
  resending.value = true
  try {
    await api.post('/api/v1/auth/activation/resend/', { email: email.value.trim() })
    resent.value = true
  } catch (caught) {
    resendErrorKey.value = caught instanceof ApiError && caught.status === 429 ? 'auth.rateLimited' : 'common.genericError'
  } finally {
    resending.value = false
  }
}

onMounted(confirm)
</script>

<template>
  <div class="page-narrow max-w-xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('auth.activation.title') }}</h1>
    <p class="page-intro">{{ t('auth.activation.intro') }}</p>

    <InlineAlert v-if="state === 'loading'" tone="info" live="polite" class="mt-7">
      {{ t('auth.activation.confirming') }}
    </InlineAlert>

    <div v-else-if="state === 'success'" class="mt-7 space-y-5">
      <InlineAlert tone="success" live="polite">
        <h2 class="text-xl font-black">{{ t('auth.activation.successTitle') }}</h2>
        <p class="mt-2">{{ t('auth.activation.successBody') }}</p>
      </InlineAlert>
      <RouterLink class="button-primary" :to="{ name: 'login', query: { notice: 'activated' } }">
        {{ t('auth.activation.signIn') }}
      </RouterLink>
    </div>

    <div v-else class="mt-7">
      <InlineAlert tone="error">
        <h2 class="text-xl font-black">{{ t('auth.activation.invalidTitle') }}</h2>
        <p class="mt-2">{{ t('auth.activation.invalidBody') }}</p>
      </InlineAlert>
      <InlineAlert v-if="resent" tone="success" live="polite" class="mt-5">
        {{ t('auth.activation.resendSuccess') }}
      </InlineAlert>
      <InlineAlert v-if="resendErrorKey" tone="error" class="mt-5">{{ t(resendErrorKey) }}</InlineAlert>
      <form class="card mt-5" novalidate @submit.prevent="resend">
        <label class="field-label" for="activation-email">{{ t('auth.email') }} ({{ t('common.required') }})</label>
        <input
          id="activation-email"
          v-model="email"
          class="field-input"
          type="email"
          autocomplete="email"
          inputmode="email"
          :aria-invalid="emailInvalid"
          :aria-describedby="emailInvalid ? 'activation-email-error' : undefined"
        />
        <p v-if="emailInvalid" id="activation-email-error" class="field-error" role="alert">
          {{ t('auth.registration.emailInvalid') }}
        </p>
        <button type="submit" class="button-primary mt-7" :disabled="resending">
          {{ t(resending ? 'auth.activation.resending' : 'auth.activation.resend') }}
        </button>
      </form>
      <RouterLink class="mt-6 inline-block font-bold" :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</RouterLink>
    </div>
  </div>
</template>
