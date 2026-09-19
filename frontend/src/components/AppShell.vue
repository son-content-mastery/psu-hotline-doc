<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { setLocale, type AppLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()

const roleLabel = computed(() => {
  const keys = {
    APPLICANT: 'common.roles.applicant',
    LOCAL_OFFICER: 'common.roles.localOfficer',
    CENTRAL_OFFICER: 'common.roles.centralOfficer',
    SUPER_ADMIN: 'common.roles.superAdmin',
  } as const
  return auth.user ? t(keys[auth.user.role]) : ''
})

const identityDetail = computed(() => {
  if (!auth.user) return ''
  return auth.user.local_authority
    ? t('common.roleAndAuthority', { role: roleLabel.value, authority: auth.user.local_authority.name })
    : roleLabel.value
})

function changeLocale(event: Event): void {
  setLocale((event.target as HTMLSelectElement).value as AppLocale)
}

async function signOut(): Promise<void> {
  try {
    await auth.logout()
  } catch {
    // The local identity is cleared by the store even when the server cannot respond.
  }
  await router.push({ name: 'home' })
}

function updateTitle(): void {
  const titleKey = route.meta.titleKey as string | undefined
  document.title = titleKey ? `${t(titleKey)} · ${t('common.serviceName')}` : t('common.serviceName')
}

watch(locale, updateTitle, { immediate: true })
</script>

<template>
  <a class="skip-link" href="#main-content">{{ t('common.skipToContent') }}</a>
  <header class="border-b border-slate-200 bg-white" :aria-label="t('common.serviceName')">
    <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
      <RouterLink class="text-xl font-black tracking-tight text-brand-800 no-underline" :to="{ name: 'home' }">
        {{ t('common.serviceName') }}
      </RouterLink>

      <div class="flex flex-wrap items-center justify-end gap-3">
        <div v-if="auth.user" class="hidden text-right text-sm text-slate-700 sm:block">
          <p class="font-semibold">{{ t('common.signedInAs', { name: auth.user.display_name }) }}</p>
          <p>{{ identityDetail }}</p>
        </div>

        <label class="sr-only" for="language-select">{{ t('common.language') }}</label>
        <select
          id="language-select"
          class="min-h-12 rounded-xl border-slate-400 bg-white py-2 pl-3 pr-9 text-base font-semibold text-slate-900"
          :value="locale"
          @change="changeLocale"
        >
          <option value="th">{{ t('common.thai') }}</option>
          <option value="en">{{ t('common.english') }}</option>
        </select>

        <RouterLink
          v-if="auth.user?.role === 'APPLICANT'"
          class="hidden min-h-12 items-center font-bold sm:inline-flex"
          :to="{ name: 'application-list' }"
        >
          {{ t('application.myApplications') }}
        </RouterLink>

        <button v-if="auth.user" type="button" class="button-secondary min-h-12" @click="signOut">
          {{ t('common.signOut') }}
        </button>
      </div>
      <div v-if="auth.user" class="w-full text-sm text-slate-700 sm:hidden">
        <p class="font-semibold">{{ t('common.signedInAs', { name: auth.user.display_name }) }}</p>
        <p>{{ identityDetail }}</p>
        <RouterLink v-if="auth.user.role === 'APPLICANT'" class="mt-2 inline-block font-bold" :to="{ name: 'application-list' }">
          {{ t('application.myApplications') }}
        </RouterLink>
      </div>
    </div>
  </header>

  <main id="main-content" tabindex="-1" class="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
    <slot />
  </main>
</template>
