<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/email_templates.php';
require_once __DIR__ . '/phpmailer/Exception.php';
require_once __DIR__ . '/phpmailer/SMTP.php';
require_once __DIR__ . '/phpmailer/PHPMailer.php';

use PHPMailer\PHPMailer\PHPMailer;

/** Send using platform-level SMTP keys in system_settings (registration, billing). */
function send_platform_email(PDO $pdo, string $to_email, string $subject, string $html): bool {
    $stmt = $pdo->prepare('SELECT setting_key, setting_value FROM system_settings WHERE setting_key LIKE :p');
    $stmt->execute(['p' => 'smtp%']);
    $platform = [];
    foreach ($stmt->fetchAll() as $row) { $platform[$row['setting_key']] = $row['setting_value']; }
    $host = $platform['smtp_host'] ?? '';
    if ($host === '' || stripos($host, 'yourdomain') !== false) { return false; }
    $from = $platform['smtp_from_email'] ?? $platform['smtp_user'] ?? 'noreply@localhost';
    $fromName = $platform['smtp_from_name'] ?? (defined('APP_NAME') ? APP_NAME : 'ADRS');
    $mail = new PHPMailer(true);
    try {
        $mail->isSMTP();
        $mail->Host = $host;
        $mail->Port = (int) ($platform['smtp_port'] ?? 587);
        $user = $platform['smtp_user'] ?? $platform['smtp_username'] ?? '';
        if ($user) {
            $mail->SMTPAuth = true;
            $mail->Username = $user;
            $mail->Password = (string) ($platform['smtp_pass'] ?? $platform['smtp_password'] ?? '');
        }
        $secure = $platform['smtp_encryption'] ?? $platform['smtp_secure'] ?? 'tls';
        if ($secure === 'ssl') { $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS; }
        elseif ($secure === 'tls') { $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS; }
        $mail->setFrom($from, $fromName);
        $mail->addAddress($to_email);
        $mail->isHTML(true);
        $mail->Subject = $subject;
        $mail->Body = $html;
        return $mail->send();
    } catch (Throwable $e) {
        return false;
    }
}

/**
 * Send one HTML email. SMTP settings come exclusively from system_settings
 * (BUG-08 fix). Falls back to PHP mail() if no SMTP host is configured.
 * Returns true on success.
 */
function send_system_email(PDO $pdo, string $to_email, string $subject, string $html): bool {
    $host = get_setting($pdo, 'smtp_host');
    $from = get_setting($pdo, 'smtp_from_email', 'no-reply@localhost');
    $fromName = get_setting($pdo, 'smtp_from_name', defined('APP_NAME') ? APP_NAME : 'ADRS');

    if ($host) {
        $mail = new PHPMailer(true);
        try {
            $mail->isSMTP();
            $mail->Host = $host;
            $mail->Port = (int) get_setting($pdo, 'smtp_port', 587);
            $user = get_setting($pdo, 'smtp_username');
            if ($user) {
                $mail->SMTPAuth = true;
                $mail->Username = $user;
                $mail->Password = (string) get_setting($pdo, 'smtp_password', '');
            }
            $secure = get_setting($pdo, 'smtp_secure', 'tls');
            if ($secure === 'ssl') { $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS; }
            elseif ($secure === 'tls') { $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS; }
            $mail->setFrom($from, $fromName);
            $mail->addAddress($to_email);
            $mail->isHTML(true);
            $mail->Subject = $subject;
            $mail->Body = $html;
            return $mail->send();
        } catch (Throwable $e) {
            if (defined('LOG_PATH')) {
                if (!is_dir(LOG_PATH)) { @mkdir(LOG_PATH, 0755, true); }
                @file_put_contents(LOG_PATH . 'mail_errors.log', '[' . date('c') . '] ' . $e->getMessage() . PHP_EOL, FILE_APPEND);
            }
            return false;
        }
    }

    $headers = "MIME-Version: 1.0\r\nContent-type: text/html; charset=utf-8\r\nFrom: {$fromName} <{$from}>\r\n";
    return @mail($to_email, $subject, $html, $headers);
}

/**
 * Dispatch pending notifications as emails. $sender(to, subject, html): bool lets tests
 * inject a fake transport; defaults to send_system_email(). Marks each notification
 * 'sent' (sets sent_at) or 'failed' (increments attempts). Returns ['sent'=>, 'failed'=>].
 */
function dispatch_pending_notifications(PDO $pdo, ?callable $sender = null, int $limit = 100): array {
    $sender = $sender ?? fn(string $to, string $subj, string $html): bool => send_system_email($pdo, $to, $subj, $html);

    $stmt = $pdo->prepare(
        "SELECT n.id, n.subject, n.message, u.email, u.name
         FROM notifications n JOIN users u ON u.id = n.recipient_id
         WHERE n.status IN ('pending','failed') AND n.attempts < 3
           AND u.is_active = 1 AND u.deleted_at IS NULL AND u.email IS NOT NULL
         ORDER BY n.id ASC LIMIT :lim"
    );
    $stmt->bindValue('lim', $limit, PDO::PARAM_INT);
    $stmt->execute();

    $ok = 0; $fail = 0;
    $markSent = $pdo->prepare("UPDATE notifications SET status='sent', sent_at=NOW(), attempts=attempts+1 WHERE id=:id");
    $markFail = $pdo->prepare("UPDATE notifications SET status='failed', attempts=attempts+1 WHERE id=:id");
    foreach ($stmt->fetchAll() as $n) {
        $html = render_notification_email($n);
        if ($sender($n['email'], $n['subject'], $html)) { $markSent->execute(['id' => $n['id']]); $ok++; }
        else { $markFail->execute(['id' => $n['id']]); $fail++; }
    }
    return ['sent' => $ok, 'failed' => $fail];
}
