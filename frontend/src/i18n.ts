import { createI18n } from 'vue-i18n'

import en from '@/locales/en.json'
import th from '@/locales/th.json'

export type AppLocale = 'th' | 'en'

const savedLocale = window.localStorage.getItem('hotline-doc:locale')
const initialLocale: AppLocale = savedLocale === 'en' ? 'en' : 'th'

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'th',
  messages: { th, en },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
})

document.documentElement.lang = initialLocale

export function setLocale(locale: AppLocale): void {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
  window.localStorage.setItem('hotline-doc:locale', locale)
}
