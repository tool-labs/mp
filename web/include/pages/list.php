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

class ListPage implements Page
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

    $num = $this->db->getMentorCount();

    $all = false;
    if (isset($_GET['all']) && $_GET['all'])
    {
      $offset = 0;
      $count  = $num;
      $all    = true;
    }

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
    $rv['title']   = "Mentorenliste";
    $rv['heading'] = 'Liste der Mentoren';
    $rv['page']    = "list";
    $rv['data']    = array();
    $rv['data']['count']       = $count;
    $rv['data']['mentors']     = $this->db->getMentors($offset, $count);
    $rv['data']['prev_offset'] = $prev_offset;
    $rv['data']['next_offset'] = $next_offset;
    $rv['data']['offset']      = $offset;
    $rv['data']['all']         = $all;

    return $rv;
  }
}
