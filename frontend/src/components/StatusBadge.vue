<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { applicationStatusKey, documentStatusKey } from '@/utils/domain'

const props = defineProps<{
  status: string | null | undefined
  kind?: 'application' | 'document'
}>()

const { t } = useI18n()
const label = computed(() =>
  t(props.kind === 'document' ? documentStatusKey(props.status) : applicationStatusKey(props.status)),
)
const toneClass = computed(() => {
  const value = props.status ?? ''
  if (value === 'APPROVED') return 'border-emerald-700 bg-emerald-50 text-emerald-950'
  if (value === 'REVISION_REQUIRED') return 'border-amber-700 bg-amber-50 text-amber-950'
  if (value === 'REJECTED') return 'border-red-700 bg-red-50 text-red-950'
  if (['SUBMITTED', 'RESUBMITTED', 'UPLOADED'].includes(value)) {
    return 'border-sky-700 bg-sky-50 text-sky-950'
  }
  if (value === 'UNDER_REVIEW') return 'border-violet-700 bg-violet-50 text-violet-950'
  if (value === 'READY_TO_SUBMIT') return 'border-brand-700 bg-brand-50 text-brand-900'
  return 'border-slate-400 bg-slate-100 text-slate-900'
})
</script>

<template>
  <span :class="['status-badge', toneClass]">
    <svg v-if="status === 'APPROVED'" class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.78-9.97a.75.75 0 0 0-1.06-1.06L9 10.69 7.28 8.97a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25Z" clip-rule="evenodd" />
    </svg>
    <svg v-else-if="status === 'REVISION_REQUIRED'" class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M8.49 3.17c.67-1.16 2.35-1.16 3.02 0l6.13 10.64c.66 1.16-.17 2.6-1.51 2.6H3.87c-1.34 0-2.17-1.44-1.5-2.6L8.48 3.17ZM10 6.75a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3a.75.75 0 0 1 .75-.75Zm0 6.75a.88.88 0 1 0 0-1.75.88.88 0 0 0 0 1.75Z" clip-rule="evenodd" />
    </svg>
    <svg v-else-if="status === 'REJECTED'" class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM7.72 6.66a.75.75 0 0 0-1.06 1.06L8.94 10l-2.28 2.28a.75.75 0 1 0 1.06 1.06L10 11.06l2.28 2.28a.75.75 0 0 0 1.06-1.06L11.06 10l2.28-2.28a.75.75 0 0 0-1.06-1.06L10 8.94 7.72 6.66Z" clip-rule="evenodd" />
    </svg>
    <svg v-else-if="['SUBMITTED', 'RESUBMITTED', 'UPLOADED'].includes(status ?? '')" class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path d="M3 3.75A1.75 1.75 0 0 1 4.75 2h6.69c.47 0 .91.19 1.24.51l3.81 3.81c.32.33.51.77.51 1.24v8.69A1.75 1.75 0 0 1 15.25 18H4.75A1.75 1.75 0 0 1 3 16.25V3.75Zm7.53 3.22a.75.75 0 0 0-1.06 0l-2.5 2.5a.75.75 0 0 0 1.06 1.06l1.22-1.22v4.19a.75.75 0 0 0 1.5 0V9.31l1.22 1.22a.75.75 0 1 0 1.06-1.06l-2.5-2.5Z" />
    </svg>
    <svg v-else-if="status === 'UNDER_REVIEW'" class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-12.5a.75.75 0 0 0-1.5 0V10c0 .24.11.47.3.61l3 2.25a.75.75 0 1 0 .9-1.2l-2.7-2.03V5.5Z" clip-rule="evenodd" />
    </svg>
    <svg v-else class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm0-11.25a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3a.75.75 0 0 1 .75-.75Zm0 6.75a.88.88 0 1 0 0-1.75.88.88 0 0 0 0 1.75Z" clip-rule="evenodd" />
    </svg>
    <span>{{ label }}</span>
  </span>
</template>
