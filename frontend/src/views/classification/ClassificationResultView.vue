<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import ContactAuthorityPanel from '@/components/ContactAuthorityPanel.vue'
import { useClassificationStore } from '@/stores/classification'
import { formatMoney } from '@/utils/format'

const router = useRouter()
const { locale, t } = useI18n()
const classification = useClassificationStore()
const refreshError = ref(false)
const showContact = ref(false)
const contactPanel = ref<InstanceType<typeof ContactAuthorityPanel> | null>(null)

const result = computed(() => classification.evaluation)
const isSupportedType = computed(() =>
  Boolean(result.value?.property_type?.id) && ['NOT_HOTEL', 'TYPE_1', 'TYPE_2'].includes(result.value?.outcome ?? ''),
)
const needsAuthorityContact = computed(() =>
  ['REQUIRES_LICENSE_REVIEW', 'OUT_OF_SCOPE'].includes(result.value?.outcome ?? ''),
)
const outcomeTitle = computed(() => {
  if (isSupportedType.value && result.value?.outcome !== 'NOT_HOTEL') {
    return result.value?.property_type?.name ?? t('common.statusUnavailable')
  }
  const keys: Record<string, string> = {
    NOT_HOTEL: 'classification.result.outcomes.notHotel.title',
    REQUIRES_LICENSE_REVIEW: 'classification.result.outcomes.review.title',
    OUT_OF_SCOPE: 'classification.result.outcomes.outOfScope.title',
  }
  return t(keys[result.value?.outcome ?? ''] ?? 'classification.result.outcomes.unknown.title')
})
const outcomeExplanation = computed(() => {
  if (result.value?.explanation) return result.value.explanation
  const keys: Record<string, string> = {
    NOT_HOTEL: 'classification.result.outcomes.notHotel.explanation',
    TYPE_1: 'classification.result.outcomes.type1.explanation',
    TYPE_2: 'classification.result.outcomes.type2.explanation',
    REQUIRES_LICENSE_REVIEW: 'classification.result.outcomes.review.explanation',
    OUT_OF_SCOPE: 'classification.result.outcomes.outOfScope.explanation',
  }
  return t(keys[result.value?.outcome ?? ''] ?? 'classification.result.outcomes.unknown.explanation')
})

async function refreshLocalizedResult(): Promise<void> {
  if (!classification.answersComplete) return
  refreshError.value = false
  try {
    await classification.evaluate()
  } catch {
    refreshError.value = true
  }
}

async function restart(): Promise<void> {
  classification.reset()
  await router.push({ name: 'home' })
}

async function openContactGuidance(): Promise<void> {
  showContact.value = true
  await nextTick()
  contactPanel.value?.focusPanel()
}

watch(locale, refreshLocalizedResult)
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('classification.result.pageTitle') }}</h1>

    <InlineAlert v-if="refreshError" tone="warning" class="mt-6">
      {{ t('classification.evaluateError') }}
    </InlineAlert>

    <template v-if="result">
      <section class="card mt-7 border-2 border-brand-700" aria-labelledby="outcome-title">
        <h2 id="outcome-title" class="text-2xl font-black sm:text-3xl">{{ outcomeTitle }}</h2>
        <p class="mt-4 text-lg text-slate-700">{{ outcomeExplanation }}</p>
        <p v-if="result.guidance" class="mt-4 font-semibold">{{ result.guidance }}</p>

        <dl v-if="result.fee && isSupportedType" class="definition-grid mt-6 border-t border-slate-200 pt-5">
          <dt>{{ t('classification.result.fee') }}</dt>
          <dd class="font-extrabold">
            {{ formatMoney(result.fee.amount, result.fee.currency, locale) }}
          </dd>
          <dt>{{ t('classification.result.validityLabel') }}</dt>
          <dd>{{ t('classification.result.validity', { years: result.fee.validity_years }) }}</dd>
        </dl>
      </section>

      <section class="mt-8" aria-labelledby="answer-summary-title">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 id="answer-summary-title" class="text-2xl font-black">{{ t('classification.result.summaryTitle') }}</h2>
          <RouterLink class="font-bold" :to="{ name: 'classification-step', params: { step: '1' } }">
            {{ t('classification.result.editAnswers') }}
          </RouterLink>
        </div>
        <ul class="mt-4 space-y-2 rounded-2xl bg-white p-5" role="list">
          <li>{{ t('classification.result.rooms', { count: classification.rooms }) }}</li>
          <li>{{ t('classification.result.guests', { count: classification.guests }) }}</li>
          <li>
            {{
              t(
                classification.hasRestaurant
                  ? 'classification.result.restaurantYes'
                  : 'classification.result.restaurantNo',
              )
            }}
          </li>
        </ul>
      </section>

      <InlineAlert tone="info" class="mt-7">{{ t('classification.result.advisory') }}</InlineAlert>

      <div class="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <RouterLink
          v-if="isSupportedType"
          class="button-primary"
          :to="{ name: 'public-requirements' }"
        >
          {{ t('classification.result.viewDocuments') }}
        </RouterLink>
        <button
          v-else-if="needsAuthorityContact"
          type="button"
          class="button-primary"
          @click="openContactGuidance"
        >
          {{ t('classification.result.viewGuidance') }}
        </button>
        <button v-else-if="result.outcome === 'NOT_HOTEL'" type="button" class="button-primary" @click="restart">
          {{ t('classification.result.checkAgain') }}
        </button>
        <RouterLink
          v-else
          class="button-primary"
          :to="{ name: 'classification-step', params: { step: '1' } }"
        >
          {{ t('classification.result.editAnswers') }}
        </RouterLink>
        <RouterLink
          v-if="needsAuthorityContact"
          class="button-secondary"
          :to="{ name: 'classification-step', params: { step: '1' } }"
        >
          {{ t('classification.result.editAnswers') }}
        </RouterLink>
      </div>

      <ContactAuthorityPanel v-if="showContact" ref="contactPanel" />
    </template>

    <template v-else>
      <InlineAlert tone="warning" class="mt-6">{{ t('classification.result.missing') }}</InlineAlert>
      <RouterLink class="button-primary mt-6" :to="{ name: 'classification-step', params: { step: '1' } }">
        {{ t('classification.result.checkAgain') }}
      </RouterLink>
    </template>
  </div>
</template>
