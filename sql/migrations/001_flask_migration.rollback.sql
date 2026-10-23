-- Rollback of 001 (only needed to go back to the PHP version).
-- Restores the legacy password columns; passwords changed or re-hashed by
-- the Flask version cannot be restored and must be reset.
-- The full backup taken before the migration is the safer alternative.

UPDATE `mentor` m JOIN `mentor_auth` a ON a.`ma_mentor_id` = m.`mentor_user_id`
  SET m.`mentor_login_password` = a.`ma_legacy_hash`, m.`mentor_pw_salt` = a.`ma_legacy_salt`,
      m.`mentor_lastupdate` = m.`mentor_lastupdate`
  WHERE a.`ma_legacy_hash` IS NOT NULL;

ALTER TABLE `mentor` DROP KEY `mentor_user_name`;
ALTER TABLE `mentee_mentor` DROP KEY `mm_stop`, DROP KEY `mm_start`;
ALTER TABLE `logging` DROP KEY `log_date`, ENGINE=MyISAM,
  CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci;
ALTER TABLE `comentors` ENGINE=MyISAM;
DROP TABLE `mp_meta`;
DROP TABLE `mentor_auth`;
DELETE FROM `schema_migrations` WHERE `version` = 1;
