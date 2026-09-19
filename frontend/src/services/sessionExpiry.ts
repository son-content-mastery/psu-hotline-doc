import type { Pinia } from 'pinia'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { setUnauthorizedHandler } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types/api'

export type LoginIntent = 'applicant' | 'officer' | 'central'

export function safeRelativeRedirect(value: unknown, fallback = '/'): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return fallback
  try {
    const base = new URL('https://hotline-doc.invalid/')
    const parsed = new URL(value, base)
    if (parsed.origin !== base.origin) return fallback
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    return fallback
  }
}

function intentForRole(role: Role | undefined): LoginIntent {
  if (role === 'LOCAL_OFFICER') return 'officer'
  if (role === 'CENTRAL_OFFICER') return 'central'
  return 'applicant'
}

function intentForRoute(route: RouteLocationNormalizedLoaded, role: Role | undefined): LoginIntent {
  if (route.meta.roles?.includes('LOCAL_OFFICER')) return 'officer'
  if (route.meta.roles?.includes('CENTRAL_OFFICER')) return 'central'
  return intentForRole(role)
}

export function installSessionExpiryHandler(router: Router, pinia: Pinia): () => void {
  let redirecting = false

  const handleUnauthorized = (): void => {
    const auth = useAuthStore(pinia)
    const route = router.currentRoute.value
    const wasAuthenticated = auth.authenticated
    const intent = intentForRoute(route, auth.user?.role)
    const redirect = safeRelativeRedirect(route.fullPath)
    auth.clearSession()

    if (!wasAuthenticated || !route.meta.requiresAuth || route.name === 'login' || redirecting) return

    redirecting = true
    void router
      .replace({ name: 'login', query: { intent, redirect, notice: 'expired' } })
      .finally(() => {
        redirecting = false
      })
  }

  setUnauthorizedHandler(handleUnauthorized)
  return () => setUnauthorizedHandler()
}
