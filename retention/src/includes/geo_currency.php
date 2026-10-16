<?php
/**
 * Visitor currency hints for the SafeData payments page.
 *
 * Zero-dependency: we never block the page on an external geo-IP call.
 * We look at Cloudflare / standard country headers (if the hosting proxy
 * sets them), then Accept-Language, then fall back to a system default.
 *
 * The USD and NGN prices on the page always come from Stripe and Paystack
 * respectively; the local-currency figure is a *display estimate* only.
 */

require_once __DIR__ . '/helpers.php';

/** ISO-3166 alpha-2 country code → ISO-4217 currency. Short list, extend as needed. */
function geo_country_to_currency(string $country): string {
    static $map = [
        'NG' => 'NGN', 'US' => 'USD', 'GB' => 'GBP', 'IE' => 'EUR',
        'FR' => 'EUR', 'DE' => 'EUR', 'ES' => 'EUR', 'IT' => 'EUR',
        'NL' => 'EUR', 'PT' => 'EUR', 'BE' => 'EUR', 'AT' => 'EUR',
        'CA' => 'CAD', 'AU' => 'AUD', 'NZ' => 'NZD', 'ZA' => 'ZAR',
        'KE' => 'KES', 'GH' => 'GHS', 'EG' => 'EGP', 'MA' => 'MAD',
        'IN' => 'INR', 'PK' => 'PKR', 'BD' => 'BDT', 'SG' => 'SGD',
        'MY' => 'MYR', 'ID' => 'IDR', 'PH' => 'PHP', 'TH' => 'THB',
        'JP' => 'JPY', 'KR' => 'KRW', 'CN' => 'CNY', 'HK' => 'HKD',
        'AE' => 'AED', 'SA' => 'SAR', 'TR' => 'TRY', 'BR' => 'BRL',
        'MX' => 'MXN', 'AR' => 'ARS', 'CL' => 'CLP', 'CO' => 'COP',
        'CH' => 'CHF', 'SE' => 'SEK', 'NO' => 'NOK', 'DK' => 'DKK',
    ];
    $country = strtoupper($country);
    return $map[$country] ?? 'USD';
}

/** Currency symbol or ISO code for display. */
function geo_currency_symbol(string $cur): string {
    static $sym = [
        'USD' => '$', 'NGN' => '₦', 'GBP' => '£', 'EUR' => '€',
        'JPY' => '¥', 'CNY' => '¥', 'INR' => '₹', 'ZAR' => 'R',
        'KES' => 'KSh', 'GHS' => 'GH₵', 'CAD' => 'C$', 'AUD' => 'A$',
    ];
    return $sym[strtoupper($cur)] ?? ($cur . ' ');
}

/** Guess visitor country code. Returns alpha-2 or '' when unknown. */
function geo_detect_country(): string {
    // 1. Proxy-set headers (Cloudflare, some CDNs, some cPanel setups).
    foreach (['HTTP_CF_IPCOUNTRY', 'HTTP_X_COUNTRY_CODE', 'HTTP_X_APPENGINE_COUNTRY', 'GEOIP_COUNTRY_CODE'] as $h) {
        $v = $_SERVER[$h] ?? '';
        if (is_string($v) && preg_match('/^[A-Z]{2}$/', strtoupper($v))) {
            return strtoupper($v);
        }
    }
    // 2. Accept-Language region hint (e.g. "en-GB,en;q=0.9" → GB).
    $al = (string) ($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '');
    if (preg_match('/[a-z]{2}-([A-Z]{2})/', $al, $m)) {
        return $m[1];
    }
    return '';
}

/**
 * Resolve the visitor's view. Returns:
 *   ['country' => 'NG', 'currency' => 'NGN', 'symbol' => '₦', 'is_nigeria' => true]
 * Honours ?country=XX in the URL (sticky via session) so support can preview.
 */
function geo_visitor_view(PDO $pdo): array {
    if (session_status() !== PHP_SESSION_ACTIVE) { @session_start(); }

    $override = strtoupper((string) ($_GET['country'] ?? ''));
    if (preg_match('/^[A-Z]{2}$/', $override)) {
        $_SESSION['billing_country'] = $override;
    }

    $country = $_SESSION['billing_country']
        ?? geo_detect_country()
        ?: (string) get_setting($pdo, 'billing_default_country', 'NG');

    $currency = geo_country_to_currency($country);

    return [
        'country'    => $country,
        'currency'   => $currency,
        'symbol'     => geo_currency_symbol($currency),
        'is_nigeria' => $country === 'NG',
    ];
}

/**
 * Format a USD-cent price in the visitor's local currency using the
 * display-only rate stored in settings. For NGN we use the Paystack kobo
 * price directly instead of a derived rate.
 */
function geo_local_estimate(PDO $pdo, int $usdCents, string $currency, ?int $ngnKobo = null): string {
    if ($currency === 'USD') { return '$' . number_format($usdCents / 100, 2); }
    if ($currency === 'NGN' && $ngnKobo !== null) {
        return '₦' . number_format($ngnKobo / 100, 2);
    }
    // Derive from the stored FX; refuses to invent cross-rates for exotic pairs.
    $ngnPerUsd = max(1, (int) get_setting($pdo, 'billing_display_fx_ngn_per_usd', '1600'));
    if ($currency === 'NGN') {
        $naira = ($usdCents / 100) * $ngnPerUsd;
        return '₦' . number_format($naira, 2);
    }
    // Fallback: show USD if we cannot responsibly convert.
    return '$' . number_format($usdCents / 100, 2) . ' USD';
}
