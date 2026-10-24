-- Rollback of 002. Names with 4-byte characters cannot be stored in utf8mb3
-- and make this fail; fix or remove those rows first.

ALTER TABLE `mentee_mentor` ENGINE=MyISAM, CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci,
  MODIFY `mm_start` datetime NOT NULL DEFAULT '0000-00-00 00:00:00';
ALTER TABLE `mentee` ENGINE=MyISAM, CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci;
ALTER TABLE `mentor` ENGINE=MyISAM, CONVERT TO CHARACTER SET utf8mb3 COLLATE utf8mb3_unicode_ci;
DELETE FROM `schema_migrations` WHERE `version` = 2;
