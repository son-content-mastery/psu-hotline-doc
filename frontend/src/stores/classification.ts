import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/services/api'
import type {
  ClassificationAnswersPayload,
  ClassificationEvaluation,
  ClassificationQuestion,
  ClassificationQuestionsResponse,
} from '@/types/api'
import { isPositiveWholeNumber } from '@/utils/domain'

export const CLASSIFICATION_SESSION_KEY = 'hotline-doc:classification'

interface PersistedClassification {
  rooms: string
  guests: string
  hasRestaurant: boolean | null
  currentStep: number
  questionsVersion: string | null
  evaluation: ClassificationEvaluation | null
}

function loadPersisted(): PersistedClassification {
  const empty: PersistedClassification = {
    rooms: '',
    guests: '',
    hasRestaurant: null,
    currentStep: 1,
    questionsVersion: null,
    evaluation: null,
  }

  try {
    const raw = window.sessionStorage.getItem(CLASSIFICATION_SESSION_KEY)
    if (!raw) return empty
    const parsed = JSON.parse(raw) as Partial<PersistedClassification>
    return {
      rooms: typeof parsed.rooms === 'string' ? parsed.rooms : '',
      guests: typeof parsed.guests === 'string' ? parsed.guests : '',
      hasRestaurant: typeof parsed.hasRestaurant === 'boolean' ? parsed.hasRestaurant : null,
      currentStep:
        typeof parsed.currentStep === 'number' && parsed.currentStep >= 1 && parsed.currentStep <= 3
          ? parsed.currentStep
          : 1,
      questionsVersion: typeof parsed.questionsVersion === 'string' ? parsed.questionsVersion : null,
      evaluation: parsed.evaluation?.outcome ? parsed.evaluation : null,
    }
  } catch {
    window.sessionStorage.removeItem(CLASSIFICATION_SESSION_KEY)
    return empty
  }
}

export const useClassificationStore = defineStore('classification', () => {
  const initial = loadPersisted()
  const rooms = ref(initial.rooms)
  const guests = ref(initial.guests)
  const hasRestaurant = ref<boolean | null>(initial.hasRestaurant)
  const currentStep = ref(initial.currentStep)
  const questionsVersion = ref<string | null>(initial.questionsVersion)
  const questions = ref<ClassificationQuestion[]>([])
  const evaluation = ref<ClassificationEvaluation | null>(initial.evaluation)
  const loadingQuestions = ref(false)
  const evaluating = ref(false)

  const hasProgress = computed(
    () => rooms.value !== '' || guests.value !== '' || hasRestaurant.value !== null || evaluation.value !== null,
  )
  const answersComplete = computed(
    () =>
      isPositiveWholeNumber(rooms.value) &&
      isPositiveWholeNumber(guests.value) &&
      hasRestaurant.value !== null,
  )
  const canCreateApplication = computed(
    () =>
      answersComplete.value &&
      Boolean(evaluation.value?.property_type?.id) &&
      ['NOT_HOTEL', 'TYPE_1', 'TYPE_2'].includes(evaluation.value?.outcome ?? ''),
  )

  function persist(): void {
    const state: PersistedClassification = {
      rooms: rooms.value,
      guests: guests.value,
      hasRestaurant: hasRestaurant.value,
      currentStep: currentStep.value,
      questionsVersion: questionsVersion.value,
      evaluation: evaluation.value,
    }
    window.sessionStorage.setItem(CLASSIFICATION_SESSION_KEY, JSON.stringify(state))
  }

  function setStep(step: number): void {
    currentStep.value = Math.min(3, Math.max(1, step))
    persist()
  }

  function updateRooms(value: string): void {
    rooms.value = value
    evaluation.value = null
    persist()
  }

  function updateGuests(value: string): void {
    guests.value = value
    evaluation.value = null
    persist()
  }

  function updateRestaurant(value: boolean): void {
    hasRestaurant.value = value
    evaluation.value = null
    persist()
  }

  function answerPayload(): ClassificationAnswersPayload {
    if (!answersComplete.value || hasRestaurant.value === null) {
      throw new Error('Classification answers are incomplete')
    }
    return {
      rooms: Number(rooms.value),
      guests: Number(guests.value),
      has_restaurant: hasRestaurant.value,
    }
  }

  async function loadQuestions(force = false): Promise<void> {
    if (questions.value.length && !force) return
    loadingQuestions.value = true
    try {
      const response = await api.get<ClassificationQuestionsResponse>('/api/v1/classification/questions/')
      questions.value = [...response.questions].sort((a, b) => a.order - b.order)
      questionsVersion.value = response.version
      persist()
    } finally {
      loadingQuestions.value = false
    }
  }

  async function evaluate(): Promise<ClassificationEvaluation> {
    evaluating.value = true
    try {
      const response = await api.post<ClassificationEvaluation>(
        '/api/v1/classification/evaluate/',
        answerPayload(),
      )
      evaluation.value = response
      currentStep.value = 3
      persist()
      return response
    } finally {
      evaluating.value = false
    }
  }

  function reset(): void {
    rooms.value = ''
    guests.value = ''
    hasRestaurant.value = null
    currentStep.value = 1
    questionsVersion.value = null
    questions.value = []
    evaluation.value = null
    window.sessionStorage.removeItem(CLASSIFICATION_SESSION_KEY)
  }

  function clearAfterApplicationCreated(): void {
    reset()
  }

  return {
    rooms,
    guests,
    hasRestaurant,
    currentStep,
    questionsVersion,
    questions,
    evaluation,
    loadingQuestions,
    evaluating,
    hasProgress,
    answersComplete,
    canCreateApplication,
    persist,
    setStep,
    updateRooms,
    updateGuests,
    updateRestaurant,
    answerPayload,
    loadQuestions,
    evaluate,
    reset,
    clearAfterApplicationCreated,
  }
})
