<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { LocalAuthority, Paginated } from '@/types/api'

const { locale, t } = useI18n()
const authorities = ref<LocalAuthority[]>([])
const selectedId = ref<number | ''>('')
const loading = ref(true)
const error = ref(false)
const heading = ref<HTMLElement | null>(null)

function selectedAuthority(): LocalAuthority | undefined {
  return authorities.value.find((item) => item.id === selectedId.value)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const response = await api.get<Paginated<LocalAuthority>>('/api/v1/local-authorities/')
    authorities.value = response.results
    if (selectedId.value && !authorities.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = ''
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function focusPanel(): void {
  void nextTick(() => heading.value?.focus())
}

defineExpose({ focusPanel })
watch(locale, load)
onMounted(load)
</script>

<template>
  <section class="card mt-7 border-2 border-brand-100" aria-labelledby="authority-contact-title">
    <h2 id="authority-contact-title" ref="heading" tabindex="-1" class="text-2xl font-black">
      {{ t('classification.contact.title') }}
    </h2>
    <p class="mt-3 text-slate-700">{{ t('classification.contact.intro') }}</p>

    <p v-if="loading" class="mt-5" aria-live="polite">{{ t('classification.contact.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-5">
      {{ t('classification.contact.error') }}
      <button type="button" class="ml-2 font-bold underline" @click="load">{{ t('common.actions.retry') }}</button>
    </InlineAlert>

    <template v-else>
      <label for="contact-authority" class="field-label mt-5">{{ t('classification.contact.selectLabel') }}</label>
      <select id="contact-authority" v-model.number="selectedId" class="field-input">
        <option value="">{{ t('classification.contact.selectPlaceholder') }}</option>
        <option v-for="authority in authorities" :key="authority.id" :value="authority.id">
          {{ authority.name }}
        </option>
      </select>
      <p class="mt-2 text-sm text-slate-600">{{ t('classification.contact.selectHelp') }}</p>

      <div v-if="selectedAuthority()" class="mt-5 rounded-2xl bg-brand-50 p-5" aria-live="polite">
        <h3 class="text-xl font-black">{{ selectedAuthority()?.name }}</h3>
        <dl class="definition-grid mt-4">
          <template v-if="selectedAuthority()?.contact_phone">
            <dt>{{ t('classification.contact.phone') }}</dt>
            <dd>
              <a :href="`tel:${selectedAuthority()?.contact_phone}`">{{ selectedAuthority()?.contact_phone }}</a>
            </dd>
          </template>
          <template v-if="selectedAuthority()?.contact_email">
            <dt>{{ t('classification.contact.email') }}</dt>
            <dd class="break-all">
              <a :href="`mailto:${selectedAuthority()?.contact_email}`">{{ selectedAuthority()?.contact_email }}</a>
            </dd>
          </template>
        </dl>
        <p class="mt-4 text-sm font-semibold text-slate-700">{{ t('classification.contact.demoNotice') }}</p>
      </div>
    </template>
  </section>
</template>
