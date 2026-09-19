import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { CLASSIFICATION_SESSION_KEY, useClassificationStore } from '@/stores/classification'

describe('classification state', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('keeps anonymous answers in session storage across store recreation', () => {
    const store = useClassificationStore()
    store.updateRooms('20')
    store.updateGuests('40')
    store.updateRestaurant(false)
    store.setStep(3)

    const saved = JSON.parse(window.sessionStorage.getItem(CLASSIFICATION_SESSION_KEY) ?? '{}')
    expect(saved).toMatchObject({ rooms: '20', guests: '40', hasRestaurant: false, currentStep: 3 })

    setActivePinia(createPinia())
    const restored = useClassificationStore()
    expect(restored.rooms).toBe('20')
    expect(restored.guests).toBe('40')
    expect(restored.hasRestaurant).toBe(false)
    expect(restored.answerPayload()).toEqual({ rooms: 20, guests: 40, has_restaurant: false })
  })

  it('invalidates a cached result when an answer changes', () => {
    const store = useClassificationStore()
    store.evaluation = {
      outcome: 'TYPE_1',
      requires_license: true,
      property_type: { id: 1, code: 'TYPE_1', name: 'Type 1' },
      fee: { amount: '10000.00', currency: 'THB', validity_years: 5 },
      needs_manual_classification_confirmation: false,
      rules_version: 'v1',
    }

    store.updateRooms('21')
    expect(store.evaluation).toBeNull()
  })

  it('never persists credentials or personal property data', () => {
    const store = useClassificationStore()
    store.updateRooms('8')
    store.updateGuests('36')
    store.updateRestaurant(true)

    const saved = window.sessionStorage.getItem(CLASSIFICATION_SESSION_KEY) ?? ''
    expect(saved).not.toContain('password')
    expect(saved).not.toContain('email')
    expect(saved).not.toContain('address')
  })
})
