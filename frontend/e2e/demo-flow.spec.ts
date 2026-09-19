import { expect, test, type Locator, type Page } from '@playwright/test'

const password = process.env.E2E_DEMO_PASSWORD ?? 'DemoPass123!'
const validPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAFElEQVR4nGP8//8/AwwwMSAB3BwAlm4DBfIlvvkAAAAASUVORK5CYII=',
  'base64',
)

async function signIn(page: Page, email: string): Promise<void> {
  await page.getByLabel('อีเมล').fill(email)
  await page.getByLabel('รหัสผ่าน').fill(password)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ' }).click()
  await page.waitForURL((url) => url.pathname !== '/login')
}

async function signOut(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'ออกจากระบบ' }).click()
  await expect(page).toHaveURL(/\/$/)
}

async function centralApprovedCount(page: Page): Promise<number> {
  const value = await page.getByRole('heading', { name: 'อนุมัติแล้ว' }).evaluate(
    (heading) => heading.parentElement?.parentElement?.querySelector(':scope > p')?.textContent ?? '',
  )
  return Number((value ?? '').replace(/[^0-9]/g, ''))
}

async function applicationCard(page: Page, propertyName: string): Promise<Locator> {
  const card = page.getByTestId('application-card').filter({ hasText: propertyName })
  await expect(card).toHaveCount(1)
  return card
}

async function openOfficerApplication(page: Page, propertyName: string): Promise<void> {
  const row = page.getByTestId('officer-queue-row').filter({ hasText: propertyName }).first()
  await expect(row).toBeVisible()
  await row.getByRole('link').click()
  await expect(page.getByRole('heading', { name: /ตรวจสอบคำขอ/ })).toBeVisible()
}

async function reviewDocument(
  page: Page,
  documentId: string,
  outcome: 'APPROVED' | 'REVISION_REQUIRED',
  reason = '',
): Promise<void> {
  const form = page.locator(`[data-testid="document-review-form"][data-document-id="${documentId}"]`)
  await form.locator(`input[value="${outcome}"]`).check()
  if (reason) await form.locator('textarea').fill(reason)
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes(`/api/v1/officer/documents/${documentId}/review/`),
  )
  await form.getByRole('button', { name: 'บันทึกผลตรวจเอกสาร' }).click()
  expect((await responsePromise).ok()).toBeTruthy()
  await expect(form).toHaveCount(0)
}

test('exact applicant revision approval and central-summary demo journey', async ({ page }) => {
  test.slow()
  const propertyName = `โรงแรมทดสอบ E2E ${Date.now()}`

  // Capture the aggregate before the exact story so the last assertion proves this case changed it.
  await page.goto('/login?intent=central&redirect=/central/overview')
  await signIn(page, 'central@example.test')
  await expect(page).toHaveURL(/\/central\/overview$/)
  const approvedBefore = await centralApprovedCount(page)
  await signOut(page)

  await page.getByRole('button', { name: 'เริ่มตรวจสอบที่พัก' }).click()
  await page.getByLabel(/ห้องพักทั้งหมด/).fill('20')
  await page.getByRole('button', { name: 'ถัดไป' }).click()
  await page.getByLabel(/ผู้เข้าพักได้สูงสุด/).fill('40')
  await page.getByRole('button', { name: 'ถัดไป' }).click()
  await page.getByLabel('ไม่มี').check()
  await page.getByRole('button', { name: 'ดูผลการตรวจสอบ' }).click()

  await expect(page.getByRole('heading', { name: 'ที่พักแรมประเภทที่ 1' })).toBeVisible()
  await page.getByRole('link', { name: 'ดูรายการเอกสาร' }).click()
  await expect(page.getByText('ต้องเตรียมทั้งหมด 28 รายการ')).toBeVisible()
  await page.getByRole('link', { name: 'เข้าสู่ระบบเพื่อบันทึกและอัปโหลดเอกสาร' }).click()
  await signIn(page, 'applicant@example.test')
  await expect(page).toHaveURL(/\/applications\/new$/)

  await page.getByLabel(/ชื่อที่พัก/).fill(propertyName)
  await page.getByLabel(/ที่อยู่/).fill('99 ถนนทดสอบ')
  await page.getByLabel(/ตำบล/).fill('ป่าตอง')
  await page.getByLabel(/อำเภอ/).fill('กะทู้')
  await page.getByLabel(/จังหวัด/).fill('ภูเก็ต')
  await page.getByLabel(/รหัสไปรษณีย์/).fill('83150')
  await page.getByLabel(/องค์กรปกครองส่วนท้องถิ่นที่รับผิดชอบ/).selectOption({ label: 'เทศบาลเมืองป่าตอง' })
  await page.getByRole('button', { name: /สร้างร่างและดำเนินการต่อ/ }).click()
  await expect(page).toHaveURL(/\/applications\/\d+\/documents/)
  const applicationId = page.url().match(/\/applications\/(\d+)\//)?.[1]
  expect(applicationId).toBeTruthy()

  const stepButtons = page.locator('nav[aria-label="ขั้นตอนการเตรียมเอกสาร"] button')
  await expect(stepButtons).toHaveCount(5)
  let correctionDocumentTypeId = ''
  for (let step = 0; step < 5; step += 1) {
    await stepButtons.nth(step).click()
    const fileIds = await page
      .locator('section[aria-labelledby="active-step-heading"] input[type="file"]')
      .evaluateAll((inputs) => inputs.map((input) => input.id))
    expect(fileIds.length).toBeGreaterThan(0)
    if (!correctionDocumentTypeId) correctionDocumentTypeId = fileIds[0].replace('file-', '')
    for (const [index, fileId] of fileIds.entries()) {
      const uploadPromise = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().includes(`/api/v1/applications/${applicationId}/documents/`),
      )
      await page.locator(`#${fileId}`).setInputFiles({
        name: `evidence-${step + 1}-${index + 1}.png`,
        mimeType: 'image/png',
        buffer: validPng,
      })
      expect((await uploadPromise).ok()).toBeTruthy()
    }
  }

  await expect(page.getByText('พร้อมแล้ว 28 จาก 28 รายการ')).toBeVisible()
  await page.getByRole('link', { name: 'ตรวจสอบข้อมูลก่อนยื่นคำขอ' }).click()
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'ยื่นคำขอ' }).click()
  await page.waitForURL(new RegExp(`/applications/${applicationId}/submitted$`))
  const reference = await page.locator('[aria-labelledby="reference-heading"] p').last().textContent()
  expect(reference).toMatch(/^HTL-\d{4}-\d{5}$/)
  await page.getByRole('link', { name: 'ติดตามคำขอ' }).click()
  await expect(page.getByText('เจ้าหน้าที่กำลังตรวจสอบ')).toBeVisible()
  await signOut(page)

  await page.getByRole('link', { name: 'เข้าสู่ระบบเจ้าหน้าที่' }).click()
  await signIn(page, 'officer.patong@example.test')
  await openOfficerApplication(page, propertyName)

  await expect(page.getByTestId('document-review-form')).toHaveCount(28)
  const reviewRecords = await page.getByTestId('document-review-form').evaluateAll((forms) =>
    forms.map((form) => ({
      documentId: form.getAttribute('data-document-id') ?? '',
      documentTypeId: form.getAttribute('data-document-type-id') ?? '',
    })),
  )
  expect(reviewRecords).toHaveLength(28)
  const revisionRecord = reviewRecords.find((record) => record.documentTypeId === correctionDocumentTypeId)
  expect(revisionRecord).toBeTruthy()
  for (const record of reviewRecords) {
    await reviewDocument(
      page,
      record.documentId,
      record.documentId === revisionRecord?.documentId ? 'REVISION_REQUIRED' : 'APPROVED',
      record.documentId === revisionRecord?.documentId ? 'กรุณาอัปโหลดหลักฐานที่ชัดเจนขึ้น' : '',
    )
  }

  await page.getByRole('button', { name: 'ส่งกลับให้แก้ไข' }).click()
  await page.getByLabel('เหตุผลการพิจารณาคำขอ').fill('แก้ไขหลักฐานหนึ่งรายการตามเหตุผลที่ระบุ')
  await page.getByRole('button', { name: 'ยืนยันส่งกลับให้แก้ไข' }).click()
  await expect(page.getByText('ส่งคำขอกลับให้ผู้ยื่นแก้ไขแล้ว').last()).toBeVisible()
  await signOut(page)

  await page.goto('/login?intent=applicant&redirect=/applications')
  await signIn(page, 'applicant@example.test')
  const revisionCard = await applicationCard(page, propertyName)
  await revisionCard.getByRole('link', { name: 'ติดตามคำขอนี้' }).click()
  await expect(page.getByText('มีเอกสารที่ต้องแก้ไข 1 รายการ')).toBeVisible()
  await page.getByRole('link', { name: 'แก้ไขเอกสาร' }).click()
  const replacementPromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes(`/api/v1/applications/${applicationId}/documents/`),
  )
  await page.locator(`#file-${correctionDocumentTypeId}`).setInputFiles({
    name: 'corrected-evidence.png',
    mimeType: 'image/png',
    buffer: validPng,
  })
  expect((await replacementPromise).ok()).toBeTruthy()
  await page.goto(`/applications/${applicationId}/review`)
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'ส่งเอกสารแก้ไข' }).click()
  await page.waitForURL(new RegExp(`/applications/${applicationId}/submitted$`))
  await expect(page.getByRole('heading', { name: /ส่งเอกสารแก้ไขแล้ว/ })).toBeVisible()
  await signOut(page)

  await page.goto('/login?intent=officer&redirect=/officer/applications')
  await signIn(page, 'officer.patong@example.test')
  await openOfficerApplication(page, propertyName)
  await expect(
    page.locator(`[data-testid="document-review-form"][data-document-type-id="${correctionDocumentTypeId}"]`),
  ).toHaveCount(1)
  const replacementDocumentId = await page
    .locator(`[data-testid="document-review-form"][data-document-type-id="${correctionDocumentTypeId}"]`)
    .getAttribute('data-document-id')
  expect(replacementDocumentId).toBeTruthy()
  await reviewDocument(page, replacementDocumentId ?? '', 'APPROVED')
  await page.getByRole('button', { name: 'อนุมัติและออกใบอนุญาต' }).click()
  await page.getByRole('button', { name: 'ยืนยันอนุมัติและออกใบอนุญาต' }).click()
  await expect(page.getByText(/อนุมัติคำขอและสร้างใบอนุญาตแล้ว/).last()).toBeVisible()
  await signOut(page)

  await page.goto('/login?intent=applicant&redirect=/applications')
  await signIn(page, 'applicant@example.test')
  await page.getByLabel('รายการที่ต้องการดู').selectOption('completed')
  const approvedCard = await applicationCard(page, propertyName)
  await approvedCard.getByRole('link', { name: 'ติดตามคำขอนี้' }).click()
  await expect(page.getByText('คำขอได้รับอนุมัติ').first()).toBeVisible()
  await page.getByRole('link', { name: 'เปิดใบอนุญาต/เลขอ้างอิงสำหรับพิมพ์' }).click()
  await expect(page.locator('article').getByText(/^LIC-/)).toBeVisible()
  await page.emulateMedia({ media: 'print' })
  await expect(page.getByRole('button', { name: 'พิมพ์' })).toBeHidden()
  await page.emulateMedia({ media: 'screen' })
  await signOut(page)

  await page.goto('/login?intent=central&redirect=/central/overview')
  await signIn(page, 'central@example.test')
  await expect(page.getByRole('heading', { name: /ภาพรวม/ })).toBeVisible()
  await expect(page.locator('[id^="authority-tile-"]')).toHaveCount(19)
  expect(await centralApprovedCount(page)).toBe(approvedBefore + 1)
})

test('basic mobile, keyboard, language and role-boundary smoke checks', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto('/')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'ข้ามไปยังเนื้อหาหลัก' })).toBeFocused()
  await page.getByLabel('ภาษา').selectOption('en')
  await expect(page.getByRole('heading', { name: 'Welcome to HoTLinE Doc' })).toBeVisible()

  await page.goto('/login?intent=central&redirect=/central/overview')
  await page.getByLabel('Email').fill('central@example.test')
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((url) => url.pathname !== '/login')
  await page.goto('/officer/applications')
  await expect(page).toHaveURL(/\/forbidden$/)
})
