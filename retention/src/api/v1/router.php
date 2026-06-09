<?php
require_once __DIR__ . '/bootstrap.php';

$route  = trim((string) ($_GET['_route'] ?? ''), '/');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$pdo    = get_db();

require_enterprise_tier($pdo);
require_api_enabled($pdo);

$apiKey = verify_api_key($pdo, $_SERVER['HTTP_X_API_KEY'] ?? '');
if ($apiKey === null) {
    api_response(401, ['error' => 'invalid_api_key', 'message' => 'A valid X-API-Key header is required.']);
}
require_once __DIR__ . '/../../includes/helpers.php';
$GLOBALS['__cron_org_id'] = (int) ($apiKey['organization_id'] ?? 1);
clear_setting_cache();
if (!within_rate_limit($pdo, (int) $apiKey['id'], (int) $apiKey['rate_limit_per_min'])) {
    header('Retry-After: 60');
    api_response(429, ['error' => 'rate_limit_exceeded', 'message' => 'Too many requests; slow down.']);
}

// Log every API call (and its final status) once the request ends.
$GLOBALS['__api_ctx'] = ['key' => $apiKey, 'route' => $route, 'method' => $method, 'start' => microtime(true), 'pdo' => $pdo];
register_shutdown_function(function () {
    $c = $GLOBALS['__api_ctx'] ?? null;
    if (!$c) { return; }
    log_integration($c['pdo'], (int) $c['key']['system_id'], (int) $c['key']['id'], 'inbound',
        '/api/v1/' . $c['route'], $c['method'], http_response_code() ?: 200, null, null, 0,
        (int) round((microtime(true) - $c['start']) * 1000));
});

/** Require a permission on the key, else 403. */
function api_require_permission(array $key, string $perm): void {
    if (!api_key_can($key, $perm)) {
        api_response(403, ['error' => 'permission_denied', 'message' => "API key lacks '$perm' permission."]);
    }
}

match (true) {
    $method === 'GET'  && $route === 'health'           => require __DIR__ . '/endpoints/health.php',
    $method === 'GET'  && $route === 'categories'       => require __DIR__ . '/endpoints/categories.php',
    $method === 'POST' && $route === 'ingest'           => require __DIR__ . '/endpoints/ingest.php',
    $method === 'POST' && $route === 'ingest/batch'     => require __DIR__ . '/endpoints/ingest_batch.php',
    $method === 'POST' && $route === 'consent/withdraw' => require __DIR__ . '/endpoints/consent_withdraw.php',
    $method === 'GET'  && str_starts_with($route, 'records/') => require __DIR__ . '/endpoints/record_status.php',
    default => api_response(404, ['error' => 'not_found', 'message' => "No route for $method /api/v1/$route"]),
};
