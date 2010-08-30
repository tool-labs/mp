<?php
/*
 * errorpage.php
 *
 * Klasse ErrorPage
 * Gibt eine Fehlermeldung aus: Die Seite existiert nicht.
 */

class ErrorPage implements Page
{
  # display()
  public function display()
  {
    return "Die Seite <tt>" . trim($_GET["action"]) . "</tt> existiert nicht.";
  }
}
