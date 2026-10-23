-- Schema of s51391__mp as it was before the Flask migration (taken from
-- SHOW CREATE TABLE on 2026-10-23). Apply the files in sql/migrations/ on top.

CREATE TABLE `comentors` (
  `co_mentor_id` int(10) unsigned NOT NULL DEFAULT 0,
  `co_comentor_id` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'mentor.mentor_user_id',
  PRIMARY KEY (`co_mentor_id`,`co_comentor_id`),
  KEY `co_mentor_id` (`co_mentor_id`),
  KEY `co_comentor_id` (`co_comentor_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

CREATE TABLE `logging` (
  `log_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `log_date` timestamp NOT NULL DEFAULT current_timestamp(),
  `log_comment` text DEFAULT NULL,
  `log_user_name` text DEFAULT NULL,
  `log_type` text DEFAULT NULL,
  `log_target` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`log_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

CREATE TABLE `mentee` (
  `mentee_user_id` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'user.user_id (wp)',
  `mentee_user_name` varchar(255) DEFAULT NULL,
  `mentee_is_hidden` tinyint(3) unsigned NOT NULL DEFAULT 0 COMMENT '1=hide the name 0=otherwise',
  `mentee_remark` varchar(255) DEFAULT NULL,
  `mentee_lastupdate` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`mentee_user_id`),
  UNIQUE KEY `mentee_user_name` (`mentee_user_name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

CREATE TABLE `mentee_articles` (
  `ma_mentee_id` int(10) unsigned DEFAULT NULL COMMENT 'mentee.mentee_user_id',
  `ma_page_id` int(10) unsigned DEFAULT NULL COMMENT 'page.page_id',
  `ma_rev_id` int(10) unsigned DEFAULT NULL COMMENT 'revision.rev_id',
  `ma_creation_date` datetime DEFAULT NULL,
  UNIQUE KEY `ma_page_id` (`ma_page_id`),
  UNIQUE KEY `ma_rev_id` (`ma_rev_id`),
  KEY `ma_mentee_id` (`ma_mentee_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

CREATE TABLE `mentee_mentor` (
  `mm_mentee_id` int(10) unsigned NOT NULL COMMENT 'mentee.mentee_user_id',
  `mm_mentor_id` int(10) unsigned NOT NULL COMMENT 'mentor.mentor_user_id',
  `mm_start` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `mm_stop` datetime DEFAULT NULL,
  `mm_type` int(3) NOT NULL DEFAULT 0 COMMENT '0=not set, 1=normal, 2=wunschmentor',
  PRIMARY KEY (`mm_mentee_id`,`mm_mentor_id`,`mm_start`),
  KEY `mm_mentee_id` (`mm_mentee_id`),
  KEY `mm_mentor_id` (`mm_mentor_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

CREATE TABLE `mentees_recentchanges` (
  `rc_id` int(11) NOT NULL DEFAULT 0,
  `rc_timestamp` varbinary(14) NOT NULL DEFAULT '',
  `actor_id` bigint(20) unsigned NOT NULL DEFAULT 0,
  `actor_name` varbinary(255) NOT NULL DEFAULT '',
  `rc_namespace` int(11) NOT NULL DEFAULT 0,
  `rc_title` varbinary(255) NOT NULL DEFAULT '',
  `comment_text` blob DEFAULT NULL,
  `rc_minor` tinyint(3) unsigned NOT NULL DEFAULT 0,
  `rc_new` tinyint(3) unsigned NOT NULL DEFAULT 0,
  `rc_this_oldid` int(10) unsigned NOT NULL DEFAULT 0,
  `rc_last_oldid` int(10) unsigned NOT NULL DEFAULT 0,
  `rc_type` tinyint(3) unsigned NOT NULL DEFAULT 0,
  `rc_source` varbinary(16) NOT NULL DEFAULT '0',
  `rc_old_len` int(11) DEFAULT 0,
  `rc_new_len` int(11) DEFAULT 0,
  `rc_log_type` varbinary(255) DEFAULT '',
  `rc_params` blob DEFAULT NULL,
  PRIMARY KEY (`rc_id`),
  KEY `rc_timestamp` (`rc_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;

CREATE TABLE `mentor` (
  `mentor_user_id` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'user.user_id',
  `mentor_user_name` varchar(255) DEFAULT NULL,
  `mentor_login_password` char(40) DEFAULT NULL COMMENT 'SHA1 HEX',
  `mentor_pw_salt` char(40) DEFAULT NULL,
  `mentor_in` date DEFAULT NULL,
  `mentor_out` date DEFAULT NULL COMMENT 'NULL = active mentor; else: former mentor',
  `mentor_pause` int(1) NOT NULL DEFAULT 0,
  `mentor_award_level` tinyint(3) unsigned NOT NULL DEFAULT 0 COMMENT '0=nothing,1=bronze,2=silber,3=gold,4=platin,5=smaragd',
  `mentor_has_barnstar` tinyint(3) unsigned DEFAULT NULL COMMENT '0=no,1=yes',
  `mentor_remark` varchar(255) DEFAULT NULL,
  `mentor_lastupdate` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`mentor_user_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;
