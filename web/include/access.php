<?php
/*
 * access.php
 */

class Access
{
  private $logged_in;
  private $user;
  private $db;

  function __construct($db)
  {
    $this->db        = $db;
    $this->logged_in = false;
    $this->user      = "";

    session_start();
    if (isset($_SESSION['logged_in']) && $_SESSION['logged_in'] && isset($_SESSION['user']))
    {
      $this->logged_in = true;
      $this->user      = trim($_SESSION['user']);
    }
  }

  public function logged_in()
  {
    return $this->logged_in;
  }

  public function user()
  {
    return $this->user;
  }

  public function login($user, $password)
  {
    $pw_hash = sha1($password);
    $db_hash = $this->db->get_hash_for_user($user);
    if ($db_hash == -1 || $pw_hash != $db_hash)
    {
      return false;
    }
    $_SESSION['logged_in'] = true;
    $_SESSION['user']      = $user;
    $this->logged_in       = true;
    $this->user            = $user;

    return true;
  }

  public function logout()
  {
    session_destroy();
  }
}
?>