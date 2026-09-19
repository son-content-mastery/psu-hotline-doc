# Central province overview

## Purpose and route

- Suggested route: `/central/overview`
- Authentication: `CENTRAL_OFFICER`
- Main task: understand province-wide application volume and bottlenecks.

The MVP is an aggregate overview, not a business-intelligence suite. Central Officers must not make decisions on individual applications. Backend summary/report permission is mandatory; frontend routing is not authorization.

## Entry and scope

The homepage central CTA requires login, then routes an authorized Central Officer here. A user without central permission sees no summary data. The heading and supporting text state that figures cover the configured province (Phuket for seeded demo data) and show the data retrieval/as-of time.

The page does not link to officer review actions or expose applicant documents. An authority tile may open aggregate detail for that area, but it must never become an individual-application drilldown.

## Required top-level counters

Show exactly these four prominent summary measures first:

1. `คำขอทั้งหมด` / `Total applications`
2. `รอเจ้าหน้าที่ตรวจสอบ` / `Waiting for review`
3. `รอผู้ยื่นแก้ไข` / `Waiting for applicant revision`
4. `อนุมัติแล้ว` / `Approved`

Display the numeric value and text label together. Do not communicate category by color alone. Each value comes directly from the central summary API's documented aggregation; Vue must not fetch all applications and count them client-side.

The API contract must define which statuses contribute to each counter. The UI must not invent mappings. If counters overlap by domain definition, explain that near the figures; otherwise treat them as independently reported metrics rather than implying they add to the total.

## Required breakdowns

After the counters, show these three sections:

### By property type

A simple table with localized property type and application count. Unknown/unresolved classifications use a localized “รอยืนยันประเภท” / “Classification pending” row supplied or safely derived from an aggregate key, never a raw code.

### By LocalAuthority

A simple table with LocalAuthority name and application count. To prevent the overview from becoming a long wall of rows, show the top five ranked authorities by default and place an explicit **ดูเพิ่มเติม** / **View more** control with an icon and remaining-count text immediately after those rows. Expanding reveals the rest in place and keeps the collapse control below the expanded list; collapsing returns to the preview. The 19 seeded Phuket authorities are master data from the backend; do not hardcode their names or assume every authority has a nonzero row. The API decides whether zero-count authorities are included, and the UI states the convention.

### By current stage

A simple table with localized human-readable stage and count. Raw application status codes are mapped through i18n and never shown. Prefer grouped service stages when provided by the API rather than exposing every internal transition.

Optional horizontal bars may supplement each table when they improve scanning. Every bar must also display its category and exact value as text; tables remain available as the authoritative readable view.

An accessible schematic heat grid supplements the LocalAuthority table. It uses a light, restrained surface rather than a dark dashboard slab, and contains one labelled button tile per active configured authority. Tiles include zero-count authorities, show the exact value in text, and use color intensity only as a redundant cue. Activating a tile opens a modal aggregate panel with the area's four totals plus breakdowns by property type and current stage. The modal contains no applicant data, application identifiers, or links to individual records. It can be closed with its button, Escape, or the backdrop; focus moves to its heading when opened, stays within the modal, and returns to the originating tile when closed.

The grid must explicitly say that it is not a geographic boundary map. Do not draw approximate boundaries or call these 19 authorities “19 subdistricts.” A future choropleth requires a validated official GeoJSON/polygon source and a reviewed mapping between stable authority codes and non-overlapping jurisdiction geometry. No third-party chart package is needed for the schematic grid.

## Timing analytics

Show average wait per non-terminal stage with the number of contributing applications, followed by one unusually-old-work total and aggregate stage breakdown using the configured day threshold. Explain that the values come from server status history, are aggregate-only, and are intended to locate process bottlenecks rather than rank officers. Do not link these values to individual cases.

Below it, show the current monthly pseudonymous workload table only when the backend clears the minimum-group threshold. Use the rotating `OFF-` reference and counts for document reviews, application decisions, and total actions. When suppressed, explain the privacy threshold without showing the exact contributor count. Never add names, authority, sortable performance ranks, or links to officer records.

## Ordering and formatting

- Counters stay in the specified order.
- Property types and stages follow backend-defined domain order, not alphabetic ordering that changes by locale.
- LocalAuthorities default to descending count with name as stable tie-breaker, unless the API provides explicit order.
- Counts are locale-formatted whole numbers.
- Do not calculate percentages unless the API returns a denominator/definition; counts are sufficient for the MVP.
- Show a single `ข้อมูล ณ` / `Data as of` timestamp for the summary response.

## Refresh behavior

Fetch the summary on entry. Provide an explicit **รีเฟรชข้อมูล** / **Refresh data** button near the as-of time; polling is unnecessary for the hackathon demo.

During refresh, retain the prior numbers, mark them as the previous snapshot, and show a textual loading state. On success, update all counters and breakdowns atomically from one summary response so sections do not represent different moments. After the officer approves an application in the demo, a refresh must reflect the changed totals.

## Loading, empty, partial, and error states

- Initial loading: show page title, scope, and text stating that the summary is loading; do not display fake zeroes.
- Valid zero-data response: show `0` counters and an explicit “ยังไม่มีคำขอในช่วงข้อมูลนี้” / “No applications in this data set” message.
- Refresh error with prior data: retain it with its as-of time and a clear stale-data warning, plus retry.
- Initial error: show no misleading metrics; provide retry and support guidance.
- Missing breakdown/counter: label the summary incomplete and do not silently replace missing values with zero.
- Forbidden/session expired: remove protected data from view and route to safe login/authorization handling.
- Unknown aggregate code: use localized “ไม่ทราบประเภท/ขั้นตอน” / “Unknown category/stage,” never the raw value.

## Privacy and authorization

- The summary API returns aggregates only for the Central Officer MVP.
- Do not render applicant names, addresses, phone numbers, uploaded files, or individual application rows.
- Do not provide approve, reject, or request-revision controls.
- Do not derive hidden individual records from small cells or expose links containing application ids.
- Generic permission errors do not reveal whether protected data exists.

## Responsive and accessible presentation

- Present the four counters as one compact summary strip with subtle semantic markers and typographic hierarchy, rather than four visually competing promotional cards. At phone widths they stack or form a readable two-column grid without reordering.
- Breakdown sections stack vertically in the specified order.
- Tables have captions and scoped column headers. Numeric columns have clear headings and remain text-readable at 200% zoom.
- If a table needs horizontal scrolling at a very narrow width, place it in a labelled scroll region; prefer a two-column table that naturally fits.
- Bars are decorative supplements and hidden from assistive technology when the same values are in the table.
- Refresh status uses a polite live region; errors use an alert when immediate attention is required.
- Focus remains on the refresh button during routine refresh and receives a concise completion announcement rather than jumping to the top.
- Heat tiles are native buttons. The selected tile is understandable without color, and opening/closing the modal aggregate detail follows a predictable focus path.

## Acceptance criteria

1. Only an authorized Central Officer can retrieve and view the overview.
2. The four required counters appear first, in the specified order, using backend aggregates.
3. Breakdowns by property type, LocalAuthority, and current stage are present as simple readable tables; the LocalAuthority table defaults to a five-row preview with a keyboard-operable view-more control directly below the visible rows.
4. No complex BI chart, unvalidated geographic map, third-party visualization dependency, or individual decision action is present; the schematic heat grid and its clickable area detail remain aggregate-only and text-readable.
5. No applicant or individual-application data is exposed.
6. Raw type/status codes never appear; missing translations use safe localized fallback.
7. Empty, loading, stale, partial, permission, and server-error states cannot be confused with real zeroes.
8. One refresh updates all figures from a single coherent snapshot and reflects the demo approval.
9. All values remain understandable without color and usable by keyboard, screen reader, 200% zoom, and phone layout.
