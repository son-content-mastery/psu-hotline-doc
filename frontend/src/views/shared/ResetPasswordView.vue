<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { ApiError, api } from '@/services/api'

const route = useRoute()
const { t } = useI18n()
const password = ref('')
const confirmation = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const errorKey = ref('')
const fieldErrors = ref<string[]>([])

const uid = computed(() => (typeof route.query.uid === 'string' ? route.query.uid : ''))
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const hasResetLink = computed(() => Boolean(uid.value && token.value))

async function submit(): Promise<void> {
  errorKey.value = ''
  fieldErrors.value = []
  if (!password.value) errorKey.value = 'auth.passwordRequired'
  else if (password.value !== confirmation.value) errorKey.value = 'auth.passwordMismatch'
  if (errorKey.value) {
    await nextTick()
    document.getElementById('new-password')?.focus()
    return
  }
  submitting.value = true
  try {
    await api.post('/api/v1/auth/password-reset/confirm/', {
      uid: uid.value,
      token: token.value,
      new_password: password.value,
    })
    submitted.value = true
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === 'PASSWORD_RESET_INVALID') {
      errorKey.value = 'auth.resetInvalid'
    } else if (caught instanceof ApiError && caught.fields.new_password) {
      fieldErrors.value = caught.fields.new_password
      errorKey.value = 'auth.passwordRules'
    } else {
      errorKey.value = 'common.genericError'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-narrow max-w-xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('auth.resetTitle') }}</h1>
    <p class="page-intro">{{ t('auth.resetIntro') }}</p>

    <InlineAlert v-if="!hasResetLink" tone="error" class="mt-7">{{ t('auth.resetInvalid') }}</InlineAlert>
    <InlineAlert v-else-if="submitted" tone="success" live="polite" class="mt-7">
      {{ t('auth.resetSuccess') }}
    </InlineAlert>
    <InlineAlert v-if="errorKey" tone="error" class="mt-7">
      <p>{{ t(errorKey) }}</p>
      <ul v-if="fieldErrors.length" class="mt-2 list-disc pl-6">
        <li v-for="message in fieldErrors" :key="message">{{ message }}</li>
      </ul>
    </InlineAlert>

    <form v-if="hasResetLink && !submitted" class="card mt-7" novalidate @submit.prevent="submit">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <label class="field-label mb-0" for="new-password">{{ t('auth.newPassword') }}</label>
        <button
          type="button"
          class="min-h-11 rounded-lg px-2 font-bold text-brand-700 underline"
          :aria-pressed="showPassword"
          @click="showPassword = !showPassword"
        >
          {{ t(showPassword ? 'auth.hidePassword' : 'auth.showPassword') }}
        </button>
      </div>
      <input
        id="new-password"
        v-model="password"
        class="field-input mt-2"
        :type="showPassword ? 'text' : 'password'"
        autocomplete="new-password"
      />
      <label class="field-label mt-6" for="confirm-password">{{ t('auth.confirmPassword') }}</label>
      <input
        id="confirm-password"
        v-model="confirmation"
        class="field-input"
        :type="showPassword ? 'text' : 'password'"
        autocomplete="new-password"
      />
      <button type="submit" class="button-primary mt-7" :disabled="submitting">
        {{ t(submitting ? 'auth.resetSubmitting' : 'auth.resetSubmit') }}
      </button>
    </form>

    <RouterLink class="mt-6 inline-block font-bold" :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</RouterLink>
  </div>
</template>
