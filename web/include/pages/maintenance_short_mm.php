<?php
/*
 * Copyright (C) 2017 by Euku
 *
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see http://toolserver.org/~dewpmp.
 */

class MaintenanceShortMmPage implements Page
{
  private $db;

  public function __construct($db)
  {
    $this->db = $db;
  }

  public function display()
  {
    $rv = array();
    $rv['title']   = 'Wartungsseite: Sehr kurze Betreuungen';
    $rv['heading'] = $rv['title'];
    $rv['page']    = 'maintenance_short_mm';
    $rv['data'] = array();
    $rv['data']['mentee_mentor'] = $this->db->get_all_mentor_mentees_with_short_mentoring();
    return $rv;
  }
}
