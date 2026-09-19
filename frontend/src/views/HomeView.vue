<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useClassificationStore } from '@/stores/classification'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const classification = useClassificationStore()

async function startApplicantFlow(): Promise<void> {
  if (classification.hasProgress && !window.confirm(t('home.restartWarning'))) return
  classification.reset()
  await router.push({ name: 'classification-step', params: { step: '1' } })
}
</script>

<template>
  <div class="page-narrow">
    <div class="text-center">
      <p class="font-bold uppercase tracking-[0.16em] text-brand-700">{{ t('common.serviceName') }}</p>
      <h1 data-page-heading tabindex="-1" class="page-title mt-3">{{ t('home.title') }}</h1>
      <p class="page-intro mx-auto">{{ t('home.intro') }}</p>
      <p class="mt-6 text-xl font-bold">{{ t('home.instruction') }}</p>
    </div>

    <ol class="mt-8 grid gap-5" :aria-label="t('home.rolesLabel')">
      <li class="card border-2 border-brand-700 bg-brand-50">
        <section aria-labelledby="applicant-role-title">
          <p class="mb-2 inline-flex rounded-full bg-brand-800 px-3 py-1 text-sm font-bold text-white">
            {{ t('common.roles.applicant') }}
          </p>
          <h2 id="applicant-role-title" class="text-2xl font-black">{{ t('home.applicant.title') }}</h2>
          <p class="mt-2 text-slate-700">{{ t('home.applicant.description') }}</p>
          <button type="button" class="button-primary mt-6" @click="startApplicantFlow">
            {{ t('home.applicant.cta') }}
          </button>
          <div class="mt-4">
            <RouterLink
              class="font-bold"
              :to="
                auth.user?.role === 'APPLICANT'
                  ? { name: 'application-list' }
                  : { name: 'login', query: { intent: 'applicant', redirect: '/applications' } }
              "
            >
              {{ t('home.applicant.resume') }}
            </RouterLink>
          </div>
        </section>
      </li>

      <li class="card">
        <section aria-labelledby="local-role-title">
          <h2 id="local-role-title" class="text-2xl font-black">{{ t('home.localOfficer.title') }}</h2>
          <p class="mt-2 text-slate-700">{{ t('home.localOfficer.description') }}</p>
          <RouterLink class="button-secondary mt-6 w-full sm:w-auto" :to="{ name: 'login', query: { intent: 'officer' } }">
            {{ t('home.localOfficer.cta') }}
          </RouterLink>
        </section>
      </li>

      <li class="card">
        <section aria-labelledby="central-role-title">
          <h2 id="central-role-title" class="text-2xl font-black">{{ t('home.centralOfficer.title') }}</h2>
          <p class="mt-2 text-slate-700">{{ t('home.centralOfficer.description') }}</p>
          <RouterLink class="button-secondary mt-6 w-full sm:w-auto" :to="{ name: 'login', query: { intent: 'central' } }">
            {{ t('home.centralOfficer.cta') }}
          </RouterLink>
        </section>
      </li>
    </ol>
    <p class="mt-7 text-center">
      <RouterLink class="font-bold" :to="{ name: 'provider-directory' }">{{ t('home.providersLink') }}</RouterLink>
    </p>
  </div>
</template>
