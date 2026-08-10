# Prompt 02 — Authentication System v4 (BUG-04 FIXED)
# Adds: forgot_password.php + reset_password.php (were missing entirely)

> **Implementation Note:** This specification was originally written with PHP code examples.
> The ADRS codebase has been fully implemented in **Python (FastAPI + SQLAlchemy + Jinja2)**.
> The business logic, rules, and requirements documented below remain the authoritative
> specification. See `retention_py/` for the Python implementation.

---

## Pre-requisites
Prompt 01 complete. `src/includes/auth.php`, `db.php`, `helpers.php`,
`mailer.php`, `email_templates.php` all exist with full implementations.

---

## 1. `src/pages/login.php`

Full-page login form (no sidebar). Layout: centred card max-width 420px.

**Fields:** Email, Password (show/hide toggle), Remember Me checkbox (stores
email in cookie 30 days — NOT password), CSRF hidden field.

**POST logic:**
- `csrf_verify()`
- Validate email format with `filter_input(INPUT_POST, 'email', FILTER_VALIDATE_EMAIL)`
- Rate limit: 5 failed attempts → 15-minute lock (session-based counter)
- Call `login_user($pdo, $email, $password)` from auth.php
- Success → `redirect(APP_URL . '/src/pages/dashboard.php')`
- Failure → flash error "Invalid email or password" (never say which field)
- Pre-fill email from Remember Me cookie if present
- Link: "Forgot your password?" → `forgot_password.php`

---

## 2. `src/pages/forgot_password.php`  ← BUG-04 FIX (was missing)

**GET:** Show a simple form with one field: Email address.

**POST logic:**
```php
csrf_verify();
$email = filter_input(INPUT_POST, 'email', FILTER_VALIDATE_EMAIL);

// ALWAYS show the same message regardless of whether email exists
// (prevents user enumeration)
$message = "If that email address is in our system, you will receive a reset link shortly.";

if ($email) {
    $stmt = $pdo->prepare("SELECT id, name FROM users WHERE email = ? AND is_active = 1 AND deleted_at IS NULL");
    $stmt->execute([$email]);
    $user = $stmt->fetch();

    if ($user) {
        // Generate raw token (64 hex chars = 32 bytes)
        $raw_token = bin2hex(random_bytes(32));

        // Expire any existing unused tokens for this email
        $pdo->prepare("UPDATE password_resets SET used = 1 WHERE email = ? AND used = 0")
            ->execute([$email]);

        // Insert new token (hashed)
        $pdo->prepare(
            "INSERT INTO password_resets (email, token_hash, expires_at)
             VALUES (?, ?, DATE_ADD(NOW(), INTERVAL 1 HOUR))"
        )->execute([$email, hash('sha256', $raw_token)]);

        // Build reset URL
        $reset_url = APP_URL . '/src/pages/reset_password.php?token=' . urlencode($raw_token) . '&email=' . urlencode($email);

        // Send email
        $subject = 'Password Reset Request — 3Consulting Data Retention System';
        $html = email_password_reset($user['name'], $reset_url, 60);
        send_notification($email, $user['name'], $subject, $html);

        log_audit($pdo, 'password_reset_requested', 'user', $user['id'], null, null, get_client_ip());
    }
}

flash('info', $message);
redirect(APP_URL . '/src/pages/forgot_password.php');
```

**UI:** Branded card layout, info alert after submit, link back to login.

---

## 3. `src/pages/reset_password.php`  ← BUG-04 FIX (was missing)

**GET:** Validate token from URL query string before showing form.
```php
$raw_token = $_GET['token'] ?? '';
$email     = $_GET['email'] ?? '';

if (!validate_reset_token($pdo, $email, $raw_token)) {
    flash('error', 'This password reset link is invalid or has expired. Please request a new one.');
    redirect(APP_URL . '/src/pages/forgot_password.php');
}
// If valid: show password reset form
```

**Form fields:**
- New Password (min 10 chars, requires uppercase + number + special char)
- Confirm Password
- Hidden: token, email
- CSRF field

**POST logic:**
```php
csrf_verify();
$raw_token = $_POST['token'] ?? '';
$email     = $_POST['email'] ?? '';
$new_pass  = $_POST['password'] ?? '';
$confirm   = $_POST['confirm_password'] ?? '';

// Re-validate token
if (!validate_reset_token($pdo, $email, $raw_token)) {
    flash('error', 'Reset link expired. Request a new one.');
    redirect(APP_URL . '/src/pages/forgot_password.php');
}

// Validate password strength
$errors = [];
if (strlen($new_pass) < 10)                        $errors[] = 'Minimum 10 characters';
if (!preg_match('/[A-Z]/', $new_pass))              $errors[] = 'Must contain an uppercase letter';
if (!preg_match('/[0-9]/', $new_pass))              $errors[] = 'Must contain a number';
if (!preg_match('/[^A-Za-z0-9]/', $new_pass))       $errors[] = 'Must contain a special character';
if ($new_pass !== $confirm)                         $errors[] = 'Passwords do not match';

if (empty($errors)) {
    $hash = password_hash($new_pass, PASSWORD_BCRYPT);
    $pdo->prepare("UPDATE users SET password_hash = ?, updated_at = NOW() WHERE email = ?")
        ->execute([$hash, $email]);
    consume_reset_token($pdo, $email);

    // Get user ID for audit log
    $user = $pdo->prepare("SELECT id FROM users WHERE email = ?")->execute([$email])
            ? $pdo->query("SELECT id FROM users WHERE email = " . $pdo->quote($email))->fetch() : null;
    // Better: use prepared statement fetch properly
    log_audit($pdo, 'password_reset_completed', 'user', $user['id'] ?? null, null, null, get_client_ip());

    flash('success', 'Password reset successfully. Please sign in with your new password.');
    redirect(APP_URL . '/src/pages/login.php');
}
// If errors: re-show form with error list
```

**UI:** Same card layout as login. Show password strength indicator (JS).
Show each validation error as a red list item below the password field.

---

## 4. `src/pages/logout.php`
```php
require_once ...auth.php;
session_name(SESSION_NAME); session_start();
if (is_logged_in()) {
    logout_user($pdo); // logs to audit_log, destroys session
}
redirect(APP_URL . '/src/pages/login.php');
```
Flash message: "You have been signed out securely."

---

## 5. `src/pages/users/index.php`
Admin-only. User list with: Name, Email, Role (badge), Status, Last Login, Actions.
- Role badges: admin=danger, dpo=primary, data_owner=secondary
- Actions: Edit, Deactivate/Activate, Delete (soft-delete + confirmation modal)
- Search filter: JS client-side by name/email
- Pagination: 25 rows server-side

---

## 6. `src/pages/users/create.php`
Admin-only. Fields: Full Name*, Email* (unique), Role*, Temporary Password*
(min 10 chars, uppercase + number + special), Confirm Password.
- Hash with `PASSWORD_BCRYPT`
- Log `user_created` to audit_log
- Send welcome email via `email_welcome_user()` template
- Flash success, redirect to index

---

## 7. `src/pages/users/edit.php`
Admin-only. Pre-populated form. Editable: Name, Email, Role, Active status.
Optional password reset section (only update hash if new password fields filled).
JSON diff before/after logged to audit_log on any change.
If `owner_id` category assignment changes: notify new owner by email.

---

## 8. `src/pages/users/delete.php`
POST handler. Admin only.
- Soft-delete: `deleted_at = NOW()`, `is_active = 0`
- Block: cannot delete own account
- Block: cannot delete last Admin
- Warn: if user owns categories → show "Reassign their categories first"
  (do not hard-block, but flash a warning)
- Log `user_deleted`

---

## auth.php — complete function list

```php
login_user(PDO $pdo, string $email, string $password): bool
logout_user(PDO $pdo): never
require_login(): void
require_role(string ...$roles): void
current_user(): array
has_role(string ...$roles): bool
is_logged_in(): bool

// Password reset (BUG-04 FIX — these were referenced but not defined)
create_password_reset_token(PDO $pdo, string $email): string
validate_reset_token(PDO $pdo, string $email, string $raw_token): bool
consume_reset_token(PDO $pdo, string $email): void
```

All functions must have PHPDoc comments. No class — plain functions only.

---

## Security checklist for this module
- Session cookie: Secure + HttpOnly + SameSite=Strict (set in index.php)
- Never reveal which field (email vs password) caused login failure
- Token URL uses `urlencode()` — raw token in URL, hash stored in DB
- Password reset page re-validates token on POST (not just GET)
- Rate limiting on login: 5 failures → 15-min lock (session counter)
- `bin2hex(random_bytes(32))` for all token generation — cryptographically secure
