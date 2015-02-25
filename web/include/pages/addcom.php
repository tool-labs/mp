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
 * This page can be used for adding a mentor/comentor relation.
 */
class AddComPage implements Page
{
  /**
   * An instance of the Wikipedia database object.
   */
  private $db;
  /**
   * An instance of the access class to determine whether
   * the current user is logged in.
   */
  private $access;

  /**
   * Constructs a new instance of this class.
   * @param Database db 
   *        Wikipedia database access
   * @param Access access
   *        login information
   */
  public function __construct($db, $access)
  {
    $this->db = $db;
    $this->access = $access;
  }
  
  /**
   * Aggregates data for displaying this page.
   * @returns array data about the page to display
   */
  public function display()
  {
    $rv = array();
    $rv['data']    = array();
    $rv['data']['comentoren'] = $this->db->get_all_comentors();
    $rv['title']   = "Co-Mentor hinzufügen";
    $rv['heading'] = "Co-Mentor hinzufügen";
  }
}
