# Prompt 09 — DSAR Tracking Module (C1)

## Context
Data Subject Access Request management. Access: Admin + DPO only.
GDPR Art. 12: respond within 30 days. NDPR: same standard applies.
Reference: `dsar_requests` table in schema.sql.

---

## Pages to build

### `src/pages/dsar/index.php`
**KPI cards (4):**
- 📬 Open Requests
- ⚠️ Due Within 5 Days (amber)
- 🚨 Overdue (red)
- ✅ Completed This Month

**Filter bar:** Status / Request Type / Framework / Assigned To / Date range

**Table columns:**
| Reference | Type | Data Subject | Framework | Received | Due Date | Days Left | Status | Assigned | Actions |

- Reference: `DSAR-2025-0001` in monospace
- Type badge: Access=blue, Erasure=red, Rectification=amber, etc.
- Days Left pill: same colour logic as retention schedule
- Overdue rows: entire row red background
- Actions: View, Edit, Complete, Assign

---

### `src/pages/dsar/create.php`
**Form fields:**
- Request Type* (select with icons and plain-English descriptions)
- Compliance Framework* (GDPR / NDPR / Both)
- Data Subject Name*
- Data Subject Email
- Data Subject Phone
- Data Subject Type (Customer / Employee / Supplier / Other)
- Received Date* (default today)
- Description* (what they are requesting — free text)
- Assign To (select from Admin/DPO users)
- Internal Notes

**On save:**
- Auto-generate reference using `generate_dsar_reference($pdo)`
- Calculate `due_date = received_date + 30 days`
- Insert record
- Log `dsar_created` to audit_log
- Send `email_dsar_received()` notification to assigned user and all DPOs
- Flash: "DSAR {reference} created. Response due by {due_date}."

---

### `src/pages/dsar/view.php`
**Sections:**
1. **Request Summary** — all fields in definition list
2. **Status Timeline** — horizontal visual:
   `Received → Identity Check → In Progress → Completed`
   Current step highlighted. Show dates at each completed step.
3. **Days Remaining Countdown** — large prominent display:
   - Green: > 10 days
   - Amber: 5–10 days
   - Red: < 5 days
   - Dark red: OVERDUE
4. **Identity Verification Panel:**
   - Toggle: Verified / Unverified
   - On verify: set `identity_verified=1, identity_verified_at, identity_verified_by`
   - Log to audit_log
5. **Extension Panel** (if status != completed/rejected):
   - "Request Extension" button — opens modal
   - Extension reason (required), new due date (max received_date + 90 days)
   - Sets `extended_due_date`, `extension_reason`, `status = 'extended'`
6. **Response Notes** — rich textarea for DPO to document what was provided
7. **Action buttons:**
   - Update Status
   - Mark Complete (requires response_notes to be filled)
   - Reject (requires rejection_reason)
8. **Audit History** — last 10 entries for this DSAR

---

### `src/pages/dsar/edit.php`
- Update: type, framework, subject details, assigned_to, internal notes
- Cannot change: reference, received_date, due_date (date integrity)
- Log `dsar_updated` with before/after JSON

---

### `src/pages/dsar/complete.php` (POST handler)
- Validate `response_notes` is not empty
- Set `status = 'completed'`, `completed_at = NOW()`
- Log `dsar_completed` to audit_log
- Send completion notification to assigned user
- Redirect to view.php with flash

---

### `src/pages/dsar/export.php`
- CSV export of all DSARs (filtered by year or status)
- Filename: `dsar-register-{year}.csv`
- Log `export_generated`

---

## Notification templates (add to `email_templates.php`)

### `email_dsar_received($reference, $type, $subject_name, $due_date, $assigned_to, $url)`
Subject: "New DSAR Received — {reference} — Response Due {due_date}"
Content:
- Request details table
- Due date prominently displayed
- CTA: "Open DSAR Record"
- Compliance note: "GDPR Article 12 requires a response within 30 days of receipt."

### `email_dsar_due_soon($reference, $type, $subject_name, $due_date, $days_remaining, $url)`
Subject: "⚠️ DSAR Due in {days} Days — {reference}"

### `email_dsar_overdue($reference, $type, $subject_name, $due_date, $days_overdue, $url)`
Subject: "🚨 OVERDUE DSAR — {reference} — {days} Days Past Deadline"
- Red alert styling throughout email

---

## Dashboard integration
Add to Admin/DPO dashboard (Prompt 08):
- DSAR summary card: Open / Due Soon / Overdue counts
- "Open DSARs" quick-action link in sidebar
