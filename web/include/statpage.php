<?php
/*
 * statpage.php
 * Copyright (C) 2010 by Robin Krahl, Merlissimo and others
 *
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see http://toolserver.org/~dewpmp.
 */

/**
 * This page displays some kind of statistics. In the moment, most of these
 * statistics have still to be created yet.
 */
class StatPage implements Page
{
  /**
   * A MP database handle.
   */
  private $db;

  /**
   * Constructor. Initialises the variable.
   * @param Database $db a MP database handle
   */
  function __construct($db)
  {
    $this->db = $db;
  }

  /**
   * Aggregates data for displaying this page.
   * @returns array data about the page to display
   */
  public function display()
  {
    $rv = array();
    $rv['heading'] = 'Statistik';
    $rv['title']   = "Statistik";
    $rv['page']    = "stat";
    $rv['data']    = array();
    $rv['data']    = array_merge($this->db->getCountsDB(), $this->db->getCountsWP(),
      $this->db->getCountsAllDB());
    return $rv;
  }
}
