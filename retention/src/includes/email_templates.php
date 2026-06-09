<?php
require_once __DIR__ . '/helpers.php';

/**
 * Branded HTML email templates (pure string builders — unit-testable).
 * Notifications carry subject + message; render_notification_email() wraps them
 * in the branded layout. Specific transactional templates have their own builders.
 */

/** Wrap body HTML in the 3Consulting-branded email shell. */
function email_layout(string $title, string $body_html): string {
    $appName = defined('APP_NAME') ? APP_NAME : 'ADRS';
    $year = date('Y');
    return '<!doctype html><html><body style="margin:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif;">'
        . '<div style="max-width:600px;margin:0 auto;background:#fff;">'
        . '<div style="background:#C85C1A;color:#fff;padding:18px 24px;font-size:20px;font-weight:bold;">ADRS</div>'
        . '<div style="padding:24px;color:#222;">'
        . '<h2 style="color:#1A6187;margin-top:0;">' . escape_html($title) . '</h2>'
        . $body_html
        . '</div>'
        . '<div style="padding:16px 24px;background:#1A1A2E;color:#cfd2dc;font-size:12px;">&copy; ' . $year
        . ' 3Consulting Limited &middot; ' . escape_html($appName) . '</div>'
        . '</div></body></html>';
}

/** Render an email for a stored notification row (subject + message). */
function render_notification_email(array $notification): string {
    $msg = nl2br(escape_html($notification['message'] ?? ''));
    return email_layout($notification['subject'] ?? 'Notification', '<p>' . $msg . '</p>');
}

/** Password-reset email. Returns [subject, html]. */
function email_password_reset(string $name, string $reset_link): array {
    $body = '<p>Hello ' . escape_html($name) . ',</p>'
        . '<p>A password reset was requested for your ADRS account. This link is valid for 1 hour:</p>'
        . '<p><a href="' . escape_html($reset_link) . '" style="background:#C85C1A;color:#fff;padding:10px 18px;'
        . 'text-decoration:none;border-radius:4px;display:inline-block;">Reset your password</a></p>'
        . '<p>If you did not request this, you can safely ignore this email.</p>';
    return ['Reset your ADRS password', email_layout('Password reset', $body)];
}

/** Email verification for new registrations. Returns [subject, html]. */
function email_verification(string $name, string $verify_link): array {
    $body = '<p>Hello ' . escape_html($name) . ',</p>'
        . '<p>Welcome to ADRS. Please verify your email address to activate your account:</p>'
        . '<p><a href="' . escape_html($verify_link) . '" style="background:#C85C1A;color:#fff;padding:10px 18px;'
        . 'text-decoration:none;border-radius:4px;display:inline-block;">Verify my email</a></p>'
        . '<p>If you did not create an account, ignore this message.</p>';
    return ['Verify your ADRS account', email_layout('Email verification', $body)];
}
