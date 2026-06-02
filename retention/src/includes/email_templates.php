<?php
function email_template_password_reset(string $resetUrl): string
{
    return '<p>Please use the link below to reset your password:</p>' .
           '<p><a href="' . htmlspecialchars($resetUrl, ENT_QUOTES, 'UTF-8') . '">Reset password</a></p>';
}

function email_template_notification(string $subject, string $body): string
{
    return '<h1>' . htmlspecialchars($subject, ENT_QUOTES, 'UTF-8') . '</h1><p>' . nl2br(htmlspecialchars($body, ENT_QUOTES, 'UTF-8')) . '</p>';
}
