<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DocumentPreflight } from '@/types/api'

const props = defineProps<{ preflight: DocumentPreflight }>()
const { t } = useI18n()

const toneClass = computed(() => {
  if (props.preflight.status === 'WARNING' || props.preflight.type_check_status === 'POSSIBLE_MISMATCH') {
    return 'border-amber-500 bg-amber-50 text-amber-950'
  }
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
  <div v-if="preflight.type_check_status && preflight.type_check_status !== 'NOT_RUN'" class="mt-2 border-t border-current/20 pt-2 text-sm">
    <p class="font-bold">{{ t(`documents.preflight.typeStatus.${preflight.type_check_status.toLowerCase()}`) }}</p>
    <p v-if="preflight.detected_family" class="mt-1">
      {{ t('documents.preflight.detectedFamily', { family: t(`documents.preflight.families.${preflight.detected_family.toLowerCase()}`) }) }}
    </p>
  </div>
  <p class="mt-1 text-xs font-semibold opacity-80">{{ t('documents.preflight.advisory') }}</p>
</aside>
</template>
