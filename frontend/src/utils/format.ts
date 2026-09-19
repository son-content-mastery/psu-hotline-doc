export type SupportedLocale = 'th' | 'en'

function localeTag(locale: string): string {
  return locale === 'en' ? 'en-GB' : 'th-TH'
}

export function formatDate(value: string | null | undefined, locale: string, includeTime = true): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(localeTag(locale), {
    dateStyle: 'medium',
    ...(includeTime ? { timeStyle: 'short' as const } : {}),
  }).format(date)
}

export function formatMoney(amount: string | number, currency: string, locale: string): string {
  const numericAmount = typeof amount === 'number' ? amount : Number(amount)
  if (!Number.isFinite(numericAmount)) return '—'
  try {
    return new Intl.NumberFormat(localeTag(locale), {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(numericAmount)
  } catch {
    return `${new Intl.NumberFormat(localeTag(locale)).format(numericAmount)} ${currency}`
  }
}

export function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(localeTag(locale), { maximumFractionDigits: 0 }).format(value)
}

export function fullDaysSince(value: string | null | undefined): number | null {
  if (!value) return null
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return null
  return Math.max(0, Math.floor((Date.now() - time) / 86_400_000))
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
