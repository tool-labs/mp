<?php
/*
 * aboutpage.php
 *
 * Klasse AboutPage
 * Die Seite mit Informationen zu Implementierung, Lizenz, etc., vgl. page.php
 */

class AboutPage implements Page
{
  # __construct
  # Konstruktor
  function __construct()
  {

  }

  # display()
  public function display()
  {
    $rv = array();
    $rv['page']  = "about";
    $rv['data']  = array();
    $rv['title'] = "Über das Mentorenprogramm auf dem Wikimedia-Toolserver";
    return $rv;
  }
}
