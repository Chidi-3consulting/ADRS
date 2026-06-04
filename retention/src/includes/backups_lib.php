<?php
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/helpers.php';

/**
 * Phase 3 automated DB backups — a self-contained pure-PHP logical dump (no external
 * mysqldump dependency, so it runs on any shared host). Produces a restorable .sql file,
 * records the outcome in backup_log, and prunes old backups.
 */

/** Dump the whole database to a .sql file in $dir. Returns ['file','size','status','message']. */
function backup_database(PDO $pdo, string $dir): array {
    if (!is_dir($dir)) { @mkdir($dir, 0755, true); }
    $file = rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'adrs_backup_' . date('Ymd_His') . '.sql';

    try {
        $fh = fopen($file, 'w');
        if (!$fh) { throw new RuntimeException('Cannot open backup file for writing'); }
        fwrite($fh, "-- ADRS backup " . date('c') . "\nSET FOREIGN_KEY_CHECKS=0;\nSET NAMES utf8mb4;\n\n");

        $tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);
        foreach ($tables as $t) {
            $create = $pdo->query("SHOW CREATE TABLE `$t`")->fetch(PDO::FETCH_ASSOC);
            $createSql = $create['Create Table'] ?? ($create['Create View'] ?? null);
            if (!$createSql) { continue; }
            fwrite($fh, "DROP TABLE IF EXISTS `$t`;\n$createSql;\n\n");

            $rows = $pdo->query("SELECT * FROM `$t`");
            while ($row = $rows->fetch(PDO::FETCH_ASSOC)) {
                $cols = '`' . implode('`,`', array_keys($row)) . '`';
                $vals = implode(',', array_map(fn($v) => $v === null ? 'NULL' : $pdo->quote((string) $v), array_values($row)));
                fwrite($fh, "INSERT INTO `$t` ($cols) VALUES ($vals);\n");
            }
            fwrite($fh, "\n");
        }
        fwrite($fh, "SET FOREIGN_KEY_CHECKS=1;\n");
        fclose($fh);

        $size = (int) filesize($file);
        $pdo->prepare("INSERT INTO backup_log (filename, size_bytes, status, message) VALUES (:f,:s,'success',NULL)")
            ->execute(['f' => basename($file), 's' => $size]);
        return ['file' => $file, 'size' => $size, 'status' => 'success', 'message' => null];
    } catch (Throwable $e) {
        try {
            $pdo->prepare("INSERT INTO backup_log (filename, size_bytes, status, message) VALUES (:f,NULL,'failed',:m)")
                ->execute(['f' => basename($file), 'm' => $e->getMessage()]);
        } catch (Throwable $ignore) { /* backup_log may be absent on an un-migrated DB */ }
        return ['file' => $file, 'size' => 0, 'status' => 'failed', 'message' => $e->getMessage()];
    }
}

/** Delete backup files (and their log rows) older than $days. Returns count removed. */
function prune_backups(PDO $pdo, string $dir, int $days): int {
    $cutoff = time() - ($days * 86400);
    $removed = 0;
    foreach (glob(rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . 'adrs_backup_*.sql') ?: [] as $f) {
        if (filemtime($f) < $cutoff) { @unlink($f); $removed++; }
    }
    $pdo->prepare("DELETE FROM backup_log WHERE created_at < DATE_SUB(NOW(), INTERVAL :d DAY)")->execute(['d' => $days]);
    return $removed;
}
