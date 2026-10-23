-- Minimal stand-in for the dewiki_p replica views used by the app and the bot.
CREATE TABLE `user` (
  user_id int unsigned NOT NULL PRIMARY KEY,
  user_name varbinary(255) NOT NULL,
  user_editcount int DEFAULT NULL,
  UNIQUE KEY (user_name)
);
CREATE TABLE actor (
  actor_id bigint unsigned NOT NULL PRIMARY KEY,
  actor_user int unsigned DEFAULT NULL,
  actor_name varbinary(255) NOT NULL,
  UNIQUE KEY (actor_name)
);
CREATE TABLE page (
  page_id int unsigned NOT NULL PRIMARY KEY,
  page_namespace int NOT NULL,
  page_title varbinary(255) NOT NULL,
  page_touched binary(14) NOT NULL DEFAULT '20260101000000',
  UNIQUE KEY (page_namespace, page_title)
);
CREATE TABLE comment (
  comment_id bigint unsigned NOT NULL PRIMARY KEY,
  comment_text blob NOT NULL
);
CREATE TABLE revision_userindex (
  rev_id int unsigned NOT NULL PRIMARY KEY,
  rev_page int unsigned NOT NULL,
  rev_actor bigint unsigned NOT NULL,
  rev_comment_id bigint unsigned NOT NULL,
  rev_timestamp binary(14) NOT NULL,
  KEY (rev_actor, rev_timestamp)
);
CREATE TABLE category (
  cat_id int unsigned NOT NULL PRIMARY KEY,
  cat_title varbinary(255) NOT NULL,
  cat_pages int NOT NULL DEFAULT 0
);
CREATE TABLE linktarget (
  lt_id bigint unsigned NOT NULL PRIMARY KEY,
  lt_namespace int NOT NULL,
  lt_title varbinary(255) NOT NULL
);
CREATE TABLE categorylinks (
  cl_from int unsigned NOT NULL,
  cl_target_id bigint unsigned NOT NULL,
  cl_type enum('page','subcat','file') NOT NULL DEFAULT 'page',
  PRIMARY KEY (cl_from, cl_target_id)
);
CREATE TABLE recentchanges_userindex (
  rc_id int unsigned NOT NULL PRIMARY KEY,
  rc_timestamp binary(14) NOT NULL,
  rc_actor bigint unsigned NOT NULL,
  rc_namespace int NOT NULL DEFAULT 0,
  rc_title varbinary(255) NOT NULL,
  rc_comment_id bigint unsigned NOT NULL,
  rc_minor tinyint unsigned NOT NULL DEFAULT 0,
  rc_source varbinary(16) NOT NULL,
  rc_this_oldid int unsigned NOT NULL DEFAULT 0,
  rc_last_oldid int unsigned NOT NULL DEFAULT 0,
  rc_old_len int DEFAULT NULL,
  rc_new_len int DEFAULT NULL,
  rc_log_type varbinary(255) DEFAULT NULL,
  rc_params blob DEFAULT NULL
);
CREATE TABLE comment_recentchanges (
  comment_id bigint unsigned NOT NULL PRIMARY KEY,
  comment_text blob NOT NULL
);
