<?php
/**
 * Pure-PHP TOTP (RFC 6238) for two-factor auth — no external service or library.
 * Compatible with Google Authenticator, Authy, Microsoft Authenticator, etc.
 */

const TOTP_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

function base32_encode(string $bin): string {
    if ($bin === '') { return ''; }
    $bits = '';
    foreach (str_split($bin) as $c) { $bits .= str_pad(decbin(ord($c)), 8, '0', STR_PAD_LEFT); }
    $out = '';
    foreach (str_split($bits, 5) as $chunk) {
        $out .= TOTP_ALPHABET[bindec(str_pad($chunk, 5, '0', STR_PAD_RIGHT))];
    }
    return $out;
}

function base32_decode(string $b32): string {
    $b32 = strtoupper(rtrim($b32, '='));
    if ($b32 === '') { return ''; }
    $bits = '';
    foreach (str_split($b32) as $c) {
        $idx = strpos(TOTP_ALPHABET, $c);
        if ($idx === false) { continue; }
        $bits .= str_pad(decbin($idx), 5, '0', STR_PAD_LEFT);
    }
    $out = '';
    foreach (str_split($bits, 8) as $byte) {
        if (strlen($byte) === 8) { $out .= chr(bindec($byte)); }
    }
    return $out;
}

/** New random base32 TOTP secret (default 20 bytes => 32 chars). */
function totp_generate_secret(int $bytes = 20): string {
    return base32_encode(random_bytes($bytes));
}

/** The TOTP code for a secret at a given time. */
function totp_code(string $secret_b32, ?int $timestamp = null, int $period = 30, int $digits = 6): string {
    $key = base32_decode($secret_b32);
    $counter = (int) floor(($timestamp ?? time()) / $period);
    $bin = pack('N*', 0) . pack('N*', $counter);      // 8-byte big-endian counter
    $hash = hash_hmac('sha1', $bin, $key, true);
    $offset = ord($hash[strlen($hash) - 1]) & 0x0F;
    $part = (ord($hash[$offset]) & 0x7F) << 24
          | (ord($hash[$offset + 1]) & 0xFF) << 16
          | (ord($hash[$offset + 2]) & 0xFF) << 8
          | (ord($hash[$offset + 3]) & 0xFF);
    return str_pad((string) ($part % (10 ** $digits)), $digits, '0', STR_PAD_LEFT);
}

/** Verify a code against a secret, tolerating ±$window periods of clock drift. */
function totp_verify(string $secret_b32, string $code, ?int $timestamp = null, int $window = 1, int $period = 30): bool {
    $code = preg_replace('/\s+/', '', $code);
    if (!preg_match('/^\d{6}$/', $code)) { return false; }
    $ts = $timestamp ?? time();
    for ($i = -$window; $i <= $window; $i++) {
        if (hash_equals(totp_code($secret_b32, $ts + ($i * $period), $period), $code)) { return true; }
    }
    return false;
}

/** otpauth:// URI for QR-code provisioning. */
function totp_uri(string $secret_b32, string $account, string $issuer): string {
    return 'otpauth://totp/' . rawurlencode($issuer . ':' . $account)
        . '?secret=' . $secret_b32 . '&issuer=' . rawurlencode($issuer) . '&period=30&digits=6';
}

/** Generate N plaintext recovery codes (show once) + their SHA-256 hashes (to store). */
function generate_recovery_codes(int $n = 8): array {
    $plain = []; $hashed = [];
    for ($i = 0; $i < $n; $i++) {
        $code = strtoupper(bin2hex(random_bytes(5))); // 10 hex chars
        $code = substr($code, 0, 5) . '-' . substr($code, 5);
        $plain[] = $code;
        $hashed[] = hash('sha256', $code);
    }
    return ['plain' => $plain, 'hashed' => $hashed];
}

/** Check a recovery code against the stored hashes; returns the remaining hashes if consumed, or null if no match. */
function consume_recovery_code(array $hashed_codes, string $candidate): ?array {
    $h = hash('sha256', strtoupper(trim($candidate)));
    $idx = array_search($h, $hashed_codes, true);
    if ($idx === false) { return null; }
    unset($hashed_codes[$idx]);
    return array_values($hashed_codes);
}
