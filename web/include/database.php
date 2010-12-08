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
    if (file_exists($ts_pw['dir'] . "/.my.cnf"))
    {
      $ts_mycnf = parse_ini_file($ts_pw['dir'] . "/.my.cnf");
    }
    if (file_exists(__DIR__ . "/../../db_settings.ini"))
    {
      $ts_mycnf = array_merge($ts_mycnf, parse_ini_file(__DIR__ . "/../../db_settings.ini"));
    }
    if (isset($db)) $ts_mycnf['dbname'] = $db;
    try
    {
      $this->db = new PDO("mysql:host=" . $ts_mycnf['host']. ";dbname=" . $ts_mycnf['dbname'],
                          $ts_mycnf['user'], $ts_mycnf['password'], array(
                            PDO::ATTR_PERSISTENT         => true
                          ));
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
      $stmt = $this->db->prepare('SELECT * FROM mentor ORDER BY mentor_id;');
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
      $stmt = $this->db->prepare('SELECT * FROM mentee ORDER BY mentee_in;');
      $stmt->execute();
      $mentees = $stmt->fetchAll();
      foreach ($mentees as $key => $m)
      {
        $stmt = $this->db->prepare('SELECT mm_mentor_id FROM mentee_mentor WHERE mm_mentee_id = :id AND mm_stop IS NULL;');
	$stmt->execute(array(':id' => $m['mentee_id']));
	if ($stmt->rowCount() == 1)
	{
	  $i = $stmt->fetch();
	  $mentees[$key]['mentor_id'] = $i['mm_mentor_id'];
	}
	else
	{
	  $stmt = $this->db->prepare('SELECT mm_mentor_id FROM mentee_mentor WHERE mm_mentee_id = :id ORDER BY mm_start DESC;');
	  $stmt->execute(array(':id' => $m['mentee_id']));
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
      $stmt = $this->db->prepare('SELECT mentee_id, mentee_user_name, mentee_user_id, mentee_in, mm_mentor_id, mentor_user_name FROM mentee JOIN (mentee_mentor, mentor) ON (mm_mentee_id = mentee_id AND mentor_id = mm_mentor_id) WHERE mentee_out IS NULL AND mm_stop IS NULL ORDER BY mentee_in;');
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
   */
  public function getMentors($offset, $count)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT * FROM mentor ORDER BY mentor_user_name LIMIT :count OFFSET :offset");
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
      $stmt = $this->db->prepare("SELECT * FROM mentor WHERE mentor_id = :id LIMIT 1");
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
      $stmt = $this->db->prepare("SELECT * FROM mentee WHERE mentee_id = :id LIMIT 1");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetch();
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
      return $stmt->fetch();
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
      $sql = 'SELECT * FROM mentee WHERE mentee_user_name REGEXP :nameregexp';
      if ($actives && !$inactives)
      {
        $sql .= ' AND mentee_out IS NULL';
      }
      elseif (!$actives && $inactives)
      {
        $sql .= ' AND mentee_out IS NOT NULL';
      }
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
      $sql = "UPDATE mentee SET mentee_out = NOW() WHERE mentee_id = :id";
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
      $stmt = $this->db->prepare('SELECT mentor_id, mentor_user_name FROM mentee_mentor INNER JOIN mentor ON mm_mentor_id = mentor_id WHERE mm_mentee_id = :id ORDER BY mentor_user_name');
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
      $stmt = $this->db->prepare("SELECT mentee_id, mentee_user_id, mentee_user_name, mentee_in, mentee_out, mm_start, mm_stop FROM mentee_mentor INNER JOIN mentee ON mm_mentee_id=mentee_id WHERE mm_mentor_id = :id ORDER BY mentee_user_name");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }

  /**
   * Returns the count of mentees a mentor ever took care of.
   * @param $id the mentor’s id
   * @returns the mentee count
   */
  public function getMenteeCountByMentor($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT COUNT(*) AS mentee_mentor_count FROM mentee_mentor WHERE mm_mentor_id = :id");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetch();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
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
      $stmt = $this->db->prepare("SELECT * FROM comentors INNER JOIN mentor ON co_comentor_id = mentor_id WHERE co_mentor_id = :id ORDER BY mentor_user_name");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Checks whether there is a comentor dataset for two certain mentors.
   * @param $mid the mentor’s id
   * @param $cmid the comentor’s id
   * @returns true if there is a dataset for these mentors.
   */
   public function exists_comentor_connection($mid, $cmid)
   {
     try
     {
       $stmt = $this->db->prepare("SELECT * FROM comentors WHERE co_mentor_id = :mid AND co_comentor_id = :cmid");
       $stmt->execute(array(":mid" => $mid, ":cmid" => $cmid));
       return ($stmt->rowCount() > 0);
     }
     catch (PDOException $ex)
     {
       $this->handleError($ex->getMessage());
     }
   }
   
   /**
    * Delete all matching comentor datasets.
    * @param $mid the mentor’s id
    * @param $cmid the comentor’s id
    */
   public function delete_comentor($mid, $cmid)
   {
     try
     {
       $stmt = $this->db->prepare("DELETE FROM comentors WHERE co_mentor_id = :mid AND co_comentor_id = :cmid");
       $stmt->execute(array(":mid" => $mid, ":cmid" => $cmid));
     }
     catch (PDOException $ex)
     {
       $this->handleError($ex->getMessage());
     }
   }
   
   /**
    * Add a comentor dataset.
    * @param $mid the mentor’s id
    * @param $cmid the comentor’s id
    */
   public function add_comentor($mid, $cmid)
   {
     try
     {
       $stmt = $this->db->prepare("INSERT INTO comentors (co_mentor_id, co_comentor_id) VALUES (:mid, :cmid)");
       $stmt->execute(array(":mid" => $mid, ":cmid" => $cmid));
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
   * @param $active new activity state
   * @param $barnstar new barnstar state
   * @param $award new award state
   * @param $remark new remark
   */
  public function updateMentor($id, $user_name, $in, $out, $active,
                               $barnstar, $award, $remark)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentor SET ' .
                                 'mentor_user_name = :user_name, ' .
                                 'mentor_in = :in, ' .
                                 'mentor_out = :out, ' .
                                 'mentor_is_active = :active, ' .
                                 'mentor_has_barnstar = :barnstar, ' .
                                 'mentor_award_level = :award, ' .
                                 'mentor_remark = :remark ' .
                                 'WHERE mentor_id = :id');
      $stmt->execute(array(':id' => $id,
                           ':user_name' => $user_name,
                           ':in' => $in,
                           ':out' => $out,
                           ':active' => (int) $active,
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
   * @param string $in        the updated in date
   * @param string $out       the updated out date
   * @param string $remark    the updated remark
   */
  public function updateMentee($id, $user_name, $in, $out, $remark)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentee SET ' .
                                 'mentee_user_name = :user_name, ' .
                                 'mentee_in = :in, ' .
                                 'mentee_out = :out, ' .
                                 'mentee_remark = :remark ' .
                                 'WHERE mentee_id = :id');
      $stmt->execute(array(':id' => $id,
                           ':user_name' => $user_name,
                           ':in' => $in,
                           ':out' => $out,
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
      $q = $this->db->query("SELECT COUNT(*) as newbie_count_db FROM mentee WHERE mentee_out IS NULL");
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
   * Get the login password hash for a certain mentor.
   * @param string $user the mentor’s user name
   * @returns the mentor’s password hash or -1 if the mentor doesn’t exist.
   */
  public function get_hash_for_user($user)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mentor_login_password FROM mentor WHERE mentor_user_name = :user");
      $stmt->execute(array(":user" => $user));
      $result = $stmt->fetch();
      if (isset($result['mentor_login_password']))
      {
        return $result['mentor_login_password'];
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
   * @param sha1   $hash the new password hash 
   */
  public function set_hash_for_user($user, $hash)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentor SET mentor_login_password = :np WHERE mentor_user_name = :user');
      $stmt->execute(array(':np' => $hash, ':user' => $user));
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
   * @param string $start     the updated start
   * @param string $stop      the updated stop
   */
  public function update_mm_item($mentor_id, $mentee_id, $ostart, $ostop, $start, $stop)
  {
    try
    {
      $args = array(':mentor_id' => $mentor_id,
                    ':mentee_id' => $mentee_id,
                    ':ostart'    => $ostart,
                    ':start'     => $start,);
      $sql = "UPDATE mentee_mentor SET mm_start = :start, mm_stop = ";
      if ($stop === '')
        $sql .= "NULL";
      else
      {
        $sql .= ":stop";
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
  public function add_mm_item($mentor_id, $mentee_id)
  {
    try
    {
      $sql = "INSERT INTO mentee_mentor (mm_mentor_id, mm_mentee_id, mm_start, mm_stop) VALUES (:mentorid, :menteeid, NOW(), NULL)";
      $stmt = $this->db->prepare($sql);
      $stmt->execute(array(':mentorid' => $mentor_id, ':menteeid' => $mentee_id));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
  }
  
  /**
   * Get the count of mentees and mentors currently active. The functionen uses
   * the categories ‘Benutzer ist Mentor’ and ‘Wird im Mentorenprogramm 
   * betreut’.
   * @return mentee/mentor count
   */
  public function getCountsWP()
  {
    try
    {
      $rv = array();
      $q = $this->db->query("SELECT COUNT(*) as mentor_count_wp FROM dewiki_p.categorylinks WHERE cl_to = 'Benutzer_ist_Mentor'");
      $rv = array_merge($rv, $q->fetch());
      $q = $this->db->query("SELECT COUNT(*) as newbie_count_wp FROM dewiki_p.categorylinks WHERE cl_to = 'Wird_im_Mentorenprogramm_betreut'");
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
   * Get the edit count of a Wikipedia user.
   * @param $id the user’s MediaWiki id
   * @returns the edit count
   */
  public function get_user_edit_count($user_id)
  {
    try
    {
      $stmt = $this->db->prepare('SELECT COUNT(*) AS edit_count FROM dewiki_p.revision WHERE rev_user = :id');
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
   * Check if a user is active.
   * @param $id the user’s MediaWiki id
   * @returns boolean value
   */
  public function is_user_active($user_id, $delay = '-1 month')
  {
    try
    {
      $stmt = $this->db->prepare('SELECT COUNT(1) AS active FROM (' . 
          'SELECT rev_id FROM dewiki_p.revision WHERE rev_user = :id AND rev_timestamp between :start and :end LIMIT 1' .
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
      $stmt = $this->db->prepare('select page_title from dewiki_p.page where page_id = :id');
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
   * Checks if a user did edit.
   */
  public function has_recent_edit($user_id, $delay = '-60 days')
  {
    try
    {
      $now   = time();
      $start = date(self::timestamp_format, strtotime($delay, $now));
      $end   = date(self::timestamp_format, strtotime('1 second', $now));
      $sql   = 'SELECT COUNT(1) AS has_edit FROM (SELECT rev_id FROM dewiki_p.revision WHERE rev_user = :user AND rev_timestamp BETWEEN :start AND :end LIMIT 1) i;';
      $stmt  = $this->db->prepare($sql);
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
      $stmt = $this->db->prepare($sql);
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
      $sql = "SELECT mentor_user_id, mentor_id, mentor_user_name, user_name FROM mentor JOIN dewiki_p.user ON mentor_user_id = user_id WHERE mentor_user_name != user_name";
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
   * Renames a mentor.
   */
  public function rename_mentor($mentor_id, $new_name)
  {
    try
    {
      $sql = 'UPDATE mentor SET mentor_user_name = :name WHERE mentor_id = :id';
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
    try
    {
      $sql = 'SELECT mentor_user_name, mentor_id FROM mentor WHERE mentor_out IS NULL AND NOT EXISTS (SELECT cl_from FROM dewiki_p.categorylinks JOIN dewiki_p.page ON page_id = cl_from WHERE page_title = REPLACE(mentor_user_name, \' \', \'_\') AND page_namespace = 2 AND cl_to = :cat);';
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
   */
  public function archive_mentor($mentor_id)
  {
    try
    {
      $sql = 'UPDATE mentor SET mentor_out = CURRENT_DATE() WHERE mentor_id = :id';
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
     try
     {
       $sql = 'SELECT REPLACE(page_title, \'_\', \' \') AS mentor_name, user_id FROM dewiki_p.categorylinks JOIN (dewiki_p.page, dewiki_p.user) ON (page_id = cl_from AND REPLACE(user_name, \' \', \'_\') = page_title) WHERE cl_to = :cat AND page_namespace = 2 AND NOT EXISTS (SELECT mentor_id FROM mentor WHERE mentor_user_id = user_id AND mentor_out IS NULL);';
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
      $this->handleError($e);
    }
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
