-- 001: schema changes for the Flask version (2026-10).
--
-- Constraint: the SpBot bot (pyapi/dewpmp.py, used by mp-helper.py) writes to
-- mentor, mentee and mentee_mentor with autocommit off and never commits.
-- That only works with MyISAM, so these three tables keep their engine and
-- columns. Only additive changes are made to them.
--
-- Rollback: sql/migrations/001_flask_migration.rollback.sql

CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version` int(10) unsigned NOT NULL,
  `description` varchar(255) NOT NULL,
  `applied_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Passwords move out of `mentor`: the public daily SQL dumps contained the
-- (weak, SHA1-based) hashes. The dump job now skips `mentor_auth`.
CREATE TABLE `mentor_auth` (
  `ma_mentor_id` int(10) unsigned NOT NULL COMMENT 'mentor.mentor_user_id',
  `ma_password_hash` varchar(255) DEFAULT NULL COMMENT 'werkzeug (scrypt/pbkdf2) hash',
  `ma_legacy_hash` char(40) DEFAULT NULL COMMENT 'PHP sha1 hash, replaced on next login',
  `ma_legacy_salt` char(40) DEFAULT NULL,
  `ma_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`ma_mentor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `mentor_auth` (`ma_mentor_id`, `ma_legacy_hash`, `ma_legacy_salt`)
  SELECT `mentor_user_id`, `mentor_login_password`, `mentor_pw_salt` FROM `mentor`
  WHERE `mentor_login_password` IS NOT NULL AND `mentor_login_password` <> '';

-- keep mentor_lastupdate unchanged (it has ON UPDATE CURRENT_TIMESTAMP)
UPDATE `mentor` SET `mentor_login_password` = NULL, `mentor_pw_salt` = NULL,
                    `mentor_lastupdate` = `mentor_lastupdate`
  WHERE `mentor_login_password` IS NOT NULL OR `mentor_pw_salt` IS NOT NULL;

-- key/value store, e.g. the last processed revision of WP:Mentorenprogramm
CREATE TABLE `mp_meta` (
  `meta_key` varchar(64) NOT NULL,
  `meta_value` text DEFAULT NULL,
  `meta_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`meta_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Not used by the bot: InnoDB allows an atomic refresh of the co-mentors
-- and utf8mb4 log comments.
ALTER TABLE `comentors` ENGINE=InnoDB;
ALTER TABLE `logging` ENGINE=InnoDB,
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  ADD KEY `log_date` (`log_date`);

-- indexes for the active-mentee, history and statistics queries
ALTER TABLE `mentee_mentor` ADD KEY `mm_stop` (`mm_stop`), ADD KEY `mm_start` (`mm_start`);
ALTER TABLE `mentor` ADD KEY `mentor_user_name` (`mentor_user_name`);

INSERT INTO `schema_migrations` (`version`, `description`) VALUES (1, 'Flask migration');
