<?php
/** POST /api/v1/consent/withdraw — inbound consent withdrawal signal (E4). */
api_require_permission($apiKey, 'consent');

$body = api_body();
$externalRef = trim((string) ($body['external_ref'] ?? ''));
if ($externalRef === '') {
    api_response(422, ['error' => 'validation_error', 'message' => 'external_ref is required.']);
}
$signalType = in_array($body['signal_type'] ?? '', ['withdrawal', 'restriction', 'erasure_request'], true)
    ? $body['signal_type'] : 'withdrawal';

$r = record_consent_signal($pdo, (int) $apiKey['system_id'], $externalRef, $signalType, $body);

api_response(200, [
    'status'    => $r['matched'] ? 'processed' : 'unmatched',
    'signal_id' => $r['signal_id'],
    'record_id' => $r['record_id'],
    'message'   => $r['matched']
        ? 'Consent withdrawal applied; disposal countdown started.'
        : 'Signal stored; no matching record yet — it will be retried automatically.',
]);
