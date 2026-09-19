# Public Licence Verification

## Route and audience

- Route: `/verify/{verification_token}`
- Audience: anyone scanning the printed QR code; no account is required.
- Source: `GET /api/v1/public/licenses/{verification_token}/`.

## Page contract

The page leads with a plain-language status—valid, expired, or notification recorded—then shows the artifact number, property display name/type, issuing authority, issue date, and expiry when applicable. Status always has visible text and never depends on colour alone.

The page must not show applicant identity, application reference, exact address, fee, documents, reasons, or audit history. An unknown or malformed token gets a generic not-found message that does not suggest sequential enumeration.

The private print-friendly artifact includes the server-generated QR SVG, a selectable verification link, descriptive alternative text, and a short privacy explanation. Printing must retain the QR and link while hiding application navigation and actions.
