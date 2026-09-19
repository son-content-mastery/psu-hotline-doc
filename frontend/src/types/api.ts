export type Role = 'APPLICANT' | 'LOCAL_OFFICER' | 'CENTRAL_OFFICER' | 'SUPER_ADMIN'

export interface LocalAuthority {
  id: number
  code: string
  name: string
  contact_phone?: string | null
  contact_email?: string | null
  translation_fallback?: boolean
}

export interface User {
  id: number
  email: string
  display_name: string
  role: Role
  local_authority: LocalAuthority | null
}

export interface AuthMeResponse {
  authenticated: boolean
  user: User | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type ClassificationQuestionKey = 'rooms' | 'guests' | 'max_guests' | 'has_restaurant'

export interface ClassificationQuestion {
  key: ClassificationQuestionKey
  order: number
  type: 'integer' | 'boolean'
  label: string
  required: boolean
  minimum?: number
}

export interface ClassificationQuestionsResponse {
  version: string
  questions: ClassificationQuestion[]
}

export type ClassificationOutcome =
  | 'NOT_HOTEL'
  | 'TYPE_1'
  | 'TYPE_2'
  | 'REQUIRES_LICENSE_REVIEW'
  | 'OUT_OF_SCOPE'

export interface PropertyType {
  id?: number
  code: string
  name: string
  issues_license?: boolean
}

export interface Fee {
  amount: string
  currency: string
  validity_years: number
}

export interface ClassificationEvaluation {
  outcome: ClassificationOutcome
  requires_license: boolean
  property_type: (PropertyType & { id: number }) | null
  fee: Fee | null
  needs_manual_classification_confirmation: boolean
  rules_version: string
  explanation?: string | null
  guidance?: string | null
}

export interface ClassificationAnswersPayload {
  rooms: number
  guests: number
  has_restaurant: boolean
}

export type RequirementCategory = 'OPERATOR_PREPARED' | 'EXTERNAL_AGENCY'
export type DocumentStatus = 'MISSING' | 'UPLOADED' | 'APPROVED' | 'REVISION_REQUIRED' | 'REJECTED'
export type ApplicationStatus =
  | 'DRAFT'
  | 'READY_TO_SUBMIT'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'REVISION_REQUIRED'
  | 'RESUBMITTED'
  | 'APPROVED'
  | 'REJECTED'

export interface DocumentType {
  id: number
  code: string
  name: string
  description?: string | null
  category?: RequirementCategory
  allows_multiple_files?: boolean
}

export type RequirementStepCode = 'APPLICANT' | 'PREMISES' | 'FACILITIES' | 'SAFETY' | 'MANAGER'

export interface RequirementGuidance {
  issuing_agency?: { id: number; code?: string; name: string } | null
  responsible_local_authority?: Pick<LocalAuthority, 'id' | 'name'> | null
  contact?: string | null
  contact_phone?: string | null
  contact_email?: string | null
  source_url?: string | null
  instructions?: string | null
  required_supporting_items?: string[]
  approximate_processing_days?: number | null
}

export interface RequirementItem {
  requirement_id?: number
  document_type: DocumentType
  required: boolean
  step_code: RequirementStepCode
  status?: DocumentStatus
  current_document_id?: number | null
  current_document_ids?: number[]
  latest_review_reason?: string | null
  description?: string | null
  instructions?: string | null
  guidance?: RequirementGuidance | null
}

export interface RequirementGroup {
  category: RequirementCategory
  items: RequirementItem[]
}

export interface RequirementStep {
  code: RequirementStepCode
  order: number
  required: number
  completed: number
  action_required: number
  complete: boolean
  items: RequirementItem[]
}

export interface RequirementsResponse {
  application_id?: number
  property_type?: PropertyType & { id?: number }
  is_legally_validated_checklist: boolean
  disclaimer: string
  complete_for_submission?: boolean
  groups: RequirementGroup[]
  steps: RequirementStep[]
}

export interface ApplicationProperty {
  id?: number
  name: string
  address_line?: string
  subdistrict?: string
  district?: string
  province?: string
  postal_code?: string
  local_authority?: LocalAuthority
}

export interface ApplicationClassification {
  outcome: ClassificationOutcome
  property_type: PropertyType | null
  answers: ClassificationAnswersPayload
}

export interface RequirementsSummary {
  required: number
  approved: number
  current_uploads: number
  complete_for_submission: boolean
}

export interface Application {
  id: number
  reference_number: string | null
  status: ApplicationStatus
  current_stage?: string
  applicant_action_required?: boolean
  waiting_since?: string | null
  property: ApplicationProperty
  property_name?: string
  classification: ApplicationClassification
  requirements?: RequirementsSummary
  requirements_complete?: boolean
  responsible_authority?: LocalAuthority
  submitted_at?: string | null
  resubmitted_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface ApplicationListItem {
  id: number
  reference_number: string | null
  property_name: string
  status: ApplicationStatus
  current_stage: string
  applicant_action_required: boolean
  waiting_since: string | null
  property_type: PropertyType | null
  responsible_authority: LocalAuthority | null
  requirements: RequirementsSummary
  updated_at: string
}

export interface ApplicationDocument {
  id: number
  application_id?: number
  document_type: DocumentType
  version: number
  attachment_index: number
  status: DocumentStatus
  is_current: boolean
  original_filename?: string
  content_type?: string
  size_bytes?: number
  uploaded_at?: string
  latest_review_reason?: string | null
  download_url?: string
  bundle_count?: number
  bundle_documents?: ApplicationDocument[]
}

export interface HistoryEvent {
  id: number
  from_status: ApplicationStatus | null
  to_status: ApplicationStatus
  occurred_at: string
  reason: string | null
  document_type?: Pick<DocumentType, 'id' | 'name'> | null
  actor_category?: string | null
}

export interface HistoryResponse {
  application_id: number
  current_status: ApplicationStatus
  waiting_since: string | null
  applicant_action_required: boolean
  events: HistoryEvent[]
}

export interface OfficerQueueItem {
  id: number
  reference_number: string
  property_name: string
  property_type: PropertyType | null
  status: ApplicationStatus
  submitted_at: string
  resubmitted_at?: string | null
  waiting_since: string
  documents_pending_review: number
}

export interface DocumentReview {
  id: number
  application_document_id?: number
  outcome: Exclude<DocumentStatus, 'MISSING' | 'UPLOADED'>
  reason: string | null
  reviewed_at: string
  reviewed_by?: { id: number; display_name: string }
}

export interface OfficerDocument extends ApplicationDocument {
  category: RequirementCategory
  version_label: 'CURRENT' | 'PRIOR'
  uploaded_by: { id: number; display_name: string; role: Role }
  uploader_role: Role
  reviews: DocumentReview[]
  versions?: OfficerDocument[]
}

export type OfficerAllowedAction = 'REVIEW_DOCUMENTS' | 'REQUEST_REVISION' | 'APPROVE' | 'REJECT'

export interface OfficerApplication {
  id: number
  reference_number: string
  status: ApplicationStatus
  waiting_since?: string | null
  submitted_at?: string | null
  resubmitted_at?: string | null
  property: ApplicationProperty
  classification: ApplicationClassification
  documents: OfficerDocument[]
  all_required_documents_approved: boolean
  allowed_actions: OfficerAllowedAction[]
  history?: HistoryEvent[]
}

export interface CentralTotals {
  applications: number
  waiting_review: number
  waiting_for_applicant_revision: number
  approved: number
}

export interface CentralBreakdownItem {
  code: string
  name?: string | null
  count: number
}

export interface CentralStageItem {
  stage: string
  count: number
}

export interface CentralAuthoritySummary {
  id: number
  code: string
  name: string
  count: number
  totals: CentralTotals
  by_property_type: CentralBreakdownItem[]
  by_current_stage: CentralStageItem[]
}

export interface CentralSummary {
  generated_at: string
  totals: CentralTotals
  by_property_type: CentralBreakdownItem[]
  by_local_authority: CentralAuthoritySummary[]
  authority_count: number
  authority_zeroes_included: boolean
  by_current_stage: CentralStageItem[]
}

export interface License {
  id: number
  artifact_kind: 'HOTEL_LICENSE' | 'NOTIFICATION_ACKNOWLEDGEMENT'
  license_number: string
  application_reference_number: string
  property: { name: string; address: string }
  property_type: PropertyType
  issuing_authority: LocalAuthority
  issued_at: string
  expires_at: string | null
  fee: {
    amount_snapshot: string
    currency: string
    fee_schedule_id: number
  } | null
}

export interface ApiErrorPayload {
  error?: {
    code?: string
    message?: string
    fields?: Record<string, string[]>
  }
}
