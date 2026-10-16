-- 2026-10-16 — Stripe (USD) alongside Paystack (NGN) + theme defaults
-- Safe to run on an existing deployment: additive only, uses INSERT IGNORE.

INSERT IGNORE INTO `system_settings` (`setting_key`, `setting_value`, `description`) VALUES
  ('stripe_publishable_key', '', 'Stripe publishable key (pk_...)'),
  ('stripe_secret_key',      '', 'Stripe secret key (sk_...)'),
  ('stripe_webhook_secret',  '', 'Stripe webhook signing secret (whsec_...)'),
  ('core_plan_amount_usd_cents',       '5000',  'Core plan annual price in USD cents (Stripe)'),
  ('enterprise_plan_amount_usd_cents', '16000', 'Enterprise plan annual price in USD cents (Stripe)'),
  ('billing_default_country', 'NG', 'ISO-3166 alpha-2 country used when no visitor hint is available'),
  ('billing_display_fx_ngn_per_usd', '1600', 'Display-only NGN per USD rate for the local-currency estimate shown beside USD prices'),
  ('ui_theme_default', 'system', 'Default colour mode: system | light | dark');
