<?php
/*
 * Copyright (C) 2010 by Robin Krahl, Merlissimo and others
 * 
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see http://toolserver.org/~dewpmp.
 */

/**
 * This class provides access on MySQL databases. It’s primarily used for the 
 * Wikipedia and the MP databases. It tries to access the configuration file
 * __DIR__ . "/../../db_settings.ini". An example config file can be found at
 * __DIR__ . "/ ../../db_settings_default.ini".
 */
class Database
{
  /**
   * Database handle.
   */
  protected $db;
  protected $db_dewikip;
  private $mp_db_name;
  /**
   * MediaWiki timestamp format.
   */
  const timestamp_format = 'YmdHis';

  /**
   * Constructor. Connects with a database using the information in the
   * default_settings.ini and .my.cnf files.
   * @param $db the database to access or null to access the database specified
   *            in db_settings.ini
   */
  function __construct($db = null)
  {
    $ts_pw = posix_getpwuid(posix_getuid());
    $ts_mycnf = array();
    if (file_exists($ts_pw['dir'] . "/replica.my.cnf"))
    {
      $ts_mycnf = parse_ini_file($ts_pw['dir'] . "/replica.my.cnf");
    }
    if (file_exists(__DIR__ . "/../../db_settings.ini"))
    {
      $ts_mycnf = array_merge($ts_mycnf, parse_ini_file(__DIR__ . "/../../db_settings.ini"));
    }
    if (isset($db)) $ts_mycnf['dbname'] = $db;
    try
    {
      $mp_db_name = $ts_mycnf['dbname'];
      $this->db = new PDO("mysql:host=" . $ts_mycnf['host']. ";dbname=" . $mp_db_name,
                          $ts_mycnf['user'], $ts_mycnf['password'], array(
                            PDO::ATTR_PERSISTENT         => true,
			    PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES \'UTF8\''
                          ));
      $this->db_dewikip = new PDO("mysql:host=dewiki.labsdb;dbname=dewiki_p",
                          $ts_mycnf['user'], $ts_mycnf['password'], array(
                            PDO::ATTR_PERSISTENT         => true,
			    PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES \'UTF8\''
                          ));
      $stmt = $this->db->prepare("SET NAMES 'utf8'");
      $stmt->execute();
      $stmt = $this->db_dewikip->prepare("SET NAMES 'utf8'");
      $stmt->execute();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Returns the count of mentor datasets in the MP database.
   * @returns mentor count
   */
  public function getMentorCount()
  {
    try
    {
      $r = $this->db->query("SELECT COUNT(*) AS count FROM mentor");
      $result = $r->fetchAll();
      return (int) $result[0]["count"];
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns a list of all mentors.
   */
  public function get_all_mentors()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT * FROM mentor ORDER BY mentor_user_name;');
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all mentees.
   */
  public function get_all_mentees()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT * FROM mentee ORDER BY mentee_user_id;');
      $stmt->execute();
      $mentees = $stmt->fetchAll();
      foreach ($mentees as $key => $m)
      {
        $stmt = $this->db->prepare('SELECT mm_mentor_id FROM mentee_mentor WHERE mm_mentee_id = :id AND mm_stop IS NULL;');
	$stmt->execute(array(':id' => $m['mentee_user_id']));
	if ($stmt->rowCount() == 1)
	{
	  $i = $stmt->fetch();
	  $mentees[$key]['mentor_id'] = $i['mm_mentor_id'];
	}
	else
	{
	  $stmt = $this->db->prepare('SELECT mm_mentor_id FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY mm_start DESC;');
	  $stmt->execute(array(':id' => $m['mentee_user_id']));
	  $i = $stmt->fetch();
	  $mentees[$key]['mentor_id'] = $i['mm_mentor_id'];
	}
      }
      return $mentees;
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }
  
  /**
   * Returns a list of all active mentees.
   */
  public function get_all_active_mentees()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT mentee_user_name, mentee_user_id, mm_start, mentor_user_id, mentor_user_name FROM mentee JOIN (mentee_mentor, mentor) ON (mm_mentee_id = mentee_user_id AND mentor_user_id = mm_mentor_id) WHERE mm_stop IS NULL ORDER BY mm_start;');
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all active mentors.
   */
  public function get_all_active_mentors()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT mentor_user_name FROM mentor WHERE mentor_out IS NULL;');
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOEXception $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all mentors that are not archived yet and are not in the category anymore.
   */
  public function get_all_active_mentors_without_category()
  {
    try
    {
      // 1st step
      $stmtMentorsInDb = $this->db->prepare("SELECT mentor_user_name FROM " . $this->mp_db_name . ".mentor WHERE mentor_out IS NULL");
      $stmtMentorsInDb->execute();
      $mentorsInDbList = $stmtMentorsInDb->fetchAll();
      $mentorsInDbList = "'" . implode("','", array_map(function($n) { return $n[0];}, array_values($mentorsInDbList))) . "'";

      // 2nd step
      $mentor_cat_name = 'Benutzer:Mentor';
      $stmt = $this->db_dewikip->prepare("SELECT user_id AS mentor_user_id, page_title AS mentor_user_name FROM dewiki_p.page " .
                "JOIN dewiki_p.user ON user_name=page_title " .
                "WHERE page_namespace=2 AND page_title IN " .
		"(" . $mentorsInDbList . ") AND page_id NOT IN " . 
		"(SELECT cl_from FROM dewiki_p.categorylinks WHERE cl_to='" . $mentor_cat_name . "')");
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all mentor_mentee where the mm_type is not set (=0).
   * $ent_time can be null, otherwise it should be YYYY-MM-DD HH-MM-SS
   */
  public function get_mentor_mentee_history($end_time, $limit)
  {
    try
    {
      $sql = "SELECT mm_start AS event_time, mentee_mentor.mm_start, mm_stop, mm_mentee_id, mentee_user_name, mm_mentor_id, mentor_user_name " .
        "FROM mentee_mentor " .
        " JOIN mentee ON mm_mentee_id = mentee.mentee_user_id " .
        " JOIN mentor ON mm_mentor_id = mentor.mentor_user_id " .
        (validate_datestamp($end_time) ? "WHERE mm_start <= :end_time " : "") .
        "UNION ALL " .
        "SELECT mm_stop AS event_time, mm_start, mm_stop, mm_mentee_id, mentee_user_name, mm_mentor_id, mentor_user_name " .
        "FROM mentee_mentor " .
        " JOIN mentee ON mm_mentee_id = mentee.mentee_user_id " .
        " JOIN mentor ON mm_mentor_id = mentor.mentor_user_id " .
        (validate_datestamp($end_time) ? "WHERE mm_stop <= :end_time " : "") .
        "ORDER BY event_time DESC LIMIT :limit";
      $stmt = $this->db->prepare($sql);
      $stmt->bindParam(":limit",  $limit,  PDO::PARAM_INT);
      if (validate_datestamp($end_time)) {
          $stmt->bindParam(":end_time",  $end_time);
      }
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all mentor_mentee where the mm_type is not set (=0).
   */
  public function get_all_mentor_mentees_with_unset_type()
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mm_start, mm_stop, mentee_user_id, mentee_user_name, mentor_user_id, mentor_user_name FROM mentee_mentor " .
	"JOIN mentee ON mentee_mentor.mm_mentee_id = mentee.mentee_user_id " .
	"JOIN mentor ON mentee_mentor.mm_mentor_id = mentor.mentor_user_id " .
	"WHERE mm_type = 0 " .
	"ORDER BY mm_start ASC");
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of all mentor_mentee where the time slot between start and 'stop' is less than 24h.
   */
  public function get_all_mentor_mentees_with_short_mentoring()
  {
    $LIMIT = '24:00:00'; // hh:mm:ss
    try
    {
      $stmt = $this->db->prepare("SELECT mm_start, mm_stop, mentee_user_id, mentee_user_name, mentor_user_id, mentor_user_name, TIMEDIFF(mm_stop, mm_start) AS mm_length ".
	"FROM mentee_mentor " .
	"JOIN mentee ON mentee_mentor.mm_mentee_id = mentee.mentee_user_id " .
	"JOIN mentor ON mentee_mentor.mm_mentor_id = mentor.mentor_user_id " .
	"WHERE TIMEDIFF(mm_stop, mm_start) < '". $LIMIT ."' " .
	"ORDER BY TIMEDIFF(mm_stop, mm_start) ASC");
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of mentors in lexical order.
   * @param $offset the list’s offset
   * @param $count the list’s length
   * @param $no_activity_filter 0=return only active, 1=don't filter by activity status
   */
  public function getMentors($offset, $count, $no_activity_filter)
  {
    try
    {
      $whereCl = "";
      if ($no_activity_filter == 0)
      {
        $whereCl = " WHERE mentor.mentor_out IS NULL ";
      }
      $stmt = $this->db->prepare("SELECT mentor_user_id, mentor_user_name, mentor_login_password, mentor_pw_salt, mentor_in, mentor_out, " .
		"mentor_award_level, mentor_has_barnstar, mentor_remark, mentor_lastupdate, " .
		"COUNT(DISTINCT mm_active.mm_mentee_id) AS mm_active_mentee_count, " .
		"COUNT(DISTINCT mm_finished.mm_mentee_id) AS mm_finished_mentee_count " .
	"FROM mentor " .
	"LEFT OUTER JOIN mentee_mentor mm_active ON mm_active.mm_mentor_id=mentor.mentor_user_id AND mm_active.mm_stop IS NULL " .
	"LEFT OUTER JOIN mentee_mentor mm_finished ON mm_finished.mm_mentor_id=mentor.mentor_user_id AND mm_finished.mm_stop IS NOT NULL " .
	$whereCl .
	"GROUP BY mentor_user_id, mentor_user_name, mentor_login_password, mentor_pw_salt, mentor_in, mentor_out, mentor_award_level, mentor_has_barnstar, " .
		"mentor_remark, mentor_lastupdate " .
	"ORDER BY mentor_user_name LIMIT :count OFFSET :offset");
      $stmt->bindParam(":count",  $count,  PDO::PARAM_INT);
      $stmt->bindParam(":offset", $offset, PDO::PARAM_INT);
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns a list of all mentor user names.
   * @returns all mentor user names
   */
  public function getMentorNames()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT mentor_user_name FROM mentor ORDER BY mentor_user_name');
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns a list of all mentee user names.
   * @returns all mentee user names
   */
  public function getMenteeNames()
  {
    try
    {
      $stmt = $this->db->prepare('SELECT mentee_user_name FROM mentee ORDER BY mentee_user_name');
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns information about a mentor in array form (or an empty array if the
   * user doesn’t exist).
   * @param $id the mentor’s id
   * @returns information about the mentor
   */
  public function getMentorById($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentor WHERE mentor_user_id = :id LIMIT 1");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns information about a mentor in array form (or an empty array if the
   * user doesn’t exist).
   * @param $name the mentor’s name
   * @returns information about the mentor
   */
  public function getMentorByName($name)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentor WHERE mentor_user_name = :name LIMIT 1");
      $stmt->execute(array(":name" => $name));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns information about a mentor specified by his name.
   * @param $name the mentor’s name
   * @param $actives search for an active mentor
   * @param $inactives search for an inactive mentor
   * @returns information about the mentor
   */
  public function getMentorByNameAndActivity($name, $actives, $inactives)
  {
    if (!$actives && !$inactives)
    {
      return array();
    }

    try
    {
      $sql = 'SELECT * FROM mentor WHERE mentor_user_name = :name';
      if ($actives && !$inactives)
      {
        $sql .= ' AND mentor_out IS NULL';
      }
      elseif (!$actives && $inactives)
      {
        $sql .= ' AND mentor_out IS NOT NULL';
      }
      $sql .= ' LIMIT 1';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':name' => $name));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches mentors whose names match the regular expression $name_regexp.
   * @param $name_regexp a regular expression
   * @returns an array of matching mentors
   */
  public function getMentorsByNameRegExp($name_regexp)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentor WHERE mentor_user_name REGEXP :nameregexp ORDER BY mentor_user_name");
      $stmt->execute(array(":nameregexp" => $name_regexp));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches for mentors using a name regexp and regarding the activity.
   * @param $name_regexp a regular expression
   * @param $actives search active mentors
   * @param $inactives search inactive mentors
   */
  public function getMentorsByNameRegExpAA($name_regexp, $actives, $inactives)
  {
    if (!$actives && !$inactives)
    {
      return array();
    }

    try
    {
      $sql = 'SELECT * FROM mentor WHERE mentor_user_name REGEXP :nameregexp';
      if ($actives && !$inactives)
      {
        $sql .= ' AND mentor_out IS NULL';
      }
      elseif (!$actives && $inactives)
      {
        $sql .= ' AND mentor_out IS NOT NULL';
      }
      $sql .= ' ORDER BY mentor_user_name';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':nameregexp' => $name_regexp));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches a mentee by its ID.
   * @param $id the mentee id
   * @returns information about the mentee
   */
  public function getMenteeById($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentee WHERE mentee_user_id = :id LIMIT 1");
      $stmt->execute(array(":id" => $id));
      $result_mentee = $stmt->fetch();

      $stmt = $this->db->prepare("SELECT mm_start AS mentee_in FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY mm_start LIMIT 1;");
      $stmt->execute(array(":id" => $id));
      $result_mentee_in = $stmt->fetch();

      $stmt = $this->db->prepare("SELECT mm_stop AS mentee_out, mm_stop IS NULL AS isnull FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY isnull DESC, mm_stop DESC LIMIT 1;");
      $stmt->execute(array(":id" => $id));
      $result_mentee_out = $stmt->fetch();

      return array_merge($result_mentee, $result_mentee_in, 
                         $result_mentee_out);
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches a mentee by its name.
   * @param $name name to search
   * @returns information in an array
   */
  public function getMenteeByName($name)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentee WHERE mentee_user_name = :name LIMIT 1");
      $stmt->execute(array(":name" => $name));
      $result_mentee = $stmt->fetch();

      $stmt = $this->db->prepare("SELECT mm_start AS mentee_in FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY mm_start LIMIT 1;");
      $stmt->execute(array(":id" => $result_mentee['mentee_user_id']));
      $result_mentee_in = $stmt->fetch();

      $stmt = $this->db->prepare("SELECT mm_stop AS mentee_out, mm_stop IS NULL AS isnull FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY isnull DESC, mm_stop DESC LIMIT 1;");
      $stmt->execute(array(":id" => $result_mentee['mentee_user_id']));
      $result_mentee_out = $stmt->fetch();

      return array_merge($result_mentee, $result_mentee_in, 
                         $result_mentee_out);
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Get the mentee’s status information (mentee_in, mentee_out):
   */
  public function get_mentee_status($id) 
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mm_start AS mentee_in FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY mm_start LIMIT 1;");
      $stmt->execute(array(":id" => $id));
      $result_mentee_in = $stmt->fetch();

      $stmt = $this->db->prepare("SELECT mm_stop AS mentee_out, mm_stop IS NULL AS isnull FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY isnull DESC, mm_stop DESC LIMIT 1;");
      $stmt->execute(array(":id" => $id));
      $result_mentee_out = $stmt->fetch();

      return array_merge($result_mentee_in, $result_mentee_out);
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }


  /**
   * Add a mentee.
   */
  public function add_mentee($name, $userid)
  {
    try
    {
      $sql = "INSERT INTO mentee (mentee_user_id, mentee_user_name, mentee_user_name_normalized, mentee_in) VALUES (:userid, :name, :name, NOW())";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':userid' => $userid, ':name' => $name));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches mentors with certain conditions:
   *   - the user name ($name)
   *   - whether to search an active ($actives) and/or inactive ($inactives)
   *     mentor
   * @returns a matching mentor dataset or an empty array
   */
  public function getMenteeByNameAndActivity($name, $actives, $inactives)
  {
    if (!$actives && !$inactives)
    {
      return array();
    }

    try
    {
      $sql = 'SELECT * FROM mentee WHERE mentee_user_name = :name';
      if ($actives && !$inactives)
      {
        $sql .= ' AND mentee_out IS NULL';
      }
      elseif (!$actives && $inactives)
      {
        $sql .= ' AND mentee_out IS NOT NULL';
      }
      $sql .= ' LIMIT 1';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':name' => $name));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches mentees whose names match a certain regular expression 
   * ($name_regexp).
   * @returns a list of mentee datasets
   */
  public function getMenteesByNameRegExp($name_regexp)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentee WHERE mentee_user_name REGEXP :nameregexp ORDER BY mentee_user_name");
      $stmt->execute(array(":nameregexp" => $name_regexp));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Searches mentees with certain conditions:
   *   - a regular expression applied on the user name ($name_regexp)
   *   - whether to search an active ($actives) and/or inactive ($inactives)
   *     mentee
   * @returns a list of matching mentees
   */
  public function getMenteesByNameRegExpAA($name_regexp, $actives, $inactives)
  {
    if (!$actives && !$inactives)
    {
      return array();
    }

    try
    {
      $sql = 'SELECT mentee_user_id, mentee_user_name, MIN(mm_start) AS mentee_in, MAX(mm_stop) AS mentee_out FROM mentee '
          .' JOIN mentee_mentor ON mm_mentee_id = mentee_user_id'
          .' WHERE mentee_user_name REGEXP :nameregexp ';
      if ($actives && !$inactives)
      {
        $sql .= ' AND mm_stop IS NULL';
      }
      elseif (!$actives && $inactives)
      {
        $sql .= ' AND mm_stop IS NOT NULL';
      }
      $sql .= ' GROUP BY mentee_user_id, mentee_user_name';
      $sql .= ' ORDER BY mentee_user_name';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':nameregexp' => $name_regexp));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Archives a mentee.
   */
  public function archive_mentee($mentee_id)
  {
    try
    {
      $sql = "UPDATE mentee SET mentee_out = NOW() WHERE mentee_user_id = :id";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':id' => $mentee_id));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns a list of all mentors who took care of a certain mentee.
   * @param $id the mentee’s id
   * @return a list of mentor datasets
   */
  public function getMentorsByMentee($id)
  {
    try
    {
      $stmt = $this->db->prepare('SELECT mentor_user_id, mentor_user_name, mm_start, mm_stop, mm_type FROM mentee_mentor INNER JOIN mentor ON mm_mentor_id = mentor_user_id WHERE mm_mentee_id = :id ORDER BY mentor_user_name');
      $stmt->execute(array(':id' => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleErorr($ex->getMessage());
    }
  }

  /**
   * Returns all mentees a mentor ever took care of.
   * @param $id the mentor’s id
   * @returns an array with mentee datasets
   */
  public function getMenteesByMentor($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mentee_user_id, mentee_user_name, mm_start, mm_stop, mm_type FROM mentee_mentor INNER JOIN mentee ON mm_mentee_id=mentee_user_id WHERE mm_mentor_id = :id ORDER BY mm_start DESC");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns the count of mentorings and mentees a mentor ever took care of.
   * @param $id the mentor’s id
   * @returns the mentee count
   */
  public function getMenteeCountByMentor($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT COUNT(mm_mentee_id) AS mentee_mentor_count, COUNT(DISTINCT mm_mentee_id) mentee_count FROM mentee_mentor WHERE mm_mentor_id = :id");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  public function get_meta_data_by_mentor_name($mentor_name) {
    try
    {
      $main_page_name = "Mentorenprogramm";
      // check if timestamp of 'WP:MP' is younger than the last update for one mentor. If so, leave, otherwise update the meta data.
      $stmt = $this->db_dewikip->prepare("SELECT page_touched FROM dewiki_p.page WHERE page_title='" . $main_page_name . "' AND page_namespace=4 LIMIT 1");
      $stmt->execute();
      $mainPageTimestamp = $stmt->fetch();
      
      $stmt = $this->db->prepare("SELECT mentor_user_id FROM mentor JOIN comentors ON mentor_user_id = co_mentor_id WHERE mentor_lastupdate >" . $mainPageTimestamp[0] . " LIMIT 1");
      $stmt->execute();
      if (!$stmt->fetch()) { // Update needed
          $raw_data = $this->reload_mentor_meta_data($main_page_name);
          if (empty($raw_data)) {
              return array();
          }
 
          // Load all Mentor IDs
          $stmt = $this->db->prepare("SELECT mentor_user_name, mentor_user_id FROM mentor");
          $stmt->execute();
          $mentorIdMap = $stmt->fetchAll(PDO::FETCH_COLUMN|PDO::FETCH_GROUP);

          // build UPDATE string
          $valueSqlString = "START TRANSACTION; DELETE FROM comentors; INSERT INTO comentors (co_mentor_id, co_comentor_id) VALUES";
          $counter = 0;
          foreach($raw_data as $mentorName => $mentorMetaData) {
             if (!array_key_exists($mentorName, $mentorIdMap)) { continue; }
             $mentorId = $mentorIdMap[$mentorName][0];
             foreach($mentorMetaData['comentors'] as $coMentorName) {
                if (!array_key_exists($coMentorName, $mentorIdMap)) { continue; }
                $coMentorId = $mentorIdMap[$coMentorName][0];
                if ($mentorId and $coMentorId) {
print($mentorName . '--> ' . $coMentorName . '\n ');
                   $valueSqlString .= ($counter==0?"":",") . "(" . $mentorId . "," . $coMentorId . ")";
                   $counter++;
                }
             }
          }
          // update mentor.last_update
          $valueSqlString .= "; UPDATE mentor SET mentor_lastupdate = NOW() WHERE mentor_user_id IN (SELECT DISTINCT co_mentor_id FROM comentors);";
          $valueSqlString .= "COMMIT;";

          // exucute it
          $stmt = $this->db->prepare($valueSqlString);
          $stmt->execute();
      }
      $stmtCo = $this->db->prepare("SELECT co_comentor_id, cm.mentor_user_name comentor_name FROM comentors JOIN mentor m ON m.mentor_user_id = co_mentor_id JOIN mentor cm ON cm.mentor_user_id = co_comentor_id WHERE m.mentor_user_name = :name");
      $stmtCo->execute(array(":name" => $mentor_name));
      $stmtCoOf = $this->db->prepare("SELECT co_mentor_id, m.mentor_user_name comentor_name FROM comentors JOIN mentor m ON m.mentor_user_id = co_mentor_id JOIN mentor cm ON cm.mentor_user_id = co_comentor_id WHERE cm.mentor_user_name = :name");
      $stmtCoOf->execute(array(":name" => $mentor_name));
      return array('comentors' => $stmtCo->fetchAll(), 'comentorOf' => $stmtCoOf->fetchAll());
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    } 
  }
  
  /**
   * Returns a dic of co-mentors that are related to a certain mentor.
   */
  private function reload_mentor_meta_data($main_page_name)
  {
      // 1.1 WMFLabs databases do not offer 'text' table, so we only can send an api request
      $response = file_get_contents("https://de.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&format=xml&titles=Wikipedia:" . $main_page_name);
      $xml = new SimpleXMLElement($response);
      $content = $xml->query->pages->page->revisions->rev;
      $content = preg_replace("/\<!\-\-.+\-\->/", "", $content); // remove comments
      // 1.2 split the templates, we can't use regex here
      $matchedSnipps = array();
      $openBrackets = 0;
      $tmpSnipp = "";
      foreach (str_split($content) as $c) {
         if ($c == "{") {
             $openBrackets += 1;
         } elseif ($c == "}") {
             $openBrackets -= 1;
             if ($openBrackets == 0) {
                $matchedMentors[] = $tmpSnipp;
                $tmpSnipp = "";
             }
         }
         if ($openBrackets >= 2) {
             $tmpSnipp .= $c;
         }
      }
      // 1.3 extract each template
      $mentors_cm = array();
      foreach ($matchedMentors as $templateSnippet) {
         $mentor = null;
         $coment = array();
         $pause = false;
         if (preg_match_all("/\|[\n\r\s]*Mentor[\n\r\s]*=[\n\r\s]*([^|}\n\r]+)[\n\r\s]*\|/", $templateSnippet, $match)) {
            $mentor = $match[1][0];
         } else {
            continue;
         }
         foreach (array(1,2,3,4) as $n) {
            if (preg_match_all("/\|[\n\r\s]*Co-Mentor" . $n . "[\n\r\s]*=[\n\r\s]*([^|}\n\r]+)[\n\r\s]*\|/", $templateSnippet, $match)) {
               $trimmedCo = trim($match[1][0]);
               if ($trimmedCo) {
                   $coment[] = $trimmedCo;
               }
            }
         }
         if (preg_match_all("/\|[\n\r\s]*Pause[\n\r\s]*=[\n\r\s]*ja[\n\r\s]*\|/", $templateSnippet, $match)) {
            $pause = true;
         }
         $mentors_cm[$mentor] = array("comentors" => $coment, "pause" => $pause);
      }
      // 2. now write it to database
      // 2.1 set mentor_pause to the initial value 0
      try {
         $stmt = $this->db->prepare('UPDATE mentor SET mentor_pause=0, mentor_lastupdate=NOW() WHERE mentor_pause = 1;');
         $stmt->execute();
      } catch (PDOException $ex) {
         $this->handleError($ex->getMessage());
      }
      // 2.2 update 'pause'
      foreach ($mentors_cm as $mentor_name => $mentor_meta) {
         if ($mentor_meta['pause'] == 1) {
            try {
               $stmt = $this->db->prepare('UPDATE mentor SET mentor_pause=1, mentor_lastupdate=NOW() WHERE mentor_name=\'' . $mentor_name . '\'');
               $stmt->execute();
            } catch (PDOException $ex) {
               $this->handleError($ex->getMessage());
            }
         }
      }
      return $mentors_cm;
  }
  /**
   * Returns a list of mentors that are co-mentors of a certain mentor.
   * @param $id the mentor’s id
   * @returns a list of mentor datasets
   */
  public function get_comentors_by_mentor_id($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM comentors INNER JOIN mentor ON co_comentor_id = mentor_user_id WHERE co_mentor_id = :id ORDER BY mentor_user_name");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Returns a list of artciles created by a certain mentee.
   * @param $id the mentee’s id
   * @returns the mentee’s article datasets
   */
  public function getArticlesByMenteeId($id)
  {
    try
    {
      $stmt = $this->db->prepare('SELECT * FROM mentee_articles WHERE ma_mentee_id = :id ORDER BY ma_creation_date DESC');
      $stmt->execute(array(':id' => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Update a mentor dataset.
   * @param $id mentor id
   * @param $user_name new user name
   * @param $in new in date
   * @param $out new out date
   * @param $barnstar new barnstar state
   * @param $award new award state
   * @param $remark new remark
   */
  public function updateMentor($id, $user_name, $in, $out,
                               $barnstar, $award, $remark)
  {
    try
    {
      // write NULL if $out is emtpy
      if (empty($out) || $out == '0000-00-00') {
          $out = NULL;
      }
      $stmt = $this->db->prepare('UPDATE mentor SET ' .
                         'mentor_user_name = :user_name, ' .
                         'mentor_in = :in, ' .
                         'mentor_out = :out, ' .
                         'mentor_has_barnstar = :barnstar, ' .
                         'mentor_award_level = :award, ' .
                         'mentor_remark = :remark ' .
                         'WHERE mentor_user_id = :id');
      $stmt->execute(array(':id' => $id,
                           ':user_name' => $user_name,
                           ':in' => $in,
                           ':out' => $out,
                           ':barnstar' => (int) $barnstar,
                           ':award' => $award,
                           ':remark' => $remark));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Update a mentee dataset.
   * @param int    $id        the mentee id specifies which mentee to update
   * @param string $user_name the updated user name
   * @param string $remark    the updated remark
   */
  public function updateMentee($id, $user_name, $remark)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentee SET ' .
                                 'mentee_user_name = :user_name, ' .
                                 'mentee_remark = :remark ' .
                                 'WHERE mentee_user_id = :id');
      $stmt->execute(array(':id' => $id,
                           ':user_name' => $user_name,
                           ':remark' => $remark));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Counts the currently active mentees and mentors.
   * @return the count of active mentees and mentors
   */
  public function getCountsDB()
  {
    try
    {
      $rv = array();
      $q = $this->db->query("SELECT COUNT(*) as mentor_count_db FROM mentor WHERE mentor_out IS NULL");
      $rv = array_merge($rv, $q->fetch());
      $q = $this->db->query("SELECT COUNT(*) as newbie_count_db FROM mentee_mentor WHERE mm_stop IS NULL");
      $rv = array_merge($rv, $q->fetch());
      return $rv;
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Counts all mentees and mentors ever.
   * @return the mentee and mentor counts
   */
  public function getCountsAllDB()
  {
    try
    {
      $rv = array();
      $q = $this->db->query("SELECT COUNT(*) as mentor_count_all_db FROM mentor");
      $rv = array_merge($rv, $q->fetch());
      $q = $this->db->query("SELECT COUNT(*) as mentee_count_all_db FROM mentee");
      $rv = array_merge($rv, $q->fetch());
      return $rv;
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Get the login password hash and the salt for a certain mentor.
   * @param string $user the mentor’s user name
   * @returns the mentor’s password hash and salt or -1 if the mentor doesn’t exist or something was not set.
   */
  public function get_hash_and_salt_for_user($user)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mentor_login_password, mentor_pw_salt FROM mentor WHERE mentor_user_name = :user");
      $stmt->execute(array(":user" => $user));
      $result = $stmt->fetch();
      if (isset($result['mentor_login_password']) and isset($result['mentor_pw_salt']))
      {
        return $result;
      }
      else
      {
        return -1;
      }
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Update the password hash for a mentor.
   * @param string $user the mentor’s user name
   * @param sha1   $hash the new salted password hash
   * @param salt   $salt the salt you used
   */
  public function set_hash_and_salt_for_user($user, $hash_with_salt, $salt)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentor SET mentor_login_password = :hs, mentor_pw_salt = :salt WHERE mentor_user_name = :user');
      $stmt->execute(array(':hs' => $hash_with_salt, ':salt' => $salt, ':user' => $user));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Get mentee/mentor relations meeting certain requirements.
   * @param int    $mentor_id the mentor’s id or 0
   * @param int    $mentee_id the mentee’s id or 0
   * @param string $start     the relation start or ""
   * @param string $stop      the relation end or ""
   * @returns a list of all mentee/mentor relations that meet the 
   *          requirements specified by the parameters (0 or "" is a wildcard).
   */
  public function get_mm_items($mentor_id, $mentee_id, $start, $stop)
  {
    try
    {
      $sql = 'SELECT * FROM mentee_mentor WHERE ';
      $args = array();
      $first = true;
      if (!($mentor_id === ''))
      {
        if ($first)
          $first = false;
        else
          $sql .= 'AND ';
        $sql .= 'mm_mentor_id = :mentor_id ';
        $args[':mentor_id'] = $mentor_id;
      }
      if (!($mentee_id === ''))
      {
        if ($first)
          $first = false;
        else
          $sql .= 'AND ';
        $sql .= 'mm_mentee_id = :mentee_id ';
        $args[':mentee_id'] = $mentee_id;
      }
      if (!($start === ''))
      {
        if ($first)
          $first = false;
        else
          $sql .= 'AND ';
        $sql .= 'mm_start = :start ';
        $args[':start'] = $start;
      }
      if (!($stop === ''))
      {
        if ($first)
          $first = false;
        else
          $sql .= 'AND ';
        $sql .= 'mm_stop = :stop ';
        $args[':stop'] = $stop;
      }
      $sql .= 'ORDER BY mm_start;';
      $stmt = $this->db->prepare($sql);
      $stmt->execute($args);
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Get all current mm relations of a certain mentee.
   * @param int $mentee_id the mentee’s id
   * @return a list of mm items
   */
  public function get_mm_items_by_mentee_id($mentee_id)
  {
    try
    {
      $sql = "SELECT * FROM mentee_mentor WHERE mm_mentee_id = :menteeid AND mm_stop IS NULL";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':menteeid' => $mentee_id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Update the start or stop of a mentee/mentor relation.
   * @param int    $mentor_id the mentor’s id
   * @param int    $mentee_id the mentee’s id
   * @param string $ostart    the old start
   * @param string $ostop     the old stop
   * @param int    $new_mentor_id    the new mentor user id
   * @param string $start     the updated start
   * @param string $stop      the updated stop
   * @param int    $type      the updated type
   */
  public function update_mm_item($mentor_id, $mentee_id, $ostart, $ostop, $new_mentor_id, $start, $stop, $type)
  {
    try
    {
      $args = array(':mentor_id' => $mentor_id,
                    ':mentee_id' => $mentee_id,
                    ':ostart'    => $ostart,
                    ':new_mentor_id' => $new_mentor_id,
                    ':start'     => $start,
                    #':stop'      => $stop,
                    ':type'      => $type);
      $sql = "UPDATE mentee_mentor SET mm_mentor_id = :new_mentor_id, mm_type = :type, mm_start = :start, ";
      if ($stop === '')
        $sql .= "mm_stop = NULL";
      else
      {
        $sql .= "mm_stop = :stop";
        $args[':stop'] = $stop;
      }
      $sql .= " WHERE mm_mentor_id = :mentor_id AND mm_mentee_id = :mentee_id AND mm_start = :ostart AND ";
      if ($ostop === '')
        $sql .= "mm_stop IS NULL";
      else
      {
        $sql .= "mm_stop = :ostop";
        $args[':ostop'] = $ostop;
      }
      $stmt = $this->db->prepare($sql);
      $stmt->execute($args);
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

   /**
    * Delete all matching mentee_mentor datasets.
    * @param int    $mentor_id the mentor’s id
    * @param int    $mentee_id the mentee’s id
    * @param string $mm_start
    */
  public function delete_mm_item($mentor_id, $mentee_id, $mm_start)
  {
    try
    {
      $args = array(':mentor_id' => $mentor_id,
                    ':mentee_id' => $mentee_id,
                    ':mm_start'  => $mm_start);
      $sql = "DELETE FROM mentee_mentor WHERE mm_mentor_id = :mentor_id AND mm_mentee_id = :mentee_id AND mm_start = :mm_start LIMIT 1";
      $stmt = $this->db->prepare($sql);
      $rows = $stmt->execute($args);
      return $rows == 1; // 1 row deleted FIXME wird nichts geloescht
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }


  /**
   * Archive a mentee/mentor relation.
   */
  public function archive_mm_item($mentor_id, $mentee_id, $start, $stop)
  {
    try
    {
      $sql = "UPDATE mentee_mentor SET mm_stop = NOW() WHERE mm_mentor_id = :mentorid AND mm_mentee_id = :menteeid AND mm_start = :start AND mm_stop IS NULL";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':mentorid' => $mentor_id, ':menteeid' => $mentee_id, ':start' => $start));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Add a mm item.
   */
  public function add_mm_item($mentor_id, $mentee_id, $start, $stop, $type)
  {
    try
    {
      $args = array(':mentor_id' => $mentor_id,
                    ':mentee_id' => $mentee_id,
                    ':start'     => $start,
                    #':stop'      => $stop,
                    ':type'      => $type);
      $sql = "INSERT INTO mentee_mentor (mm_mentor_id, mm_mentee_id, mm_start, mm_stop, mm_type) VALUES (:mentor_id, :mentee_id, :start, ";
      if ($stop === '')
      {
        $sql .= "NULL, ";
      }
      else
      {
        $sql .= ":stop, ";
        $args[':stop'] = $stop;
      }
      $sql .= " :type)";
      $stmt = $this->db->prepare($sql);
      $stmt->execute($args);
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Get the count of mentees and mentors currently active. The functionen uses
   * the categories ‘Benutzer:Mentor’ and 'Mentee’.
   * @return mentee/mentor count
   */
  public function getCountsWP()
  {
    try
    {
      $rv = array();
      $q = $this->db_dewikip->query("SELECT cat_pages as newbie_count_wp FROM dewiki_p.category WHERE `cat_title` = 'Benutzer:Mentee'");
      $rv = array_merge($rv, $q->fetch());
      $q = $this->db_dewikip->query("SELECT cat_pages as mentor_count_wp FROM dewiki_p.category WHERE `cat_title` = 'Benutzer:Mentor'");
      $rv = array_merge($rv, $q->fetch());
      return $rv;
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
    return array();
  }

  /**
   * Returns a list of all users in the category 'Benutzer:Mentee'.
   */
  public function get_all_wp_mentees()
  {
    try
    {
      $q = $this->db->query("SELECT page_title FROM dewiki_p.page JOIN dewiki_p.categorylinks ON cl_from = page_id WHERE cl_to = 'Benutzer:Mentee'");
      return $q->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
    return array();
  }

  /**
   * Get the edit count of a Wikipedia user.
   * @param $id the user’s MediaWiki id
   * @returns the edit count
   */
  public function get_user_edit_count($user_id)
  {
    try
    {
      $stmt = $this->db_dewikip->prepare('SELECT COUNT(*) AS edit_count FROM dewiki_p.revision_userindex ' .
          'JOIN actor ON actor_id = rev_actor WHERE actor_user = :id');
      $stmt->execute(array(':id' => $user_id));
      $line = $stmt->fetch();
      return $line['edit_count'];
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Get the user page hostory of a Wikipedia user.
   * @param $name the user’s MediaWiki name
   * @returns the fields
   */
  public function get_user_page_history($user_name)
  {
    try
    {
      $stmt = $this->db_dewikip->prepare('SELECT rev_timestamp, actor_name, comment_text FROM dewiki_p.revision_userindex ' .
           'JOIN dewiki_p.page ON rev_page=page_id AND page_namespace = 2 AND page_title = :user_name ' .
           'JOIN dewiki_p.comment ON comment_id = rev_comment_id ' .
           'JOIN dewiki_p.actor ON rev_actor = actor_id ' .
           'ORDER BY rev_timestamp DESC LIMIT 50');
      # white space -> _
      $stmt->execute(array(':user_name' => str_replace(' ', '_', $user_name)));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Check if a user is active.
   * @param $id the user’s MediaWiki id
   * @returns boolean value
   */
  public function is_user_active($user_id, $delay = '-1 month')
  {
    try
    {
      $stmt = $this->db_dewikip->prepare('SELECT COUNT(1) AS active FROM (' . 
          'SELECT rev_id FROM dewiki_p.revision_userindex ' .
          'JOIN actor ON actor_id = rev_actor ' .
          'WHERE actor_user = :id AND rev_timestamp between :start and :end LIMIT 1' .
          ') i');
      $now   = time();
      $start = date(self::timestamp_format, strtotime($delay, $now));
      $end   = date(self::timestamp_format, $now);
      $stmt->execute(array(':id' => $user_id, ':start' => $start, ':end' => $end));
      $row   = $stmt->fetch();
      return (bool) $row['active'];
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns the name of the corresponding article.
   * @param $id article id
   */
  public function get_article_name_by_id($id)
  {
    try
    {
      $stmt = $this->db_dewikip->prepare('select page_title from dewiki_p.page where page_id = :id');
      $stmt->execute(array(':id' => $id));
      $row = $stmt->fetch();
      return preg_replace('/_/', ' ', $row['page_title']);
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns user's last edit.
   */
  public function get_users_recent_edit_timestamp($user_id)
  {
    try
    {
      $sql   = 'SELECT rev_timestamp AS last_edit FROM dewiki_p.revision_userindex ' .
      'JOIN actor ON actor_id = rev_actor ' .
      'WHERE actor_user = :user ORDER BY rev_timestamp DESC LIMIT 1;';
      $stmt  = $this->db_dewikip->prepare($sql);
      $stmt->execute(array(':user' => $user_id));
      $row = $stmt->fetch();
      return $row['last_edit'];
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Checks if a user did edit.
   */
  public function has_recent_edit($user_id, $delay = '-60 days')
  {
    try
    {
      $now   = time();
      $start = date(self::timestamp_format, strtotime($delay, $now));
      $end   = date(self::timestamp_format, strtotime('1 second', $now));
      $sql   = 'SELECT COUNT(1) AS has_edit FROM (SELECT rev_id FROM dewiki_p.revision_userindex ' .
      'JOIN actor ON actor_id = rev_actor ' .
      'WHERE actor_user = :user AND rev_timestamp BETWEEN :start AND :end LIMIT 1) i;';
      $stmt  = $this->db_dewikip->prepare($sql);
      $stmt->execute(array(':user' => $user_id, ':start' => $start, ':end' => $end));
      $row = $stmt->fetch();
      return (bool) $row['has_edit'];
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns the MW user id or -1 for certain user name.
   */
  public function get_user_id($user_name)
  {
    try
    {
      $sql = "SELECT * FROM dewiki_p.user WHERE user_name = :name";
      $stmt = $this->db_dewikip->prepare($sql);
      $stmt->execute(array(':name' => $user_name));
      $row = $stmt->fetch();
      if (!($row === false))
      {
	return (int) $row['user_id'];
      }
      return -1;
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns a list of mentors with different user names stored in mentor and
   * dewiki_p.user.
   */
  public function get_renamed_mentors()
  {
    try
    {
      $sql = "SELECT mentor_user_id, mentor_user_id, mentor_user_name, user_name FROM mentor JOIN dewiki_p.user ON mentor_user_id = user_id WHERE mentor_user_name != user_name";
      $stmt = $this->db_dewikip->prepare($sql);
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Renames a mentor.
   *  XXX veraltet?
   */
  public function rename_mentor($mentor_id, $new_name)
  {
    try
    {
      $sql = 'UPDATE mentor SET mentor_user_name = :name WHERE mentor_user_id = :id';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':name' => $new_name, ':id' => $mentor_id));
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Return a list of mentors who are no longer in the mentor category.
   */
  public function get_archived_mentors($mentor_cat)
  {
    try // TODO JOIN per code duerchfueren
    {
      $sql = 'SELECT mentor_user_name, mentor_user_id FROM mentor WHERE mentor_out IS NULL AND NOT EXISTS (SELECT cl_from FROM dewiki_p.categorylinks JOIN dewiki_p.page ON page_id = cl_from WHERE page_title = REPLACE(mentor_user_name, \' \', \'_\') AND page_namespace = 2 AND cl_to = :cat);';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':cat' => $mentor_cat));
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }
  
  /**
   * Archives a mentor.
   *  XXX veraltet?
   */
  public function archive_mentor($mentor_id)
  {
    try
    {
      $sql = 'UPDATE mentor SET mentor_out = CURRENT_DATE() WHERE mentor_user_id = :id';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':id' => $mentor_id));
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Returns a list of mentors who are in the mentor category but not in the database.
   */
   public function get_new_mentors($mentor_cat)
   {
     try // TODO JOIN aufloesen
     {
       $sql = 'SELECT REPLACE(page_title, \'_\', \' \') AS mentor_name, user_id FROM dewiki_p.categorylinks JOIN (dewiki_p.page, dewiki_p.user) ON (page_id = cl_from AND REPLACE(user_name, \' \', \'_\') = page_title) WHERE cl_to = :cat AND page_namespace = 2 AND NOT EXISTS (SELECT mentor_user_id FROM mentor WHERE mentor_user_id = user_id AND mentor_out IS NULL);';
       $stmt = $this->db_dewikip->prepare($sql);
       $stmt->execute(array(':cat' => $mentor_cat));
       return $stmt->fetchAll();
     }
     catch (PDOException $e)
     {
       $this->handleError($e->getMessage());
     }
   }

  /**
   * Adds a new mentor.
   */
  public function add_mentor($user_id, $user_name)
  {
    try
    {
      $sql = 'INSERT INTO mentor (mentor_user_id, mentor_user_name, mentor_user_name_normalized, mentor_login_name, mentor_in) VALUES (:id, :name, :name, :name, CURRENT_DATE());';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':name' => $user_name, ':id' => $user_id));
      $sql = 'UPDATE mentor SET mentor_out = NULL WHERE mentor_user_id = :id';
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':id' => $user_id));
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Logs a message in the `logging` table.
   */
  public function log($user, $comment, $action, $target)
  {
    try
    {
      $sql = "INSERT INTO logging (log_comment, log_user_name, log_type, log_target) VALUES (:comment, :user, :type, :target);";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':comment' => $comment, ':user' => $user, ':type' => $action, ':target' => $target));
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  /**
   * Gets the recent 50 entries from the `logging` table.
   */
  public function get_log_entries()
  {
    try
    {
      $sql = "SELECT log_id, log_date, log_comment, log_user_name, log_type, log_target FROM logging ORDER BY log_date DESC LIMIT 50";
      $stmt = $this->db->prepare($sql);
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }   
  }

  /**
   * Anzahl der neuer und alter Betreuungen gruppiert nach Wochen.
   * Achtung, wenn es keine neuen in der Woche gab, werden die entlassenden nicht
   * ausgegeben. Damit kann man hoffentlich leben.
   */
  public function get_stats_mentees()
  {
    try
    {
      $sql = "SELECT s_year, s_week, s_count, e_count FROM (SELECT YEARWEEK(mm_start) AS s_year_week, SUBSTRING(YEARWEEK(mm_start),1,4) as s_year, SUBSTRING(YEARWEEK(mm_start),5,2) as s_week, COUNT(mm_mentee_id) as s_count FROM `mentee_mentor` " .
             "GROUP BY SUBSTRING(YEARWEEK(mm_start),1,4), SUBSTRING(YEARWEEK(mm_start),5,2) " .
             ") AS a LEFT JOIN (" .
             "SELECT YEARWEEK(mm_stop) AS e_year_week, COUNT(mm_mentee_id) as e_count FROM `mentee_mentor` " .
             "GROUP BY SUBSTRING(YEARWEEK(mm_stop),1,4), SUBSTRING(YEARWEEK(mm_stop),5,2) " .
             ") AS b ON s_year_week = e_year_week " .
             "ORDER BY s_year DESC, s_week ASC";
      $stmt = $this->db->prepare($sql);
      $stmt->execute();
      return $stmt->fetchAll();
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }   
  }

  /**
   * Get the recent changes for the current Mentees only.
   * $start_time    show only changes happened AFTER or at $start_time
   * $end_time      show only changes happened BEFORE or at $end_time
   * $limit         show only $limit number of results
   */
  public function get_recent_mentee_edits($start_time, $end_time, $limit)
  {
    try
    {
      $sql = "SELECT rc_timestamp, actor_id, actor_name, rc_namespace, rc_title, comment_text,
                rc_minor, rc_new, rc_this_oldid, rc_last_oldid, rc_type, rc_source,
                rc_old_len, rc_new_len, rc_params,
                rc_log_type " .
             "FROM mentees_recentchanges " .
             "WHERE 1=1 " .
             (validate_timestamp_with_seconds($start_time) ? "AND rc_timestamp >= :start_time " : "") .
             (validate_timestamp_with_seconds($end_time) ? "AND rc_timestamp <= :end_time " : "") .
             "ORDER BY rc_timestamp DESC " .
             "LIMIT :limit;";
      $stmt = $this->db->prepare($sql);
      if (validate_timestamp_with_seconds($start_time)) {
          $stmt->bindParam(":start_time", $start_time);
      }
      if (validate_timestamp_with_seconds($end_time)) {
          $stmt->bindParam(":end_time", $end_time);
      }
      $stmt->bindParam(":limit", $limit, PDO::PARAM_INT);
      $stmt->execute();
      return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

  private function fetch_latest_timestamp_form_mentees_rc()
  {
    try
    {
      $stmt = $this->db->prepare("SELECT MAX(rc_timestamp) FROM mentees_recentchanges;");
      $stmt->execute();
      return $stmt->fetchAll()[0][0];
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }   
  }

  private function placeholders($text, $count=0, $separator=",")
  {
      $result = array();
      for ($x=0; $x<$count; $x++) {
          $result[] = $text;
      }
      return implode($separator, $result);
  }

  private function insert_new_data_in_mentees_rc($datafields, $results_from_dewikip)
  {
     $insert_values = array();
     $row_values = array();
     foreach($results_from_dewikip as $row) {
         $escaped_row = array();
         foreach ($row as $raw_value) {
            $escaped_row[] = "'" . str_replace("'", "\'", $raw_value) . "'";
         }
         $row_values[] = '(' . implode(",", $escaped_row) . ')';
     }
     
     $sql = "START TRANSACTION; INSERT INTO mentees_recentchanges (" . implode(",", $datafields ) . ") VALUES " .
            implode(',', $row_values) . "; COMMIT;";
     try {
         $stmt = $this->db->prepare($sql);
         $stmt->execute();
     } catch (PDOException $e) {
         $this->handleError($e->getMessage());
     }
  }

  private function delete_old_data_in_mentees_rc($end_time)
  {
     try {
         $stmt = $this->db->prepare("DELETE FROM mentees_recentchanges WHERE rc_timestamp < :end_time;");
         $stmt->bindParam(":end_time", $end_time);
         $stmt->execute();
     } catch (PDOException $e) {
         $this->handleError($e->getMessage());
     }
  }

  /**
   * Fetches the recent changes since last run and add them into the local table. The local
   * table is much smaller and has an index on column rc_timestamp'.
   */
  public function update_mentees_recentchanges()
  {
    $COLUMNS = "rc_id, rc_timestamp, actor_id, actor_name, rc_namespace, rc_title, comment_text,"
                . "rc_minor, rc_new, rc_this_oldid, rc_last_oldid, rc_type, rc_source,"
                . "rc_old_len, rc_new_len, rc_params, rc_log_type ";
    
    try
    {
      // 1. what was the last timestamp we have in the local table?
      $start_time = $this->fetch_latest_timestamp_form_mentees_rc();
      echo("latest timestamp form mentees_recentchanges: " . $start_time . "\n");
      
      // 2. fetch new data from the replicated database
      $source_sql = "SELECT ". $COLUMNS .
             "FROM categorylinks " .
             "JOIN page ON cl_from=page_id AND page_namespace=2 " .
             "JOIN actor ON actor_name=REPLACE(page_title, '_', ' ') " .
             "JOIN recentchanges_userindex ON rc_actor=actor_id " .
             "JOIN comment_recentchanges ON rc_comment_id=comment_id " .
             "WHERE cl_to = 'Benutzer:Mentee' " .
             (validate_timestamp_with_seconds($start_time) ? "AND rc_timestamp > :start_time;" : ";");
      $stmt = $this->db_dewikip->prepare($source_sql);
      if (validate_timestamp_with_seconds($start_time)) {
          $stmt->bindParam(":start_time", $start_time);
      }
      $stmt->execute();
      $results_from_dewikip = $stmt->fetchAll(PDO::FETCH_ASSOC);
      echo("found " . sizeof($results_from_dewikip) . " new entries in dewiki_p\n");
      
      // 3. put all this data into the local RC table
      $this->insert_new_data_in_mentees_rc(preg_split('/,/i', $COLUMNS), $results_from_dewikip);
      
      // 4. delete old entries
      $date_30_days_ago = date_format(new DateTime("- 30 days"), 'YmdHis');
      $this->delete_old_data_in_mentees_rc($date_30_days_ago);
    }
    catch (PDOException $e)
    {
      $this->handleError($e->getMessage());
    }
  }

   /*
    * Create a string representing the executed query.
    */
   private function sql_debug($sql_string, array $params = null)
   {
       if (!empty($params)) {
           $indexed = $params == array_values($params);
           foreach($params as $k=>$v) {
               if (is_object($v)) {
                   if ($v instanceof \DateTime) $v = $v->format('Y-m-d H:i:s');
                   else continue;
               }
               elseif (is_string($v)) $v="'$v'";
               elseif ($v === null) $v='NULL';
               elseif (is_array($v)) $v = implode(',', $v);
   
               if ($indexed) {
                   $sql_string = preg_replace('/\?/', $v, $sql_string, 1);
               }
               else {
                   if ($k[0] != ':') $k = ':'.$k; //add leading colon if it was left out
                   $sql_string = str_replace($k,$v,$sql_string);
               }
           }
       }
       return $sql_string;
   }

  /**
   * Prints an error message and quits the application.
   * @param string $msg error message
   */
  protected function handleError($msg)
  {
    die("<p class='error'>Datenbank-Fehler: <pre>" . $msg . "</pre></p>");
  }

}
