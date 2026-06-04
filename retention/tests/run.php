<?php
/** Usage: php tests/run.php  (run from retention/ root). Exit non-zero on any failure. */
error_reporting(E_ALL);
ini_set('display_errors', '1');

require __DIR__ . '/lib/assert.php';
// bootstrap.php (added in Task 4) sets DB availability + resets the test DB when reachable.
if (is_file(__DIR__ . '/bootstrap.php')) { require __DIR__ . '/bootstrap.php'; }

$files = [];
$dir = new RecursiveDirectoryIterator(__DIR__, FilesystemIterator::SKIP_DOTS);
foreach (new RecursiveIteratorIterator($dir) as $f) {
    if (preg_match('/_test\.php$/', $f->getFilename())) { $files[] = $f->getPathname(); }
}
sort($files);

foreach ($files as $file) {
    echo "\n# " . substr($file, strlen(__DIR__) + 1) . "\n";
    require $file;
}

$t = $GLOBALS['__tests'];
echo "\n----------------------------------------\n";
echo "Passed: {$t['passed']}  Failed: {$t['failed']}  Skipped: {$t['skipped']}\n";
exit($t['failed'] > 0 ? 1 : 0);
