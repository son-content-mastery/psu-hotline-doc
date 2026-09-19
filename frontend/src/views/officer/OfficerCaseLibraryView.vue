<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { CaseLibraryFaq, CaseLibraryResponse, CaseStudy, Paginated, PropertyType } from '@/types/api'
import { formatDate } from '@/utils/format'

const { locale, t } = useI18n()
const query = ref('')
const decision = ref('')
const propertyType = ref('')
const cases = ref<CaseStudy[]>([])
const faqs = ref<CaseLibraryFaq[]>([])
const propertyTypes = ref<PropertyType[]>([])
const count = ref(0)
const nextPage = ref<string | null>(null)
const previousPage = ref<string | null>(null)
const loading = ref(true)
const error = ref(false)

async function load(url?: string): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const params = new URLSearchParams()
    if (query.value.trim()) params.set('q', query.value.trim())
    if (decision.value) params.set('decision', decision.value)
    if (propertyType.value) params.set('property_type', propertyType.value)
    const response = await api.get<CaseLibraryResponse>(url ?? `/api/v1/officer/case-library/?${params.toString()}`)
    cases.value = response.results
    faqs.value = response.faqs
    count.value = response.count
    nextPage.value = response.next
    previousPage.value = response.previous
  } catch {
    error.value = true
    cases.value = []
    faqs.value = []
  } finally {
    loading.value = false
  }
}

async function loadPropertyTypes(): Promise<void> {
  try {
    propertyTypes.value = (await api.get<Paginated<PropertyType>>('/api/v1/property-types/')).results
  } catch {
    propertyTypes.value = []
  }
}

function resetFilters(): void {
  query.value = ''
  decision.value = ''
  propertyType.value = ''
  void load()
}

watch(locale, () => Promise.all([load(), loadPropertyTypes()]))
onMounted(() => Promise.all([load(), loadPropertyTypes()]))
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'officer-queue' }">{{ t('caseLibrary.backToQueue') }}</RouterLink>
    <div class="mt-5 max-w-3xl">
      <p class="eyebrow">{{ t('caseLibrary.eyebrow') }}</p>
      <h1 data-page-heading tabindex="-1" class="page-title">{{ t('caseLibrary.title') }}</h1>
      <p class="page-intro">{{ t('caseLibrary.intro') }}</p>
    </div>

    <InlineAlert tone="info" class="mt-7 max-w-4xl">
      {{ t('caseLibrary.advisory') }}
    </InlineAlert>

    <form class="mt-7 grid gap-4 rounded-3xl border border-slate-200 bg-white p-5 md:grid-cols-4" @submit.prevent="load()">
      <div class="md:col-span-2">
        <label for="case-query" class="field-label">{{ t('caseLibrary.searchLabel') }}</label>
        <input id="case-query" v-model="query" class="field-input" maxlength="100" :placeholder="t('caseLibrary.searchPlaceholder')" />
      </div>
      <div>
        <label for="case-decision" class="field-label">{{ t('caseLibrary.decisionLabel') }}</label>
        <select id="case-decision" v-model="decision" class="field-input">
          <option value="">{{ t('caseLibrary.allDecisions') }}</option>
          <option value="APPROVED">{{ t('caseLibrary.approved') }}</option>
          <option value="REJECTED">{{ t('caseLibrary.rejected') }}</option>
        </select>
      </div>
      <div>
        <label for="case-type" class="field-label">{{ t('caseLibrary.typeLabel') }}</label>
        <select id="case-type" v-model="propertyType" class="field-input">
          <option value="">{{ t('caseLibrary.allTypes') }}</option>
          <option v-for="item in propertyTypes" :key="item.code" :value="item.code">{{ item.name }}</option>
        </select>
      </div>
      <div class="flex flex-wrap gap-3 md:col-span-4">
        <button type="submit" class="button-primary" :disabled="loading">{{ t('caseLibrary.search') }}</button>
        <button type="button" class="button-secondary" :disabled="loading" @click="resetFilters">{{ t('caseLibrary.reset') }}</button>
      </div>
    </form>

    <p v-if="loading" class="mt-8" aria-live="polite">{{ t('caseLibrary.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-8 max-w-3xl">
      {{ t('caseLibrary.error') }}
      <button type="button" class="ml-2 font-bold underline" @click="load()">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else>
      <section class="mt-9" aria-labelledby="case-results-title">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="case-results-title" class="section-title">{{ t('caseLibrary.resultsTitle') }}</h2>
            <p class="mt-1 text-slate-700">{{ t('caseLibrary.resultCount', { count }) }}</p>
          </div>
        </div>
        <InlineAlert v-if="cases.length === 0" tone="info" class="mt-5 max-w-3xl">{{ t('caseLibrary.empty') }}</InlineAlert>
        <ul v-else class="mt-5 grid gap-5 lg:grid-cols-2" role="list">
          <li v-for="item in cases" :key="item.case_reference" class="card">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="text-sm font-bold text-slate-600">{{ item.case_reference }}</p>
                <h3 class="mt-1 text-xl font-black">{{ item.property_type.name }}</h3>
              </div>
              <span :class="['rounded-full px-3 py-1 text-sm font-bold', item.decision === 'APPROVED' ? 'bg-emerald-100 text-emerald-950' : 'bg-red-100 text-red-950']">
                {{ t(item.decision === 'APPROVED' ? 'caseLibrary.approved' : 'caseLibrary.rejected') }}
              </span>
            </div>
            <dl class="definition-grid mt-5">
              <dt>{{ t('caseLibrary.roomsGuests') }}</dt>
              <dd>{{ t('caseLibrary.roomsGuestsValue', { rooms: item.classification.rooms, guests: item.classification.guests }) }}</dd>
              <dt>{{ t('caseLibrary.restaurant') }}</dt>
              <dd>{{ t(item.classification.has_restaurant ? 'common.yes' : 'common.no') }}</dd>
              <dt>{{ t('caseLibrary.revisionRounds') }}</dt>
              <dd>{{ item.revision_rounds }}</dd>
              <dt>{{ t('caseLibrary.processingDays') }}</dt>
              <dd>{{ item.processing_days ?? t('caseLibrary.notAvailable') }}</dd>
              <dt>{{ t('caseLibrary.reviewedVersions') }}</dt>
              <dd>{{ item.documents.versions_reviewed }}</dd>
              <dt>{{ t('caseLibrary.decidedAt') }}</dt>
              <dd>{{ formatDate(item.decided_at, locale) }}</dd>
            </dl>
          </li>
        </ul>
        <nav v-if="previousPage || nextPage" class="mt-6 flex items-center justify-between gap-3" :aria-label="t('common.pagination')">
          <button type="button" class="button-secondary" :disabled="!previousPage || loading" @click="previousPage && load(previousPage)">{{ t('common.actions.back') }}</button>
          <button type="button" class="button-secondary" :disabled="!nextPage || loading" @click="nextPage && load(nextPage)">{{ t('common.actions.next') }}</button>
        </nav>
      </section>

      <section class="mt-12 max-w-4xl" aria-labelledby="case-faq-title">
        <h2 id="case-faq-title" class="section-title">{{ t('caseLibrary.faqTitle') }}</h2>
        <p class="mt-2 text-slate-700">{{ t('caseLibrary.faqIntro') }}</p>
        <InlineAlert v-if="faqs.length === 0" tone="info" class="mt-5">{{ t('caseLibrary.noFaq') }}</InlineAlert>
        <div v-else class="mt-5 space-y-3">
          <details v-for="article in faqs" :key="article.slug" class="rounded-2xl border border-slate-200 bg-white p-5">
            <summary class="cursor-pointer font-bold">{{ article.question }}</summary>
            <p class="mt-4 whitespace-pre-line text-slate-700">{{ article.answer }}</p>
          </details>
        </div>
      </section>
    </template>
  </div>
</template>
