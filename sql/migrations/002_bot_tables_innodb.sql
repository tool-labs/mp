-- 002: mentor, mentee and mentee_mentor to InnoDB/utf8mb4 (2026-10).
--
-- Only apply after SpBot's mp-helper.py runs on API v1: the old pyapi/dewpmp.py
-- never commits, its writes would be lost on InnoDB. The writers are now the
-- web interface and the job sync-mentees, both use transactions.
-- utf8mb4 allows 4-byte characters (e.g. emoji) in user names.
--
-- Check first (must be 0, zero dates cannot be converted):
--   SELECT COUNT(*) FROM mentee_mentor WHERE mm_start < '2000-01-01';
--
-- Rollback: sql/migrations/002_bot_tables_innodb.rollback.sql

ALTER TABLE `mentor` ENGINE=InnoDB, CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE `mentee` ENGINE=InnoDB, CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE `mentee_mentor` ENGINE=InnoDB, CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  MODIFY `mm_start` datetime NOT NULL;

INSERT INTO `schema_migrations` (`version`, `description`) VALUES (2, 'bot tables to InnoDB/utf8mb4');
