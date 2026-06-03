<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/records_lib.php';

/**
 * Two-pass bulk import (B8). Pass 1 validates every row against the live category register
 * without writing anything; pass 2 commits only if there were no blocking errors (or commits
 * the valid subset, recording skipped rows). CSV header: category_name, record_reference,
 * data_subject_type, collection_date.
 */

/** Parse CSV text into a list of associative rows keyed by the header. */
function parse_csv(string $content): array {
    $lines = preg_split('/\r\n|\r|\n/', trim($content));
    if (!$lines || count($lines) < 2) { return []; }
    $header = str_getcsv(array_shift($lines), ',', '"', '');
    $header = array_map(fn($h) => strtolower(trim($h)), $header);
    $rows = [];
    foreach ($lines as $line) {
        if (trim($line) === '') { continue; }
        $cells = str_getcsv($line, ',', '"', '');
        $row = [];
        foreach ($header as $i => $key) { $row[$key] = $cells[$i] ?? ''; }
        $rows[] = $row;
    }
    return $rows;
}

/**
 * Pass 1: validate rows. Returns ['valid'=>[[row, category]...], 'errors'=>[['line'=>n,'error'=>..]]].
 * A row is valid when the category name resolves to an active category, a reference is present,
 * and the collection date parses.
 */
function validate_import_rows(PDO $pdo, array $rows): array {
    // Build a name -> category map once.
    $cats = [];
    foreach ($pdo->query("SELECT * FROM data_categories WHERE deleted_at IS NULL AND is_active=1")->fetchAll() as $c) {
        $cats[strtolower(trim($c['name']))] = $c;
    }
    $valid = []; $errors = [];
    foreach ($rows as $i => $row) {
        $line = $i + 2; // +1 header, +1 to 1-base
        $name = strtolower(trim($row['category_name'] ?? ''));
        $ref = trim($row['record_reference'] ?? '');
        $date = trim($row['collection_date'] ?? '');
        if ($name === '' || !isset($cats[$name])) { $errors[] = ['line' => $line, 'error' => 'Unknown category: ' . ($row['category_name'] ?? '')]; continue; }
        if ($ref === '') { $errors[] = ['line' => $line, 'error' => 'Missing record_reference']; continue; }
        if ($date === '' || strtotime($date) === false) { $errors[] = ['line' => $line, 'error' => 'Invalid collection_date']; continue; }
        $valid[] = ['row' => $row, 'category' => $cats[$name]];
    }
    return ['valid' => $valid, 'errors' => $errors];
}

/**
 * Pass 2: commit valid rows. Records an import_jobs row with the tallies. Returns the job summary.
 */
function commit_import(PDO $pdo, string $filename, array $rows, int $actor_id): array {
    $check = validate_import_rows($pdo, $rows);
    $imported = 0;
    $ins = $pdo->prepare(
        "INSERT INTO data_records (category_id, record_reference, data_subject_type, collection_date, retention_end_date, status, created_by)
         VALUES (:cid,:ref,:subj,:cdate,:rend,'active',:by)"
    );
    foreach ($check['valid'] as $item) {
        $cat = $item['category']; $row = $item['row'];
        $cdate = date('Y-m-d', strtotime($row['collection_date']));
        $rend = compute_retention_end($cat, $cdate);
        $ins->execute([
            'cid' => $cat['id'], 'ref' => trim($row['record_reference']),
            'subj' => ($row['data_subject_type'] ?? '') ?: null, 'cdate' => $cdate, 'rend' => $rend, 'by' => $actor_id,
        ]);
        $imported++;
    }
    $total = count($rows);
    $errors = count($check['errors']);
    $status = $imported > 0 ? 'imported' : 'failed';
    $pdo->prepare(
        "INSERT INTO import_jobs (imported_by, filename, total_rows, valid_rows, imported_rows, skipped_rows, error_rows, status, error_report, completed_at)
         VALUES (:by,:fn,:total,:valid,:imp,:skip,:err,:st,:report,NOW())"
    )->execute([
        'by' => $actor_id, 'fn' => $filename, 'total' => $total, 'valid' => count($check['valid']),
        'imp' => $imported, 'skip' => $errors, 'err' => $errors, 'st' => $status,
        'report' => json_encode($check['errors'], JSON_UNESCAPED_UNICODE),
    ]);
    log_audit($pdo, 'bulk_import', 'system', null, $actor_id, ['filename' => $filename, 'imported' => $imported, 'errors' => $errors], get_client_ip());
    return ['imported' => $imported, 'errors' => $errors, 'total' => $total];
}
