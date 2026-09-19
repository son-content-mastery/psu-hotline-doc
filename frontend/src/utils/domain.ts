import type { ApplicationStatus, DocumentStatus } from '@/types/api'

const applicationStatusKeys: Record<ApplicationStatus, string> = {
  DRAFT: 'statuses.application.draft',
  READY_TO_SUBMIT: 'statuses.application.readyToSubmit',
  SUBMITTED: 'statuses.application.submitted',
  UNDER_REVIEW: 'statuses.application.underReview',
  REVISION_REQUIRED: 'statuses.application.revisionRequired',
  RESUBMITTED: 'statuses.application.resubmitted',
  APPROVED: 'statuses.application.approved',
  REJECTED: 'statuses.application.rejected',
}

const documentStatusKeys: Record<DocumentStatus, string> = {
  MISSING: 'statuses.document.missing',
  UPLOADED: 'statuses.document.uploaded',
  APPROVED: 'statuses.document.approved',
  REVISION_REQUIRED: 'statuses.document.revisionRequired',
  REJECTED: 'statuses.document.rejected',
}

const stageKeys: Record<string, string> = {
  APPLICANT_PREPARATION: 'statuses.stage.applicantPreparation',
  APPLICANT_ACTION: 'statuses.stage.applicantAction',
  LOCAL_OFFICER_REVIEW: 'statuses.stage.localOfficer',
  COMPLETED: 'statuses.stage.completed',
}

export function applicationStatusKey(value: string | null | undefined): string {
  return applicationStatusKeys[value as ApplicationStatus] ?? 'common.statusUnavailable'
}

export function documentStatusKey(value: string | null | undefined): string {
  return documentStatusKeys[value as DocumentStatus] ?? 'common.statusUnavailable'
}

export function stageKey(value: string | null | undefined): string {
  return (value && stageKeys[value]) || 'common.statusUnavailable'
}

export function isPositiveWholeNumber(value: string): boolean {
  return /^[1-9]\d*$/.test(value.trim())
}

export function statusSymbol(value: string): string {
  if (value === 'APPROVED') return '✓'
  if (value === 'UPLOADED' || value === 'SUBMITTED') return '↑'
  if (value === 'RESUBMITTED') return '↻'
  if (value === 'UNDER_REVIEW') return '◷'
  if (value === 'READY_TO_SUBMIT') return '→'
  if (value === 'REVISION_REQUIRED') return '!'
  if (value === 'REJECTED') return '×'
  return '○'
}

export function isReviewableStatus(value: string): boolean {
  return ['SUBMITTED', 'RESUBMITTED', 'UNDER_REVIEW'].includes(value)
}

export type ApplicantApplicationDestination =
  | 'application-documents'
  | 'application-review'
  | 'application-tracking'

export function applicantApplicationDestination(status: string): ApplicantApplicationDestination {
  if (status === 'DRAFT') return 'application-documents'
  if (status === 'READY_TO_SUBMIT') return 'application-review'
  return 'application-tracking'
}
