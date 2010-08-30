<?php
/*
 * lmpage.php
 * 
 * Klasse LMPage
 * List-Mentore-Page
 */

class LMPage implements Page
{
  # Datenbank-Handle
  private $db;

  # __construct(Database)
  # Konstruktor
  function __construct($db)
  {
    $this->db = $db;
  }

  # display()
  public function display()
  {
    $offset = 0;
    if (isset($_GET["offset"]) && !empty($_GET["offset"]))
    {
      $offset = (int) $_GET["offset"];
    }
    $count = 10;
    if (isset($_GET["count"]) && !empty($_GET["count"]))
    {
      $count = (int) $_GET["count"];
    }

    $num  = $this->db->getMentorCount();

    # überprüfe gegebene Parameter
    if ($offset < 0 || ($offset >= $num && $offset != 0))
    {
      return "Invalid offset.";
    }
    if ($count <= 0)
    {
      return "Invalid count.";
    }

    # vor- / zurück-Daten
    $prev_offset = -1;
    $next_offset = -1;

    if ($offset > 0)
    {
      $prev_offset = $offset - $count;
      if ($prev_offset < 0)
      {
        $prev_offset = 0;
      }
    }

    if ($offset + $count < $num)
    {
      $next_offset = $offset + $count;
    }

    $rv = array();
    $rv['title'] = "Mentorenliste";
    $rv['page']  = "list";
    $rv['data']  = array();
    $rv['data']['count']       = $count;
    $rv['data']['mentors']     = $this->db->getMentors($offset, $count);
    $rv['data']['prev_offset'] = $prev_offset;
    $rv['data']['next_offset'] = $next_offset;
    $rv['data']['offset']      = $offset;

    return $rv;
  }
}
