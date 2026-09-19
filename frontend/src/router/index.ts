import { nextTick } from 'vue'
import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useClassificationStore } from '@/stores/classification'
import type { Role } from '@/types/api'
import { isPositiveWholeNumber } from '@/utils/domain'

declare module 'vue-router' {
  interface RouteMeta {
    titleKey: string
    requiresAuth?: boolean
    roles?: Role[]
    requiresClassification?: 'evaluation' | 'supported'
  }
}

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { titleKey: 'routes.home' },
    },
    {
      path: '/classification/:step(1|2|3)',
      name: 'classification-step',
      component: () => import('@/views/classification/ClassificationWizardView.vue'),
      meta: { titleKey: 'routes.classification' },
    },
    {
      path: '/classification/result',
      name: 'classification-result',
      component: () => import('@/views/classification/ClassificationResultView.vue'),
      meta: { titleKey: 'routes.classificationResult', requiresClassification: 'evaluation' },
    },
    {
      path: '/classification/requirements',
      name: 'public-requirements',
      component: () => import('@/views/classification/PublicRequirementsView.vue'),
      meta: { titleKey: 'routes.requirements', requiresClassification: 'supported' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/shared/LoginView.vue'),
      meta: { titleKey: 'routes.login' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/shared/RegisterView.vue'),
      meta: { titleKey: 'routes.register' },
    },
    {
      path: '/activate-account',
      name: 'activate-account',
      component: () => import('@/views/shared/ActivateAccountView.vue'),
      meta: { titleKey: 'routes.activateAccount' },
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('@/views/shared/ForgotPasswordView.vue'),
      meta: { titleKey: 'routes.forgotPassword' },
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('@/views/shared/ResetPasswordView.vue'),
      meta: { titleKey: 'routes.resetPassword' },
    },
    {
      path: '/applications',
      name: 'application-list',
      component: () => import('@/views/applicant/ApplicationListView.vue'),
      meta: { titleKey: 'routes.applications', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/applications/new',
      name: 'application-create',
      component: () => import('@/views/applicant/ApplicationCreateView.vue'),
      meta: {
        titleKey: 'routes.applicationCreate',
        requiresAuth: true,
        roles: ['APPLICANT'],
        requiresClassification: 'supported',
      },
    },
    {
      path: '/applications/:id(\\d+)/documents',
      name: 'application-documents',
      component: () => import('@/views/applicant/ApplicationDocumentsView.vue'),
      meta: { titleKey: 'routes.documents', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/applications/:id(\\d+)/review',
      name: 'application-review',
      component: () => import('@/views/applicant/ApplicationReviewView.vue'),
      meta: { titleKey: 'routes.submissionReview', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/applications/:id(\\d+)/submitted',
      name: 'application-submitted',
      component: () => import('@/views/applicant/SubmissionSuccessView.vue'),
      meta: { titleKey: 'routes.submitted', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/applications/:id(\\d+)/tracking',
      name: 'application-tracking',
      component: () => import('@/views/applicant/ApplicationTrackingView.vue'),
      meta: { titleKey: 'routes.tracking', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/applications/:id(\\d+)/license',
      name: 'application-license',
      component: () => import('@/views/applicant/LicenseView.vue'),
      meta: { titleKey: 'routes.license', requiresAuth: true, roles: ['APPLICANT'] },
    },
    {
      path: '/officer/applications',
      name: 'officer-queue',
      component: () => import('@/views/officer/OfficerQueueView.vue'),
      meta: { titleKey: 'routes.officerQueue', requiresAuth: true, roles: ['LOCAL_OFFICER'] },
    },
    {
      path: '/officer/applications/:id(\\d+)',
      name: 'officer-review',
      component: () => import('@/views/officer/OfficerReviewView.vue'),
      meta: { titleKey: 'routes.officerReview', requiresAuth: true, roles: ['LOCAL_OFFICER'] },
    },
    {
      path: '/central/overview',
      name: 'central-overview',
      component: () => import('@/views/central/CentralOverviewView.vue'),
      meta: { titleKey: 'routes.central', requiresAuth: true, roles: ['CENTRAL_OFFICER'] },
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/shared/ForbiddenView.vue'),
      meta: { titleKey: 'routes.forbidden' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/shared/NotFoundView.vue'),
      meta: { titleKey: 'routes.notFound' },
    },
  ],
})

function loginIntentFor(route: RouteLocationNormalized): string {
  if (route.meta.roles?.includes('LOCAL_OFFICER')) return 'officer'
  if (route.meta.roles?.includes('CENTRAL_OFFICER')) return 'central'
  return 'applicant'
}

function homeForRole(role: Role): string {
  if (role === 'LOCAL_OFFICER') return '/officer/applications'
  if (role === 'CENTRAL_OFFICER') return '/central/overview'
  if (role === 'APPLICANT') return '/applications'
  return '/'
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const classification = useClassificationStore()
  await auth.bootstrap()

  if ((to.name === 'login' || to.name === 'register') && auth.user) return homeForRole(auth.user.role)

  if (to.name === 'classification-step') {
    const step = Number(to.params.step)
    if (step > 1 && !isPositiveWholeNumber(classification.rooms)) {
      return { name: 'classification-step', params: { step: '1' }, query: { notice: 'missing' } }
    }
    if (step > 2 && !isPositiveWholeNumber(classification.guests)) {
      return { name: 'classification-step', params: { step: '2' }, query: { notice: 'missing' } }
    }
  }

  if (to.meta.requiresClassification === 'evaluation' && !classification.evaluation) {
    return { name: 'classification-step', params: { step: '1' }, query: { notice: 'missing' } }
  }
  if (to.meta.requiresClassification === 'supported' && !classification.canCreateApplication) {
    return classification.evaluation
      ? { name: 'classification-result' }
      : { name: 'classification-step', params: { step: '1' }, query: { notice: 'missing' } }
  }

  if (to.meta.requiresAuth && !auth.authenticated) {
    return {
      name: 'login',
      query: { intent: loginIntentFor(to), redirect: to.fullPath },
    }
  }
  if (to.meta.roles?.length && auth.user && !to.meta.roles.includes(auth.user.role)) {
    return { name: 'forbidden' }
  }
  return true
})

router.afterEach((to, from) => {
  const title = i18n.global.t(to.meta.titleKey)
  document.title = `${title} · ${i18n.global.t('common.serviceName')}`
  if (from.name === undefined) return
  void nextTick(() => {
    document.querySelector<HTMLElement>('[data-page-heading]')?.focus({ preventScroll: true })
  })
})

export default router
