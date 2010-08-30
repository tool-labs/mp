<?php
/*
 * infopage.php
 *
 * Klasse InfoPage
 * Die Startseite, vgl. page.php
 */

class InfoPage implements Page
{
  # __construct
  # Konstruktor
  function __construct($db)
  {

  }

  # display()
  public function display()
  {
    $rv = array();
    $rv['page']  = "info";
    $rv['data']  = array();
    $rv['title'] = "Mentorenprogramm auf dem Wikimedia-Toolserver";
    return $rv;
  }
}
