<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/phpmailer/Exception.php';
require_once __DIR__ . '/phpmailer/SMTP.php';
require_once __DIR__ . '/phpmailer/PHPMailer.php';

function send_system_email(PDO $pdo, string $toEmail, string $subject, string $messageHtml): bool
{
    $smtpHost = get_setting($pdo, 'smtp_host');
    $smtpUser = get_setting($pdo, 'smtp_username');
    $smtpPass = get_setting($pdo, 'smtp_password');
    $smtpPort = get_setting($pdo, 'smtp_port', 25);
    $smtpSecure = get_setting($pdo, 'smtp_secure', 'tls');
    $fromEmail = get_setting($pdo, 'smtp_from_email', 'no-reply@localhost');
    $fromName = get_setting($pdo, 'smtp_from_name', 'ADRS');

    if ($smtpHost && class_exists('PHPMailer')) {
        $mail = new PHPMailer(true);
        try {
            $mail->isSMTP();
            $mail->Host = $smtpHost;
            $mail->SMTPAuth = true;
            $mail->Username = $smtpUser;
            $mail->Password = $smtpPass;
            $mail->SMTPSecure = $smtpSecure;
            $mail->Port = $smtpPort;
            $mail->setFrom($fromEmail, $fromName);
            $mail->addAddress($toEmail);
            $mail->isHTML(true);
            $mail->Subject = $subject;
            $mail->Body = $messageHtml;
            return $mail->send();
        } catch (Exception $e) {
            return false;
        }
    }

    $headers = "MIME-Version: 1.0\r\n";
    $headers .= "Content-type: text/html; charset=utf-8\r\n";
    $headers .= "From: {$fromName} <{$fromEmail}>\r\n";
    return mail($toEmail, $subject, $messageHtml, $headers);
}
