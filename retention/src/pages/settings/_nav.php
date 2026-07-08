<?php
/** Shared sub-navigation for Settings area. */
function settings_nav(string $active): string {
    $items = [
        'organization' => ['Organisation', '/settings/organization'],
        'general'      => ['Retention & email', '/settings'],
        'twofa'        => ['Two-factor auth', '/settings/2fa'],
    ];
    $html = '<ul class="nav nav-tabs settings-nav mb-4">';
    foreach ($items as $key => [$label, $route]) {
        $cls = $key === $active ? ' active' : '';
        $html .= '<li class="nav-item"><a class="nav-link' . $cls . '" href="' . APP_URL . $route . '">' . escape_html($label) . '</a></li>';
    }
    $html .= '</ul>';
    return $html;
}
