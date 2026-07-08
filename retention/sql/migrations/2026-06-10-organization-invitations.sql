-- Team invitations for SaaS onboarding (email invite links).
CREATE TABLE IF NOT EXISTS `organization_invitations` (
  `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `organization_id` INT UNSIGNED NOT NULL,
  `email`           VARCHAR(255) NOT NULL,
  `name`            VARCHAR(255) NOT NULL,
  `role`            ENUM('admin','dpo','data_owner') NOT NULL DEFAULT 'data_owner',
  `token_hash`      CHAR(64)     NOT NULL,
  `invited_by`      INT UNSIGNED NULL,
  `expires_at`      TIMESTAMP    NOT NULL,
  `accepted_at`     TIMESTAMP    NULL,
  `revoked_at`      TIMESTAMP    NULL,
  `created_at`      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_invites_org` (`organization_id`),
  KEY `idx_invites_email` (`email`),
  KEY `idx_invites_token` (`token_hash`),
  CONSTRAINT `fk_invites_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_invites_user` FOREIGN KEY (`invited_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
