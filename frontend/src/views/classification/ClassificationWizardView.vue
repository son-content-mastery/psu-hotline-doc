<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import InlineAlert from '@/components/InlineAlert.vue'
import { useClassificationStore } from '@/stores/classification'
import { ApiError } from '@/services/api'
import { isPositiveWholeNumber } from '@/utils/domain'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const classification = useClassificationStore()
const errorKey = ref('')
const loadError = ref(false)

const step = computed(() => Number(route.params.step))
const currentQuestion = computed(() => classification.questions[step.value - 1])
const questionLabel = computed(() => {
  if (currentQuestion.value?.label) return currentQuestion.value.label
  if (step.value === 1) return t('classification.roomsLabelFallback')
  if (step.value === 2) return t('classification.guestsLabelFallback')
  return t('classification.restaurantLegendFallback')
})

async function loadQuestions(force = false): Promise<void> {
  loadError.value = false
  try {
    await classification.loadQuestions(force)
  } catch {
    loadError.value = true
  }
}

function focusError(): void {
  void nextTick(() => document.querySelector<HTMLElement>('[data-validation-error]')?.focus())
}

async function continueFlow(): Promise<void> {
  errorKey.value = ''
  if (step.value === 1 && !isPositiveWholeNumber(classification.rooms)) {
    errorKey.value = 'classification.positiveIntegerError'
  } else if (step.value === 2 && !isPositiveWholeNumber(classification.guests)) {
    errorKey.value = 'classification.positiveIntegerError'
  } else if (step.value === 3 && classification.hasRestaurant === null) {
    errorKey.value = 'classification.restaurantError'
  }

  if (errorKey.value) {
    focusError()
    return
  }

  if (step.value < 3) {
    await router.push({ name: 'classification-step', params: { step: String(step.value + 1) } })
    return
  }

  try {
    await classification.evaluate()
    await router.push({ name: 'classification-result' })
  } catch (caught) {
    errorKey.value =
      caught instanceof ApiError && caught.status === 400
        ? 'classification.positiveIntegerError'
        : 'classification.evaluateError'
    focusError()
  }
}

async function goBack(): Promise<void> {
  if (step.value > 1) {
    await router.push({ name: 'classification-step', params: { step: String(step.value - 1) } })
  }
}

watch(
  step,
  (value) => {
    classification.setStep(value)
    errorKey.value = ''
  },
  { immediate: true },
)
watch(locale, () => loadQuestions(true))
onMounted(() => loadQuestions())
</script>

<template>
  <div class="page-narrow">
    <p class="font-bold text-brand-800">{{ t('classification.step', { current: step, total: 3 }) }}</p>
    <progress
      class="mt-3 h-4 w-full overflow-hidden rounded-full accent-brand-700"
      :value="step"
      max="3"
      :aria-label="t('classification.progressLabel')"
    />

    <InlineAlert v-if="route.query.notice === 'missing'" tone="warning" class="mt-6">
      {{ t('classification.result.missing') }}
    </InlineAlert>

    <div v-if="classification.loadingQuestions" class="mt-8" aria-live="polite">
      <h1 data-page-heading tabindex="-1" class="page-title">{{ t('classification.pageTitle') }}</h1>
      <p class="mt-4">{{ t('classification.questionsLoading') }}</p>
    </div>

    <div v-else-if="loadError" class="mt-8">
      <h1 data-page-heading tabindex="-1" class="page-title">{{ t('classification.pageTitle') }}</h1>
      <InlineAlert tone="error" class="mt-6">{{ t('classification.questionsError') }}</InlineAlert>
      <button type="button" class="button-primary mt-6" @click="loadQuestions(true)">
        {{ t('common.actions.retry') }}
      </button>
    </div>

    <form v-else class="mt-8" novalidate @submit.prevent="continueFlow">
      <div v-if="step === 3">
        <h1 id="restaurant-question" data-page-heading tabindex="-1" class="page-title">{{ questionLabel }}</h1>
        <p class="mt-3 text-slate-600">{{ t('classification.requiredHint') }}</p>
        <fieldset
          class="mt-6"
          aria-labelledby="restaurant-question"
          :aria-describedby="errorKey ? 'answer-error' : undefined"
          :aria-invalid="Boolean(errorKey)"
        >
          <legend class="sr-only">{{ questionLabel }}</legend>
          <div class="grid gap-4 sm:grid-cols-2">
            <label
              class="flex min-h-16 cursor-pointer items-center gap-4 rounded-2xl border-2 border-slate-400 bg-white p-4 has-[:checked]:border-brand-700 has-[:checked]:bg-brand-50"
            >
              <input
                type="radio"
                name="has_restaurant"
                :checked="classification.hasRestaurant === true"
                class="h-6 w-6 text-brand-700 focus:ring-brand-700"
                :aria-describedby="errorKey ? 'answer-error' : undefined"
                @change="classification.updateRestaurant(true); errorKey = ''"
              />
              <span class="text-lg font-bold">{{ t('common.yes') }}</span>
            </label>
            <label
              class="flex min-h-16 cursor-pointer items-center gap-4 rounded-2xl border-2 border-slate-400 bg-white p-4 has-[:checked]:border-brand-700 has-[:checked]:bg-brand-50"
            >
              <input
                type="radio"
                name="has_restaurant"
                :checked="classification.hasRestaurant === false"
                class="h-6 w-6 text-brand-700 focus:ring-brand-700"
                :aria-describedby="errorKey ? 'answer-error' : undefined"
                @change="classification.updateRestaurant(false); errorKey = ''"
              />
              <span class="text-lg font-bold">{{ t('common.no') }}</span>
            </label>
          </div>
        </fieldset>
      </div>

      <div v-else>
        <h1 data-page-heading tabindex="-1" class="page-title">{{ questionLabel }}</h1>
        <label class="field-label mt-7" :for="step === 1 ? 'rooms' : 'guests'">
          {{ questionLabel }} <span class="text-base font-normal">({{ t('common.required') }})</span>
        </label>
        <input
          v-if="step === 1"
          id="rooms"
          class="field-input max-w-xs"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          :value="classification.rooms"
          :aria-invalid="Boolean(errorKey)"
          :aria-describedby="errorKey ? 'answer-error rooms-help' : 'rooms-help'"
          @input="classification.updateRooms(($event.target as HTMLInputElement).value); errorKey = ''"
        />
        <input
          v-else
          id="guests"
          class="field-input max-w-xs"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          :value="classification.guests"
          :aria-invalid="Boolean(errorKey)"
          :aria-describedby="errorKey ? 'answer-error guests-help' : 'guests-help'"
          @input="classification.updateGuests(($event.target as HTMLInputElement).value); errorKey = ''"
        />
        <p :id="step === 1 ? 'rooms-help' : 'guests-help'" class="mt-3 text-slate-600">
          {{ t(step === 1 ? 'classification.roomsHelper' : 'classification.guestsHelper') }}
        </p>
      </div>

      <p
        v-if="errorKey"
        id="answer-error"
        data-validation-error
        tabindex="-1"
        class="field-error"
        role="alert"
      >
        {{ t(errorKey) }}
      </p>

      <p v-if="classification.evaluating" class="mt-6 font-semibold" aria-live="polite">
        {{ t('classification.evaluating') }}
      </p>

      <div class="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button v-if="step > 1" type="button" class="button-secondary" @click="goBack">
          {{ t('common.actions.back') }}
        </button>
        <span v-else aria-hidden="true" />
        <button type="submit" class="button-primary" :disabled="classification.evaluating">
          {{ t(step === 3 ? 'classification.seeResult' : 'common.actions.next') }}
        </button>
      </div>
    </form>
  </div>
</template>
