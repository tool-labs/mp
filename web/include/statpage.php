<?php
/*
 * statpage.php
 */

class StatPage implements Page
{
  private $db;

  function __construct($db)
  {
    $this->db = $db;
  }

  public function display()
  {
    $rv = array();
    $rv['title'] = "Statistik";
    $rv['page']  = "stat";
    $rv['data']  = array();
    $rv['data']  = array_merge($this->db->getCountsDB(), $this->db->getCountsWP(),
      $this->db->getCountsAllDB());
    return $rv;
  }
}
