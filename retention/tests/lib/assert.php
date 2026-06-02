<?php
/** Minimal no-Composer assertion library. */

$GLOBALS['__tests'] = ['passed' => 0, 'failed' => 0, 'skipped' => 0, 'failures' => []];

function _record_pass(): void { $GLOBALS['__tests']['passed']++; }

function _record_fail(string $msg): void {
    $GLOBALS['__tests']['failed']++;
    $GLOBALS['__tests']['failures'][] = $msg;
    echo "  \033[31mFAIL\033[0m $msg\n";
}

function test_skip(string $msg): void {
    $GLOBALS['__tests']['skipped']++;
    echo "  \033[33mSKIP\033[0m $msg\n";
}

function assert_true($cond, string $msg = ''): void {
    if ($cond === true) { _record_pass(); } else { _record_fail($msg ?: 'expected true, got ' . var_export($cond, true)); }
}

function assert_false($cond, string $msg = ''): void {
    if ($cond === false) { _record_pass(); } else { _record_fail($msg ?: 'expected false, got ' . var_export($cond, true)); }
}

function assert_equals($expected, $actual, string $msg = ''): void {
    if ($expected === $actual) { _record_pass(); }
    else { _record_fail(($msg ?: 'not equal') . " — expected " . var_export($expected, true) . ", got " . var_export($actual, true)); }
}

function assert_throws(callable $fn, string $msg = ''): void {
    try { $fn(); _record_fail($msg ?: 'expected exception, none thrown'); }
    catch (Throwable $e) { _record_pass(); }
}
