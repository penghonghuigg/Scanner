CREATE TABLE `integration_snapshots` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `session_id` BIGINT UNSIGNED NOT NULL,
    `payload_json` JSON NOT NULL,
    `payload_sha256` CHAR(64) NOT NULL,
    `status` VARCHAR(16) NOT NULL,
    `external_data_id` VARCHAR(100) NULL,
    `attempt_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `last_error_code` VARCHAR(64) NULL,
    `last_error_message` VARCHAR(500) NULL,
    `created_by` BIGINT UNSIGNED NOT NULL,
    `last_attempted_by` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `succeeded_at` DATETIME(6) NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_integration_snapshots_session` (`session_id`),
    KEY `idx_integration_snapshots_status_updated` (`status`, `updated_at`),
    CONSTRAINT `fk_integration_snapshots_session`
        FOREIGN KEY (`session_id`) REFERENCES `scan_sessions` (`id`)
        ON DELETE RESTRICT,
    CONSTRAINT `fk_integration_snapshots_created_by`
        FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
        ON DELETE RESTRICT,
    CONSTRAINT `fk_integration_snapshots_last_attempted_by`
        FOREIGN KEY (`last_attempted_by`) REFERENCES `users` (`id`)
        ON DELETE RESTRICT,
    CONSTRAINT `ck_integration_snapshots_status`
        CHECK (`status` IN ('PENDING', 'SUCCEEDED', 'FAILED', 'UNCERTAIN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
