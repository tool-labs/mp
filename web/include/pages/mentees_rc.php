<?php
/*
 * Copyright (C) 2020 by Euku
 *
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see https://mp.toolforge.org
 */

class MenteesRcPage implements Page
{
  private $db;

  public function __construct($db)
  {
    $this->db = $db;
  }

  public function display()
  {
    $start_time = '';
    if (isset($_GET["start_time"])) {
        $start_time = $_GET["start_time"];
        if (!validate_timestamp_with_seconds($start_time)) {
            return "Ungültiger Zeitstempel in start_time";
        }
    }
    
    $end_time = '';
    if (isset($_GET["end_time"])) {
        $end_time = $_GET["end_time"];
        if (!validate_timestamp_with_seconds($end_time)) {
            return "Ungültiger Zeitstempel in end_time";
        }
    }
    
    $limit = 100;
    if (isset($_GET["limit"])) {
      $limit = (int) $_GET["limit"];
      if ($limit > 500) {
          $limit = 500;
      }
    }
    
    $sort_by = 'start';
    $rv = array();
    $rv['title']   = 'Letzte Änderungen von Mentees';
    $rv['heading'] = $rv['title'];
    $rv['page']    = 'mentees_rc';
    $rv['data'] = array();
    $rv['data']['start_time'] = $start_time;
    $rv['data']['end_time'] = $end_time;
    $rv['data']['limit']    = $limit;
    // db query
    $start_time = microtime(true);
    $mentees_rc = $this->db->get_recent_mentee_edits($start_time, $end_time, $limit +1);
    $rv['data']['execution_time'] = microtime(true) - $start_time;
    $rv['data']['rc'] = $mentees_rc;
    // get the next_timestamp
    $last_timestamp = '';
    if (sizeof($mentees_rc) != 0) {
       $last_timestamp = $mentees_rc[ sizeof($mentees_rc)-1 ]['rc_timestamp'];
    }
    $rv['data']['next_end_time'] = $last_timestamp;
    // remove the last element, we didn't asked for
    array_pop($rv['data']['rc']);
    return $rv;
  }
}
