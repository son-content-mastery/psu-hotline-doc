<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="page-narrow">
    <h1 data-page-heading tabindex="-1" class="page-title">{{ t('errors.notFoundTitle') }}</h1>
    <p class="page-intro">{{ t('errors.notFoundBody') }}</p>
    <RouterLink class="button-primary mt-7" :to="{ name: 'home' }">{{ t('common.actions.home') }}</RouterLink>
  </div>
</template>
