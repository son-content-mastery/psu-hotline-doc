import { describe, expect, it } from 'vitest'

import {
  applicantApplicationDestination,
  applicationStatusKey,
  documentStatusKey,
  isPositiveWholeNumber,
  stageKey,
} from '@/utils/domain'

describe('domain presentation guards', () => {
  it.each(['1', '8', '49', ' 20 '])('accepts positive whole-number input %s', (value) => {
    expect(isPositiveWholeNumber(value)).toBe(true)
  })

  it.each(['', '0', '-1', '1.5', '1e2', '20 rooms'])('rejects unsafe numeric input %s', (value) => {
    expect(isPositiveWholeNumber(value)).toBe(false)
  })

  it('maps known workflow codes to translation keys', () => {
    expect(applicationStatusKey('UNDER_REVIEW')).toBe('statuses.application.underReview')
    expect(documentStatusKey('REVISION_REQUIRED')).toBe('statuses.document.revisionRequired')
    expect(stageKey('APPLICANT_PREPARATION')).toBe('statuses.stage.applicantPreparation')
    expect(stageKey('APPLICANT_ACTION')).toBe('statuses.stage.applicantAction')
    expect(stageKey('LOCAL_OFFICER_REVIEW')).toBe('statuses.stage.localOfficer')
  })

  it('never returns an unknown raw code for display', () => {
    expect(applicationStatusKey('FUTURE_STATUS')).toBe('common.statusUnavailable')
    expect(documentStatusKey('FUTURE_DOCUMENT_STATUS')).toBe('common.statusUnavailable')
    expect(stageKey('FUTURE_STAGE')).toBe('common.statusUnavailable')
  })

  it('routes a returning applicant to the next useful application task', () => {
    expect(applicantApplicationDestination('DRAFT')).toBe('application-documents')
    expect(applicantApplicationDestination('READY_TO_SUBMIT')).toBe('application-review')
    expect(applicantApplicationDestination('REVISION_REQUIRED')).toBe('application-tracking')
    expect(applicantApplicationDestination('APPROVED')).toBe('application-tracking')
    expect(applicantApplicationDestination('FUTURE_STATUS')).toBe('application-tracking')
  })
})
