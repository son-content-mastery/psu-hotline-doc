<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import InlineAlert from '@/components/InlineAlert.vue'
import { api } from '@/services/api'
import type { DiscussionMessage } from '@/types/api'
import { formatDate } from '@/utils/format'

const props = defineProps<{ endpoint: string; canPost: boolean }>()
const { locale, t } = useI18n()
const messages = ref<DiscussionMessage[]>([])
const body = ref('')
const loading = ref(true)
const working = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    messages.value = (await api.get<{ results: DiscussionMessage[] }>(props.endpoint)).results ?? []
  } catch {
    error.value = t('discussion.loadError')
  } finally {
    loading.value = false
  }
}

async function send(): Promise<void> {
  const trimmed = body.value.trim()
  if (!trimmed) return
  working.value = true
  error.value = ''
  try {
    messages.value.push(await api.post<DiscussionMessage>(props.endpoint, { body: trimmed }))
    body.value = ''
  } catch {
    error.value = t('discussion.sendError')
  } finally {
    working.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="card mt-8" aria-labelledby="discussion-heading">
    <h2 id="discussion-heading" class="text-2xl font-black">{{ t('discussion.title') }}</h2>
    <p class="mt-2 text-slate-700">{{ t('discussion.intro') }}</p>
    <p v-if="loading" class="mt-5" aria-live="polite">{{ t('common.loading') }}</p>
    <InlineAlert v-else-if="error" tone="error" class="mt-5">{{ error }}</InlineAlert>
    <p v-else-if="messages.length === 0" class="mt-5 text-slate-600">{{ t('discussion.empty') }}</p>
    <ol v-else class="mt-5 space-y-3" role="list">
      <li v-for="message in messages" :key="message.id" class="rounded-2xl border border-slate-200 p-4">
        <div class="flex flex-wrap justify-between gap-3">
          <p class="font-black">{{ t(`discussion.sender.${message.sender_category}`) }}</p>
          <time class="text-sm text-slate-600" :datetime="message.created_at">{{ formatDate(message.created_at, locale) }}</time>
        </div>
        <p class="mt-2 whitespace-pre-wrap break-words">{{ message.body }}</p>
      </li>
    </ol>
    <form v-if="canPost" class="mt-6 border-t border-slate-200 pt-5" @submit.prevent="send">
      <label class="field-label" for="discussion-message">{{ t('discussion.messageLabel') }}</label>
      <textarea id="discussion-message" v-model="body" class="field-input min-h-28" maxlength="2000" required />
      <p class="mt-2 text-sm text-slate-600">{{ t('discussion.evidenceNotice') }}</p>
      <button type="submit" class="button-primary mt-4" :disabled="working || !body.trim()">
        {{ t(working ? 'discussion.sending' : 'discussion.send') }}
      </button>
    </form>
    <InlineAlert v-else tone="info" class="mt-5">{{ t('discussion.closed') }}</InlineAlert>
  </section>
</template>
