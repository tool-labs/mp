<?php

class ChangePWPage implements Page
{
  private $db;
  private $access;

  public function __construct($db, $access)
  {
    $this->db     = $db;
    $this->access = $access;
  }

  public function display()
  {
    if (!$this->access->logged_in())
    {
      return 'Du musst angemeldet sein, um dein Passwort ändern zu können.';
    }

    $rv = array();
    $rv['page']    = 'changepw';
    $rv['data']    = array();
    $rv['data']['what']  = 'form';
    $rv['title']   = 'Passwort ändern';
    $rv['heading'] = 'Passwort ändern';
    if (isset($_POST['new_password']))
    {
      $rv['data']['what'] = 'success';
      $this->db->set_hash_for_user($this->access->user(), sha1($_POST['new_password']));
    }

    return $rv;
  }
}
?>