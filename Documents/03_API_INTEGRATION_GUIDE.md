# SafeData Enterprise REST API — Developer Integration Guide

This guide provides technical specifications, authentication requirements, endpoint schemas, and code samples for integrating external enterprise software (CRMs, Core Banking Systems, HR Portals) with the **SafeData Enterprise REST API**.

---

## 1. Authentication & API Key Management

The SafeData REST API uses **Bearer Token Authentication** backed by SHA-256 API Key verification.

### 1.1 Generating API Keys
1. Log in to the SafeData Enterprise Web Portal as an **Admin**.
2. Navigate to **Integrations → API Keys** (`/integrations/keys`).
3. Click **Create API Key**. Select the Target Connected System, set a name, configure permissions, set rate limit (requests per minute), and optionally set an expiry date.
4. The system generates a raw API key prefixed with `SafeData_` (e.g., `SafeData_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4`).

> ⚠️ **CRITICAL SECURITY NOTE**: The raw API key is displayed **ONCE ONLY** upon creation. SafeData stores only the SHA-256 hash (`key_hash`) and a display prefix (`key_prefix`, first 12 characters) in the database. There is no way to recover the full key after creation.

### 1.2 API Key Properties

| Property | Description |
| :--- | :--- |
| `key_name` | Descriptive label for the key |
| `key_hash` | SHA-256 hash of the raw key (stored, never the raw key) |
| `key_prefix` | First 12 characters for display identification |
| `permissions` | JSON array of granted permissions |
| `rate_limit_per_min` | Maximum requests per minute (default: 60) |
| `is_active` | Whether the key is active or revoked |
| `expires_at` | Optional expiration timestamp |
| `last_used_at` | Timestamp of the last successful API call |

### 1.3 Including Keys in Request Headers
All requests to Enterprise endpoints (`/api/v1/*`) must pass the raw API key in the `Authorization` HTTP header:

```http
Authorization: Bearer SafeData_a1b2c3d4e5f6a7b8c9d0e1f2...
Content-Type: application/json
```

### 1.4 Authentication Errors
- **401 Unauthorized**: Missing or invalid `Authorization` header, invalid/revoked key, or expired key.
- All successful API calls update the key's `last_used_at` timestamp.
- All API calls (successful and failed) are logged in the `IntegrationLog` with direction, endpoint, method, status code, request/response bodies, records affected, and duration.

---

## 2. API Endpoints Reference

Base URL: `https://your-SafeData-domain.com/api/v1` (or `http://localhost:8200/api/v1` for local dev)

### 2.1 Health Check
- **Endpoint**: `GET /api/v1/health`
- **Authentication**: None required
- **Response**:
```json
{
  "status": "healthy",
  "service": "SafeData API v1"
}
```

---

### 2.2 List Data Categories
- **Endpoint**: `GET /api/v1/categories`
- **Authentication**: Bearer Token
- **Description**: Returns all active retention categories configured for the organisation.
- **Response (200 OK)**:
```json
{
  "categories": [
    {
      "id": 14,
      "name": "Customer Account KYC Records",
      "framework": "NDPR",
      "disposal_trigger": "account_closure",
      "retention_period_label": "5 Years"
    },
    {
      "id": 22,
      "name": "Marketing Subscriptions",
      "framework": "GDPR",
      "disposal_trigger": "consent_withdrawal",
      "retention_period_label": "1 Year"
    }
  ]
}
```

---

### 2.3 Single Record Ingestion
- **Endpoint**: `POST /api/v1/ingest`
- **Authentication**: Bearer Token
- **Request Body**:
```json
{
  "record_reference": "CUST-ACCT-884920",
  "category_id": 14,
  "collection_date": "2026-08-10",
  "data_subject_type": "Customer",
  "notes": "Opened savings account via mobile app"
}
```

- **Response (200 OK - Created)**:
```json
{
  "status": "success",
  "record_id": 4821
}
```

- **Response (200 OK - Duplicate Reference)**:
```json
{
  "status": "duplicate",
  "record_id": 4821,
  "message": "Record reference already exists."
}
```

- **Error Responses**:
  - `400 Bad Request`: Invalid date format or category not found.
  - `401 Unauthorized`: Invalid or missing API key.

---

### 2.4 Batch Record Ingestion
- **Endpoint**: `POST /api/v1/ingest/batch`
- **Authentication**: Bearer Token
- **Description**: Ingest multiple records in a single API call. Invalid entries are silently skipped.
- **Request Body**:
```json
{
  "records": [
    {
      "record_reference": "TX-2026-00192",
      "category_id": 8,
      "collection_date": "2026-08-01",
      "data_subject_type": "Customer"
    },
    {
      "record_reference": "TX-2026-00193",
      "category_id": 8,
      "collection_date": "2026-08-01",
      "data_subject_type": "Customer"
    }
  ]
}
```
- **Response (200 OK)**:
```json
{
  "status": "success",
  "processed": 2,
  "duplicates_skipped": 0
}
```

---

### 2.5 Consent Withdrawal Signal
- **Endpoint**: `POST /api/v1/consent/withdraw`
- **Authentication**: Bearer Token
- **Description**: Marks records as consent-withdrawn, triggering retention recalculation for consent-based categories.
- **Request Body**:
```json
{
  "record_reference": "USER-EMAIL-john.doe@example.com",
  "category_id": 22
}
```
- **Response (200 OK)**:
```json
{
  "status": "success",
  "updated_records": 1
}
```

- **Notes**:
  - `category_id` is optional. If omitted, all records matching the reference are updated.
  - Only records that have not already been disposed and do not already have a withdrawal timestamp are affected.
  - The system sets `consent_withdrawn_at` and recalculates `retention_end_date`.

---

### 2.6 Query Record Retention Status
- **Endpoint**: `GET /api/v1/records/status?record_reference=CUST-ACCT-884920`
- **Authentication**: Bearer Token
- **Optional Query Parameter**: `category_id` — filter to a specific category.
- **Response (200 OK)**:
```json
{
  "record_id": 4821,
  "record_reference": "CUST-ACCT-884920",
  "status": "active",
  "collection_date": "2026-08-10",
  "retention_end_date": "2031-08-10",
  "legal_hold": false
}
```

---

### 2.7 Account Closure Termination Signal
- **Endpoint**: `POST /api/v1/records/terminate`
- **Authentication**: Bearer Token
- **Description**: Informs SafeData that a customer account or employee relationship has ended. Starts the retention clock for categories using `account_closure` disposal triggers.
- **Request Body**:
```json
{
  "external_ref": "CUST-ACCT-884920",
  "termination_date": "2026-08-10"
}
```
- **Response (200 OK)**:
```json
{
  "status": "processed",
  "external_ref": "CUST-ACCT-884920",
  "matched_count": 1,
  "updated_records": [
    {
      "record_id": 4821,
      "category": "Customer Account KYC Records",
      "retention_end_date": "2031-08-10"
    }
  ]
}
```

- **Notes**:
  - `termination_date` is optional (defaults to today).
  - Only affects records under categories with `disposal_trigger = "account_closure"` that do not already have a `retention_end_date`.
  - Each matched record generates an audit log entry with `action: "account_terminated"`.

---

### 2.8 Confirm Record Disposal
- **Endpoint**: `POST /api/v1/records/disposed`
- **Authentication**: Bearer Token
- **Description**: Explicitly request disposal of records matching an external reference. SafeData executes the disposal method configured for each record's category.
- **Request Body**:
```json
{
  "external_ref": "CUST-ACCT-884920"
}
```
- **Response (200 OK)**:
```json
{
  "status": "processed",
  "external_ref": "CUST-ACCT-884920",
  "matched_count": 1,
  "disposed_count": 1
}
```

- **Notes**:
  - Records on legal hold are skipped.
  - Records already disposed are skipped.
  - The disposal method (delete/anonymise/archive) is determined by the record's category configuration.

---

## 3. Integration Logging

Every API call is automatically logged in the `IntegrationLog` table with the following data:

| Field | Description |
| :--- | :--- |
| `system_id` | Connected system that owns the API key |
| `api_key_id` | Specific API key used |
| `direction` | `inbound` (client → SafeData) or `outbound` (SafeData → client webhook) |
| `endpoint` | The API path called |
| `method` | HTTP method (GET, POST, etc.) |
| `status_code` | HTTP response status |
| `request_body` | Logged request payload (JSON) |
| `response_body` | Logged response payload (JSON) |
| `records_affected` | Number of records created/updated/disposed |
| `duration_ms` | Request processing time in milliseconds |
| `ip_address` | Client IP address |

Integration logs are viewable in the SafeData portal at **Integrations → API Logs** (`/integrations/logs`).

---

## 4. Integration Code Samples

### 4.1 Python (`httpx`)
```python
import httpx

API_URL = "https://retention.3consult-ng.com/api/v1/ingest"
API_KEY = "SafeData_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "record_reference": "POL-2026-99120",
    "category_id": 4,
    "collection_date": "2026-08-10",
    "data_subject_type": "PolicyHolder",
    "notes": "Life insurance agreement signed"
}

with httpx.Client() as client:
    response = client.post(API_URL, json=payload, headers=headers)
    print(response.status_code, response.json())
```

### 4.2 cURL (CLI)
```bash
curl -X POST "https://retention.3consult-ng.com/api/v1/ingest" \
     -H "Authorization: Bearer SafeData_a1b2c3d4e5f6a7b8c9d0e1f2..." \
     -H "Content-Type: application/json" \
     -d '{
       "record_reference": "POL-2026-99120",
       "category_id": 4,
       "collection_date": "2026-08-10",
       "data_subject_type": "PolicyHolder"
     }'
```

### 4.3 Node.js (`axios`)
```javascript
const axios = require('axios');

async function ingestRecord() {
  const url = 'https://retention.3consult-ng.com/api/v1/ingest';
  const apiKey = 'SafeData_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4';

  try {
    const res = await axios.post(url, {
      record_reference: 'POL-2026-99120',
      category_id: 4,
      collection_date: '2026-08-10',
      data_subject_type: 'PolicyHolder'
    }, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });
    console.log('Ingest Response:', res.data);
  } catch (err) {
    console.error('Ingest Error:', err.response ? err.response.data : err.message);
  }
}

ingestRecord();
```
