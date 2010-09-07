<?php
/*
 * database.php
 *
 * Klasse Database
 * Die Database-Klasse stellt die Verbindung zur Datenbank her und kümmert sich
 * die Abfrage der notwendigen Daten. Zur Kommunikation mit der MySQL-Datenbank
 * verwendet sie eine persistente PDO-Verbindung.
 */

# Datenbank-Einstellungen
# __DIR__ . "/../../db_settings.ini"

class Database
{
  # Datenbank-Handle
  private $db;

  # void __construct()
  # Konstruktor
  function __construct($db=null)
  {
    $ts_pw = posix_getpwuid(posix_getuid());
    $ts_mycnf = array();
    if(file_exists($ts_pw['dir'] . "/.my.cnf"))
    {
      $ts_mycnf = parse_ini_file($ts_pw['dir'] . "/.my.cnf");
    }
    if(file_exists(__DIR__ . "/../../db_settings.ini"))
    {
      $ts_mycnf = array_merge($ts_mycnf, parse_ini_file(__DIR__ . "/../../db_settings.ini"));
    }
    if(isset($db)) $ts_mycnf['dbname'] = $db;
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

  # int getMentorCount()
  # gibt die Anzahl Mentoren zurück
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
    return 0;
  }

  # array getMentors(offset, count)
  # gibt die ersten <count> Mentoren ab <offset> zurück
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
    return array();
  }

  # array getMentorNames()
  # gibt die Namen aller Mentoren zurück.
  # *Achtung* Rückgabe als array(array('mentor_user_name' => $user_name))
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
      $this->handleError($ex);
    }
    return '';
  }

  # array getMenteeNames()
  # gibt die Namen aller Neulinge zurück
  # *Achtung* Rückgabe als array(array('mentee_user_name' => $user_name))
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
      $this->handleError($ex);
    }
    return '';
  }

  # array getMentorById(id)
  # gibt den Mentor mit der Mentorenid <id> in Arrayform zurück
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
    return array();
  }

  # array getMentorByName(name)
  # gibt den Mentor mit den Benutzernamen <name> in Arrayform zurück
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
    return array();
  }

  # array getMentorByNameAndActivity(string name, bool actives, bool inactives)
  # gibt den Mentor mit den Benutzernamen <name> in Arrayform zurück.
  # Hierbei geben <actives> und <inactives> an, ob in den aktiven und/oder den
  # inaktiven Mentoren gesucht wird.
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
    return array();
  }

  # array getMentorsByNameRegExp(name_regexp)
  # Gibt einen Array mit allen Mentoren, deren Name auf den
  # regulären Ausdruck <name_regexp> passt, zurück.
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
    return array();
  }

  # array getMentorsByNameRegExpAA(regexp name_regexp, bool actives, bool inactives)
  # Gibt einen Array mit allen Mentoren, deren Name auf den
  # regulären Ausdruck <name_regexp> passt, zurück. Hierbei geben
  # <actives> und <inactives> an, ob dabei die aktiven und/oder
  # die inaktiven Mentoren durchsucht werden.
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
    return array();
  }

  # array getMenteeById(int id)
  # Gibt den Neuling mit der Menteeid <id> in Arraydarstellung
  # zurück.
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
    return array();
  }

  # array getMenteeByName(string name)
  # Gibt den Neuling mit Benutzername <name> in Arraydarstellung
  # zurück.
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
    return array();
  }

  # array getMenteeByNameAndActivity(string name, bool actives, bool inactives)
  # gibt den Neuling mit den Benutzernamen <name> in Arrayform zurück.
  # Hierbei geben <actives> und <inactives> an, ob in den aktiven und/oder den
  # inaktiven Neulingen gesucht wird.
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
    return array();
  }

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
    return array();
  }

  # array getMenteesByNameRegExpAA(regexp name_regexp, bool actives, bool inactives)
  # Gibt einen Array mit allen Neulingen, deren Name auf den
  # regulären Ausdruck <name_regexp> passt, zurück. Hierbei geben
  # <actives> und <inactives> an, ob dabei die aktiven und/oder
  # die inaktiven Neulinge durchsucht werden.
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
    return array();
  }


  # array getMentorsByMentee(id)
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
    return array();
  }

  # array getMenteesByMentor(id)
  public function getMenteesByMentor($id)
  {
    try
    {
      $stmt = $this->db->prepare("SELECT mentee_id, mentee_user_name, mentee_in, mentee_out, mm_start, mm_stop FROM mentee_mentor INNER JOIN mentee ON mm_mentee_id=mentee_id WHERE mm_mentor_id = :id ORDER BY mentee_user_name");
      $stmt->execute(array(":id" => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
    return array();
  }

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
    return array();
  }

  public function getArticlesByMenteeId($id)
  {
    try
    {
      $stmt = $this->db->prepare('SELECT * FROM mentee_articles WHERE ma_mentee_id = :id');
      $stmt->execute(array(':id' => $id));
      return $stmt->fetchAll();
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex->getMessage());
    }
    return array();
  }

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
      $this->handleError($ex);
    }
  }

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
    return array();
  }

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
    return array();
  }

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
      $this->handleError($ex);
    }
    return -1;
  }

  public function set_hash_for_user($user, $hash)
  {
    try
    {
      $stmt = $this->db->prepare('UPDATE mentor SET mentor_login_password = :np WHERE mentor_user_name = :user');
      $stmt->execute(array(':np' => $hash, ':user' => $user));
    }
    catch (PDOException $ex)
    {
      $this->handleError($ex);
    }
  }

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
      $this->handleError($ex);
    }
  }

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
      $this->handleError($ex);
    }
  }

  # handleError(string)
  # gibt eine Fehlermeldung aus und terminiert
  protected function handleError($msg)
  {
    die("<p class='error'>Datenbank-Fehler: <pre>" . $msg . "</pre></p>");
  }

}

?>
