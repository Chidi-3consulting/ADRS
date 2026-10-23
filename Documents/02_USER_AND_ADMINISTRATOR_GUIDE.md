# SafeData — User & Administrator Operational Guide

This document serves as the official operational manual for Platform Administrators, Data Protection Officers (DPOs), and Data Owners using the SafeData — Data Retention & Governance Platform.

---

## 1. User Roles & Permission Matrix

SafeData strictly enforces Role-Based Access Control (RBAC). Every user belongs to a specific organisation and holds one of three roles. Additionally, a **Platform Admin** flag grants super-admin capabilities across all tenants.

| Privilege / Action | Admin | DPO | Data Owner | Platform Admin |
| :--- | :---: | :---: | :---: | :---: |
| **Manage Users & Invite New Members** | ✅ | ❌ | ❌ | ✅ |
| **Configure System & SMTP Settings** | ✅ | ❌ | ❌ | ✅ |
| **Subscription & Licence Management** | ✅ | ❌ | ❌ | ✅ |
| **Billing & Payment Management** | ✅ | ❌ | ❌ | ✅ |
| **API Keys & Connected Systems** | ✅ | ❌ | ❌ | ✅ |
| **Create & Edit Data Categories** | ✅ | ✅ | ❌ | ✅ |
| **Manage Category Retention Rules** | ✅ | ✅ | ❌ | ✅ |
| **Place & Lift Legal Holds** | ✅ | ✅ | ❌ | ✅ |
| **Approve Dual-Approval Disposals** | ✅ | ✅ | ❌ | ✅ |
| **Manage Breach Incidents** | ✅ | ✅ | ❌ | ✅ |
| **Manage DPIA Assessments** | ✅ | ✅ | ❌ | ✅ |
| **Manage RoPA Register** | ✅ | ✅ | ❌ | ✅ |
| **Create & Edit Data Records** | ✅ | ✅ | ✅ (Own dept) | ✅ |
| **Trigger Category Recalculations** | ✅ | ✅ | ❌ | ✅ |
| **View Audit Trail & Export Reports** | ✅ | ✅ | ❌ | ✅ |
| **Manage All Organisations (Platform)** | ❌ | ❌ | ❌ | ✅ |
| **Generate Platform Licence Keys** | ❌ | ❌ | ❌ | ✅ |

---

## 2. Organisation Onboarding & Registration

### 2.1 Multi-Tenant Organisation Setup
1. Navigate to `/register` in your web browser.
2. Enter the **Organisation Name**, **Primary Domain**, **Country** (40+ countries supported), and Admin contact details.
3. The platform creates the Organisation entity in `trial` status with a **14-day free trial**.
4. The primary Admin account is provisioned automatically.
5. Jurisdiction-specific retention categories are **automatically seeded** based on the selected country (e.g., Nigeria → NDPR categories, UK → GDPR categories, US → CCPA categories).

### 2.2 Email Verification
1. After registration, users must verify their email address via a token-based verification link.
2. Verification tokens expire after **24 hours**.
3. Until verified, authenticated users are redirected to `/verify_email` and cannot access other features.

### 2.3 Initial Setup Wizard
1. On first login, if the system has not been configured, users are redirected to `/setup`.
2. The setup wizard configures essential system settings.
3. Once complete, the `setup_complete` flag is set and the guard is removed.

### 2.4 User Provisioning via Invitation
1. Log in as an **Admin** and navigate to **Settings → User Management** (`/users`).
2. Click **Invite User**.
3. Provide Full Name, Email, and Role (`admin`, `dpo`, or `data_owner`).
4. The system generates a **token-based invitation link** with an expiry date.
5. The invited user receives the link, navigates to `/invite/accept`, and creates their account.
6. Invitations can be **revoked** by the Admin before acceptance.

### 2.5 Password Policy
- Minimum **10 characters**.
- Must include **both letters and numbers**.
- Users with `must_change_password = True` are forced to update their password before accessing any other page.

### 2.6 Two-Factor Authentication (2FA)
1. Navigate to **Settings → Security** (`/settings?tab=twofa`).
2. Click **Enable 2FA** to generate a TOTP secret.
3. Scan the QR code with an authenticator app (Google Authenticator, Authy, etc.).
4. Enter the 6-digit code to confirm setup.
5. **8 recovery codes** are generated and displayed once — store them securely.
6. If the organisation policy requires 2FA for certain roles, users are redirected to enable it on login.

---

## 3. Managing Data Categories (Retention Register)

Data Categories form the core policy register of SafeData. Every record ingested must be bound to an active Category.

### 3.1 Creating a Data Category
1. Navigate to **Data Categories → Add Category** (`/categories/create`).
2. Complete the required fields:
   - **Category Name**: e.g., *Customer KYC Documents*.
   - **Compliance Framework**: Auto-detected based on your organisation's country. Common values: GDPR, NDPR, CCPA, LGPD, POPIA, PDPA, DPDP, PDPL, PIPEDA, APPs, EGDPL, BOTH.
   - **Lawful Basis**: Choose from:
     - `legal_obligation`
     - `contract`
     - `consent`
     - `legitimate_interest`
     - `vital_interest`
     - `public_task`
   - **Disposal Trigger**:
     - `date_based`: Clock runs immediately from record collection date.
     - `consent_withdrawal`: Clock starts when consent withdrawal is logged.
     - `account_closure`: Clock starts when account termination event is received (typically via Enterprise API).
   - **Retention Period**: Specify duration in days (e.g., `1825` for 5 years) and a human-readable label (`5 Years`).
   - **Disposal Method**: Select action upon expiration:
     - `delete`: Soft-delete record and purge associated binary attachments.
     - `anonymise`: Scrub PII columns while retaining statistical data.
     - `archive`: Transition record state to long-term immutable archive.
   - **Requires Dual Approval**: Enable toggle for high-risk datasets.
   - **Review Frequency**: `monthly`, `quarterly`, or `annually`.
   - **Data Owner**: Assign an internal user responsible for this category.
3. Click **Save Category**.

### 3.2 Category Retention Rules
Each category can have **multiple retention rules** (`CategoryRetentionRule`) that allow different retention periods based on institution type (banking, insurance, healthcare, etc.). Rules include:
- **Rule Name**: Descriptive label.
- **Institution Type**: `all`, `banking`, `insurance`, `healthcare`, `public_sector`, `telecom`, `retail`, or `general`.
- **Processing Purpose**: Description of the specific processing activity.
- **Priority / Sort Order**: Determines rule evaluation order.
- **Is Default**: Whether this is the fallback rule when no specific rule matches.

### 3.3 Recalculation on Rule Changes
When a category's retention rules are modified, all affected records are queued in the **Recalculation Queue** (`/recalculations`). An Admin or DPO must review each entry and choose:
- **Recalculate**: Apply the new retention end date.
- **Keep Original**: Preserve the existing retention end date.

---

## 4. Records Lifecycle Management

### 4.1 Ingesting Records Manually
Data Owners and DPOs can register individual records into the portal:
1. Navigate to **Data Records → Add Record** (`/records/create`).
2. Select the **Data Category**. The system automatically pulls the associated lawful basis and retention period.
3. Optionally select a specific **Retention Rule** if the category has multiple rules.
4. Enter the **Record Reference** (e.g., Account Number, Employee ID, Application Ref).
5. Select the **Collection Date**.
6. Optional: Input **Data Subject Type** (e.g., `Customer`, `Employee`) and additional notes.
7. Submit the form. The system automatically computes `retention_end_date`.

### 4.2 File Attachments
Records support **file attachments** (evidence documents, scanned forms, etc.):
- Files are stored in `storage/attachments/` with unique filenames.
- Attachments track original filename, MIME type, file size, and uploader.
- When a record is disposed via the `delete` method, associated attachments are purged.

### 4.3 Record Status Transitions

```
                            Collection Date
  ┌──────────┐            ┌──────────┐
  │   New    │ ─────────> │  active  │
  └──────────┘            └─────┬────┘
                                │
              Retention End Date Approaching / Reached
                                │
                                ▼
  ┌─────────────────┐    ┌──────────────┐    ┌───────────────────┐
  │   legal_hold    │    │  due_review  │───>│ disposal_requested│
  └─────────────────┘    └──────────────┘    └────────┬──────────┘
         ▲                                            │
         │                               Approved / Auto-Disposed
         │                                            │
  Legal Hold Applied                                  ▼
                                         ┌──────────────┐
                                         │   disposed   │
                                         └──────────────┘
```

- **active**: Record is within its valid retention lifespan.
- **due_review**: Record has reached its expiration date and is pending verification or dual-approval sign-off.
- **disposal_requested**: Disposal has been explicitly requested and is awaiting processing.
- **legal_hold**: Record is under legal hold (also tracked via the `legal_hold` boolean flag).
- **disposed**: Record has undergone final deletion, anonymisation, or archiving.

---

## 5. Dual-Approval & Expiration Workflows

When records in a `requires_dual_approval = True` category expire:
1. They are flagged as `due_review` by the background retention engine.
2. They appear in the DPO/Admin dashboard under **Pending Disposals**.
3. A DPO or Admin must inspect the record reference and initiate **Process Disposal**.
4. The `execute_disposal()` function performs the designated action (`delete`, `anonymise`, or `archive`), records an immutable audit event, and (for Enterprise tier) queues outbound disposal dispatches to connected systems.

Records in categories **without** dual approval are auto-disposed by the engine when their retention end date passes.

---

## 6. Managing Legal Holds

To prevent data disposal during active litigation, regulatory inquiries, or internal investigations:
1. Navigate to **Data Records** and select the target record.
2. Click **Place Legal Hold**.
3. Enter the mandatory **Reason for Hold** and reference case number.
4. The record's `legal_hold` flag is set to `True`. The background engine skips this record during all disposal runs.
5. To release, click **Lift Legal Hold** and provide formal DPO/Admin sign-off justification.
6. The `legal_hold_lifted_at` timestamp is recorded, and an immutable audit entry is created.

---

## 7. Retention Run, Consent Management and Simulations (Administrators)

The **collection queue** is the set of records whose retention period has been reached (retention end date is today or earlier). Records still inside their retention period are never collected.

1. **Retention: run & simulate** (`/admin/retention`): shows the collection queue. *Simulate* shows exactly what a run would do (flag, dispose, wait for approval, blocked by legal hold or freeze) and changes nothing. *Run now* does it for real after you type `RUN`.
2. **Consent management** (`/admin/consent`): lists records held on a consent basis. *Record withdrawal* starts the grace period; the record is disposed when it ends.
3. **Simulate consent removal** shows, per record, the date it would be disposed if consent were withdrawn now, or why nothing would happen (legal hold, emergency freeze, category not consent-triggered). It changes nothing.

Every simulation and every real run is written to the audit trail.

---

## 8. Bulk CSV Import Utility

1. Navigate to **Bulk Import** (`/import`).
2. Download the standard CSV Template.
3. Populate record details (`category_id`, `record_reference`, `collection_date`, `data_subject_type`, `notes`).
4. Upload the CSV. SafeData performs a **Two-Pass Import**:
   - **Pass 1 (Validation)**: Checks date formatting, category validity, and duplicate reference constraints.
   - **Pass 2 (Execution)**: Commits clean rows into `data_records` and generates a detailed job summary.
5. The **Import Job** record tracks: `total_rows`, `valid_rows`, `imported_rows`, `skipped_rows`, `error_rows`, and a detailed `error_report` (JSON).

---

## 9. Notifications & Escalation

SafeData includes an in-app notification centre accessible from the navigation bar.

- **Review Due Notifications**: When records transition to `due_review`, the category owner is notified. If no owner is assigned, notifications fall back to all **DPO** users.
- **Escalation Alerts**: If `due_review` records remain unactioned beyond the escalation window (default: 14 days), **Admin** users receive escalation notifications.
- **Follow-Up Reminders**: Unread review/escalation notifications older than 3 days trigger automatic follow-up notifications.

---

## 10. Session Management & Security

- **Idle Timeout**: Sessions expire after **30 minutes** of inactivity.
- **Absolute Timeout**: Sessions have a hard cap of **8 hours** regardless of activity.
- **Expired sessions** redirect to `/login?expired=1`.
- **CSRF Protection**: All form submissions require a valid CSRF token. API endpoints are exempt (they use Bearer token auth).
- **Subscription Enforcement**: Organisations with `suspended` status or expired trials are redirected to `/billing`.
