<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'info' | 'success' | 'warning' | 'error'
    live?: 'off' | 'polite' | 'assertive'
  }>(),
  { tone: 'info', live: 'off' },
)
</script>

<template>
  <div
    class="rounded-2xl border px-4 py-4 text-base leading-relaxed"
    :class="{
      'border-sky-300 bg-sky-50 text-sky-950': tone === 'info',
      'border-emerald-300 bg-emerald-50 text-emerald-950': tone === 'success',
      'border-amber-400 bg-amber-50 text-amber-950': tone === 'warning',
      'border-red-400 bg-red-50 text-red-950': tone === 'error',
    }"
    :role="tone === 'error' ? 'alert' : undefined"
    :aria-live="live === 'off' ? undefined : live"
  >
    <slot />
  </div>
</template>
