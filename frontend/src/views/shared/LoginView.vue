<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { api, ApiError } from '@/services/api'
import { safeRelativeRedirect } from '@/services/sessionExpiry'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

const form = reactive({ email: '', password: '' })
const fieldErrors = reactive({ email: false, password: false })
const submitErrorKey = ref('')
const submitting = ref(false)
const showPassword = ref(false)
const activationResent = ref(false)
const resendingActivation = ref(false)

const intent = computed(() => (typeof route.query.intent === 'string' ? route.query.intent : 'applicant'))
const introKey = computed(() => {
  if (intent.value === 'officer') return 'auth.officerIntro'
  if (intent.value === 'central') return 'auth.centralIntro'
  return 'auth.applicantIntro'
})

const expectedRole = computed<Role>(() => {
  if (intent.value === 'officer') return 'LOCAL_OFFICER'
  if (intent.value === 'central') return 'CENTRAL_OFFICER'
  return 'APPLICANT'
})

function safeRedirect(): string {
  const fallback =
    expectedRole.value === 'LOCAL_OFFICER'
      ? '/officer/applications'
      : expectedRole.value === 'CENTRAL_OFFICER'
        ? '/central/overview'
        : '/applications'
  return safeRelativeRedirect(route.query.redirect, fallback)
}

function validate(): boolean {
  fieldErrors.email = !form.email.trim()
  fieldErrors.password = !form.password
  if (!fieldErrors.email && !fieldErrors.password) return true
  void nextTick(() => {
    const target = document.querySelector<HTMLElement>('[aria-invalid="true"]')
    target?.focus()
  })
  return false
}

async function submit(): Promise<void> {
  submitErrorKey.value = ''
  activationResent.value = false
  if (!validate()) return
  submitting.value = true
  try {
    const user = await auth.login(form.email.trim(), form.password)
    if (user.role !== expectedRole.value) {
      await auth.logout()
      submitErrorKey.value = 'auth.roleMismatch'
      return
    }
    await router.replace(safeRedirect())
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === 'EMAIL_NOT_VERIFIED') submitErrorKey.value = 'auth.activationRequired'
    else if (caught instanceof ApiError && caught.status === 429) submitErrorKey.value = 'auth.rateLimited'
    else if (caught instanceof ApiError && caught.status === 401) submitErrorKey.value = 'auth.invalid'
    else submitErrorKey.value = 'common.genericError'
  } finally {
    submitting.value = false
  }
}

async function resendActivation(): Promise<void> {
  resendingActivation.value = true
  activationResent.value = false
  try {
    await api.post('/api/v1/auth/activation/resend/', { email: form.email.trim() })
    activationResent.value = true
    submitErrorKey.value = ''
  } catch (caught) {
    submitErrorKey.value = caught instanceof ApiError && caught.status === 429 ? 'auth.rateLimited' : 'common.genericError'
  } finally {
    resendingActivation.value = false
  }
}
</script>

<template>
  <div class="page-narrow max-w-xl">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('auth.title') }}</h1>
    <p class="page-intro">{{ t(introKey) }}</p>

    <InlineAlert v-if="route.query.notice === 'expired'" tone="warning" live="polite" class="mt-6">
      {{ t('auth.sessionExpired') }}
    </InlineAlert>
    <InlineAlert v-if="route.query.notice === 'activated'" tone="success" live="polite" class="mt-6">
      {{ t('auth.accountActivated') }}
    </InlineAlert>
    <InlineAlert v-if="submitErrorKey" tone="error" class="mt-6">{{ t(submitErrorKey) }}</InlineAlert>
    <InlineAlert v-if="activationResent" tone="success" live="polite" class="mt-6">
      {{ t('auth.activation.resendSuccess') }}
    </InlineAlert>

    <form class="card mt-7" novalidate @submit.prevent="submit">
      <div>
        <label class="field-label" for="email">{{ t('auth.email') }} ({{ t('common.required') }})</label>
        <input
          id="email"
          v-model="form.email"
          class="field-input"
          type="email"
          autocomplete="username"
          inputmode="email"
          :aria-invalid="Boolean(fieldErrors.email)"
          :aria-describedby="fieldErrors.email ? 'email-error' : undefined"
        />
        <p v-if="fieldErrors.email" id="email-error" class="field-error" role="alert">{{ t('auth.emailRequired') }}</p>
      </div>

      <div class="mt-6">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <label class="field-label mb-0" for="password">{{ t('auth.password') }} ({{ t('common.required') }})</label>
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
          id="password"
          v-model="form.password"
          class="field-input mt-2"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          :aria-invalid="Boolean(fieldErrors.password)"
          :aria-describedby="fieldErrors.password ? 'password-error' : undefined"
        />
        <p v-if="fieldErrors.password" id="password-error" class="field-error" role="alert">{{ t('auth.passwordRequired') }}</p>
      </div>

      <button type="submit" class="button-primary mt-8" :disabled="submitting">
        {{ t(submitting ? 'auth.submitting' : 'auth.submit') }}
      </button>
      <RouterLink class="mt-5 inline-block font-bold" :to="{ name: 'forgot-password' }">
        {{ t('auth.forgotPassword') }}
      </RouterLink>
      <button
        v-if="submitErrorKey === 'auth.activationRequired'"
        type="button"
        class="button-secondary mt-5 w-full sm:w-auto"
        :disabled="resendingActivation"
        @click="resendActivation"
      >
        {{ t(resendingActivation ? 'auth.activation.resending' : 'auth.activation.resend') }}
      </button>
      <p v-if="intent === 'applicant'" class="mt-6 border-t border-slate-200 pt-5">
        {{ t('auth.noAccount') }}
        <RouterLink
          class="font-bold"
          :to="{ name: 'register', query: typeof route.query.redirect === 'string' ? { redirect: route.query.redirect } : undefined }"
        >
          {{ t('auth.createAccount') }}
        </RouterLink>
      </p>
    </form>
  </div>
</template>
