<?php
/*
 * editmmpage.php
 * Copyright (C) 2010 by Robin Krahl, Merlissimo and others
 *
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see http://toolserver.org/~dewpmp.
 */

/**
 * This page is used for editing the mentee-mentor relationship.
 */
class EditMMPage implements Page
{
  /**
   * handle of the MP database
   */
  private $db;
  /**
   * access object
   */
  private $access;

  
  /**
   * Constructor.
   * @param Database $db_mp handle of the MP database
   * @param Access $access Access object
   */
  public function __construct($db_mp, $access)
  {
    $this->db     = $db_mp;
    $this->access = $access;
  }

  /**
   * Returns information on what to display.
   * @return mixed if succesful: array:  information on what to display
   *               else:         string: error string
   */
  public function display()
  {
    if (!$this->access->is_editor())
    {
      return "Du musst angemeldet sein und die entsprechenden Rechte besitzen, um Einträge bearbeiten zu können.";
    }

    $rv = array();
    $rv['heading'] = "Mentee-Mentor-Beziehung bearbeiten";
    $rv['title']   = "Mentee-Mentor-Beziehung bearbeiten";
    $rv['page']    = "editmm";
    $rv['data']    = array();

    $mentor_id = '';
    if (isset($_GET['mentor_id']))
    {
      $mentor_id = $_GET['mentor_id'];
    }
    $mentee_id = '';
    if (isset($_GET['mentee_id']))
    {
      $mentee_id = $_GET['mentee_id'];
    }
    if ($mentee_id === '' && $mentor_id === '')
    {
      return "Du musst mindestens entweder die ID des Neulings oder die des Mentors angeben (<tt>mentee_id</tt> oder <tt>mentor_id</tt>).";
    }

    $start = '';
    if (isset($_GET['start']))
    {
      $start = $_GET['start'];
    }
    $end = '';
    if (isset($_GET['end']))
    {
      $end = $_GET['end'];
    }

    $pos = $this->db->get_mm_items($mentor_id, $mentee_id, $start, $end);

    if (count($pos) == 0)
    {
      return "Es existiert keine Mentee-Mentor-Beziehung mit diesen Eigenschaften.";
    }

    if (count($pos) == 1 && isset($_POST['start']))
    {
      if (!(isset($_POST['start']) && isset($_POST['end'])))
      {
        return "Du hast ein falsches Formular verwendet.";
      }

      if (!validate_timestamp($_POST['start']))
      {
        return "<tt>start</tt> ist kein gültiger Zeitstempel!";
      }
      if (!(validate_timestamp($_POST['end']) || $_POST['end'] === ''))
      {
        return "<tt>end</tt> ist kein gültiger Zeitstempel!";
      }

      $this->db->update_mm_item($mentor_id, $mentee_id, $start, $end, $_POST['start'], $_POST['end']);

      $rv['page'] = "editmm_result";
    }
    else
    {
      foreach ($pos as $key => $p)
      {
        $mentor = $this->db->getMentorById($p['mm_mentor_id']);
        $mentee = $this->db->getMenteeById($p['mm_mentee_id']);
        $p['mentor_user_name'] = $mentor['mentor_user_name'];
        $p['mentee_user_name'] = $mentee['mentee_user_name'];
        $pos[$key] = $p;
      }
    }

    $rv['data']['pos'] = $pos;
    
    return $rv;
  }
}