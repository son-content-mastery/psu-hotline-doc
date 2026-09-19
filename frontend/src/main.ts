import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from '@/App.vue'
import { i18n } from '@/i18n'
import router from '@/router'
import { installSessionExpiryHandler } from '@/services/sessionExpiry'
import '@/styles.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(i18n)
app.use(router)
installSessionExpiryHandler(router, pinia)
app.mount('#app')
