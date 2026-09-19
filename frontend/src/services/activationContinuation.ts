import { safeRelativeRedirect } from '@/services/sessionExpiry'

const ACTIVATION_REDIRECT_KEY = 'hotline-doc.activation-redirect'

export function rememberActivationRedirect(value: unknown): void {
  const redirect = safeRelativeRedirect(value, '/applications')
  try {
    window.localStorage.setItem(ACTIVATION_REDIRECT_KEY, redirect)
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }
}

export function takeActivationRedirect(): string {
  try {
    const redirect = safeRelativeRedirect(window.localStorage.getItem(ACTIVATION_REDIRECT_KEY), '/applications')
    window.localStorage.removeItem(ACTIVATION_REDIRECT_KEY)
    return redirect
  } catch {
    return '/applications'
  }
}
