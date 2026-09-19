import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api, ApiError } from '@/services/api'
import type { AuthMeResponse, User } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const loading = ref(false)

  const authenticated = computed(() => user.value !== null)

  async function bootstrap(force = false): Promise<void> {
    if (initialized.value && !force) return
    loading.value = true
    try {
      const response = await api.get<AuthMeResponse>('/api/v1/auth/me/')
      user.value = response.authenticated ? response.user : null
    } catch {
      user.value = null
    } finally {
      initialized.value = true
      loading.value = false
    }
  }

  async function login(email: string, password: string): Promise<User> {
    const response = await api.post<{ user: User }>('/api/v1/auth/login/', { email, password })
    user.value = response.user
    initialized.value = true
    return response.user
  }

  async function logout(): Promise<void> {
    try {
      await api.post<void>('/api/v1/auth/logout/')
    } catch (caught) {
      if (!(caught instanceof ApiError && caught.status === 401)) throw caught
    } finally {
      user.value = null
      initialized.value = true
    }
  }

  function clearSession(): void {
    user.value = null
    initialized.value = true
  }

  return { user, initialized, loading, authenticated, bootstrap, login, logout, clearSession }
})
