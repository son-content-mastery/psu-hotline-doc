<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { rememberActivationRedirect } from '@/services/activationContinuation'
import { ApiError, api } from '@/services/api'

const route = useRoute()
const { t } = useI18n()

const form = reactive({
  email: '',
  password: '',
  passwordConfirmation: '',
  termsAccepted: false,
})
const invalid = reactive({
  email: false,
  password: false,
  passwordConfirmation: false,
  termsAccepted: false,
})
const backendErrors = ref<Record<string, string[]>>({})
const errorKey = ref('')
const submitting = ref(false)
const submitted = ref(false)
const showPassword = ref(false)
const resending = ref(false)
const resent = ref(false)

function loginTarget() {
  return {
    name: 'login',
    query: typeof route.query.redirect === 'string' ? { redirect: route.query.redirect } : undefined,
  }
}

async function focusFirstError(): Promise<void> {
  await nextTick()
  document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

function validate(): boolean {
  invalid.email = !form.email.trim() || !form.email.includes('@')
  invalid.password = !form.password
  invalid.passwordConfirmation = !form.passwordConfirmation || form.password !== form.passwordConfirmation
  invalid.termsAccepted = !form.termsAccepted
  return !Object.values(invalid).some(Boolean)
}

async function submit(): Promise<void> {
  errorKey.value = ''
  backendErrors.value = {}
  resent.value = false
  if (!validate()) {
    await focusFirstError()
    return
  }
  submitting.value = true
  try {
    await api.post('/api/v1/auth/register/', {
      email: form.email.trim(),
      password: form.password,
      password_confirmation: form.passwordConfirmation,
      terms_accepted: form.termsAccepted,
    })
    rememberActivationRedirect(route.query.redirect)
    submitted.value = true
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 429) {
      errorKey.value = 'auth.rateLimited'
    } else if (caught instanceof ApiError && Object.keys(caught.fields).length) {
      backendErrors.value = caught.fields
      errorKey.value = 'auth.registration.validationSummary'
      await focusFirstError()
    } else {
      errorKey.value = 'common.genericError'
    }
  } finally {
    submitting.value = false
  }
}

async function resend(): Promise<void> {
  resending.value = true
  errorKey.value = ''
  resent.value = false
  try {
    await api.post('/api/v1/auth/activation/resend/', { email: form.email.trim() })
    resent.value = true
  } catch (caught) {
    errorKey.value = caught instanceof ApiError && caught.status === 429 ? 'auth.rateLimited' : 'common.genericError'
  } finally {
    resending.value = false
  }
}
</script>

<template>
  <div class="page-narrow max-w-xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('auth.registration.title') }}</h1>
    <p class="page-intro">{{ t('auth.registration.intro') }}</p>

    <InlineAlert v-if="errorKey" tone="error" class="mt-6">
      <p>{{ t(errorKey) }}</p>
    </InlineAlert>

    <div v-if="submitted" class="mt-7 space-y-5">
      <InlineAlert tone="success" live="polite">
        <h2 class="text-xl font-black">{{ t('auth.registration.successTitle') }}</h2>
        <p class="mt-2">{{ t('auth.registration.successBody') }}</p>
      </InlineAlert>
      <InlineAlert v-if="resent" tone="info" live="polite">{{ t('auth.activation.resendSuccess') }}</InlineAlert>
      <div class="flex flex-col gap-3 sm:flex-row">
        <RouterLink class="button-primary" :to="loginTarget()">{{ t('auth.registration.goToLogin') }}</RouterLink>
        <button type="button" class="button-secondary" :disabled="resending" @click="resend">
          {{ t(resending ? 'auth.activation.resending' : 'auth.activation.resend') }}
        </button>
      </div>
    </div>

    <form v-else class="card mt-7" novalidate @submit.prevent="submit">
      <div>
        <label class="field-label" for="register-email">{{ t('auth.email') }} ({{ t('common.required') }})</label>
        <input
          id="register-email"
          v-model="form.email"
          class="field-input"
          type="email"
          autocomplete="email"
          inputmode="email"
          :aria-invalid="invalid.email || Boolean(backendErrors.email)"
          :aria-describedby="invalid.email || backendErrors.email ? 'register-email-error' : undefined"
        />
        <p v-if="invalid.email || backendErrors.email" id="register-email-error" class="field-error" role="alert">
          {{ t('auth.registration.emailInvalid') }}
        </p>
      </div>

      <div class="mt-6">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="field-label mb-0" for="register-password">
            {{ t('auth.password') }} ({{ t('common.required') }})
          </label>
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
          id="register-password"
          v-model="form.password"
          class="field-input mt-2"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          :aria-invalid="invalid.password || Boolean(backendErrors.password)"
          :aria-describedby="backendErrors.password ? 'registration-password-help registration-password-error' : 'registration-password-help'"
        />
        <p id="registration-password-help" class="mt-2 text-slate-700">{{ t('auth.registration.passwordHelp') }}</p>
        <p v-if="backendErrors.password" id="registration-password-error" class="field-error" role="alert">
          {{ t('auth.passwordRules') }}
        </p>
      </div>

      <div class="mt-6">
        <label class="field-label" for="register-password-confirmation">
          {{ t('auth.registration.confirmPassword') }} ({{ t('common.required') }})
        </label>
        <input
          id="register-password-confirmation"
          v-model="form.passwordConfirmation"
          class="field-input"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          :aria-invalid="invalid.passwordConfirmation || Boolean(backendErrors.password_confirmation)"
          :aria-describedby="invalid.passwordConfirmation || backendErrors.password_confirmation ? 'register-password-confirmation-error' : undefined"
        />
        <p
          v-if="invalid.passwordConfirmation || backendErrors.password_confirmation"
          id="register-password-confirmation-error"
          class="field-error"
          role="alert"
        >
          {{ t('auth.registration.passwordMismatch') }}
        </p>
      </div>

      <div class="mt-6 rounded-2xl border border-slate-300 bg-slate-50 p-4">
        <label class="flex items-start gap-3" for="terms-accepted">
          <input
            id="terms-accepted"
            v-model="form.termsAccepted"
            class="mt-1 h-6 w-6 shrink-0 rounded border-slate-500 text-brand-700"
            type="checkbox"
            :aria-invalid="invalid.termsAccepted || Boolean(backendErrors.terms_accepted)"
            :aria-describedby="invalid.termsAccepted || backendErrors.terms_accepted ? 'terms-help terms-error' : 'terms-help'"
          />
          <span class="font-semibold">{{ t('auth.registration.termsLabel') }}</span>
        </label>
        <p id="terms-help" class="ml-9 mt-2 text-slate-700">{{ t('auth.registration.termsHelp') }}</p>
        <p v-if="invalid.termsAccepted || backendErrors.terms_accepted" id="terms-error" class="field-error ml-9" role="alert">
          {{ t('auth.registration.termsRequired') }}
        </p>
      </div>

      <button type="submit" class="button-primary mt-8" :disabled="submitting">
        {{ t(submitting ? 'auth.registration.submitting' : 'auth.registration.submit') }}
      </button>
      <p class="mt-5">
        {{ t('auth.registration.haveAccount') }}
        <RouterLink class="font-bold" :to="loginTarget()">{{ t('auth.backToLogin') }}</RouterLink>
      </p>
    </form>
  </div>
</template>
