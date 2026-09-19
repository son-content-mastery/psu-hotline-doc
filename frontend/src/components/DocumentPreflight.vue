<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DocumentPreflight } from '@/types/api'

const props = defineProps<{ preflight: DocumentPreflight }>()
const { t } = useI18n()

const toneClass = computed(() => {
  if (props.preflight.status === 'WARNING') return 'border-amber-500 bg-amber-50 text-amber-950'
  if (props.preflight.status === 'PASS') return 'border-emerald-600 bg-emerald-50 text-emerald-950'
  return 'border-sky-500 bg-sky-50 text-sky-950'
})
</script>

<template>
<aside
  class="mt-3 rounded-xl border-l-4 p-3"
  :class="toneClass"
  :aria-label="t('documents.preflight.label')"
  data-testid="document-preflight"
>
  <p class="font-bold">
    {{ t(`documents.preflight.status.${preflight.status.toLowerCase()}`) }}
  </p>
  <ul v-if="preflight.issue_codes.length" class="mt-1 list-disc space-y-1 pl-5 text-sm" role="list">
    <li v-for="code in preflight.issue_codes" :key="code">
      {{ t(`documents.preflight.issues.${code.toLowerCase()}`) }}
    </li>
  </ul>
  <p class="mt-1 text-xs font-semibold opacity-80">{{ t('documents.preflight.advisory') }}</p>
</aside>
</template>
