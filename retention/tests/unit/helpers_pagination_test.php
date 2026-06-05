<?php
$pg = paginate(0, 25, 1);
assert_equals(1, $pg['pages'], 'zero results -> 1 page');
assert_equals(0, $pg['offset'], 'zero results -> offset 0');
assert_false($pg['has_prev'], 'page 1 has no prev');
assert_false($pg['has_next'], 'single page has no next');

$pg = paginate(120, 25, 1);
assert_equals(5, $pg['pages'], '120/25 -> 5 pages');
assert_equals(0, $pg['offset'], 'page 1 offset 0');
assert_true($pg['has_next'], 'page 1 of 5 has next');

$pg = paginate(120, 25, 3);
assert_equals(50, $pg['offset'], 'page 3 offset = 50');
assert_true($pg['has_prev'] && $pg['has_next'], 'middle page has both');

$pg = paginate(120, 25, 99);
assert_equals(5, $pg['current'], 'over-range page clamps to last');
assert_equals(100, $pg['offset'], 'last page offset = 100');

assert_equals('', pagination_links(paginate(10, 25, 1), '/x'), 'single page renders no nav');
assert_true(str_contains(pagination_links(paginate(120, 25, 2), '/records', ['q' => 'a']), 'page=3'), 'nav builds next-page link preserving params');
