<?php
/*
 * output.php
 */

class Output
{
  private $access;
  public $title;
  public $data;
  public $page;

  function __construct(&$access)
  {
    $this->access = $access;

    $this->title = "Mentorenprogramm auf dem Wikimedia-Toolserver";
    $this->data  = array();
    $this->page  = "";
  }

  public function critical($msg, $data)
  {
    $this->title = "Fehler";
    $this->data  = $data;
    $this->data['error'] = $msg;
    $this->page  = "error";
    $this->printOutput();
  }

  public function printOutput()
  {
    ob_start();
    require_once(__DIR__ . "/../templates/header.html");
    require_once(__DIR__ . "/../templates/" . $this->page . ".html");
    require_once(__DIR__ . "/../templates/footer.html");
    ob_end_flush();
    exit;
  }
}
