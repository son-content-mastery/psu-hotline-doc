<script setup lang="ts">
import AppShell from '@/components/AppShell.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="flex min-h-screen flex-col bg-slate-50 text-slate-950">
    <AppShell>
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" v-if="!route.meta.requiresAuth || auth.authenticated" />
      </RouterView>
    </AppShell>
  </div>
</template>
