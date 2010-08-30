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
  public $header;

  function __construct(&$access)
  {
    $this->access = $access;

    $this->title = "Mentorenprogramm auf dem Wikimedia-Toolserver";
    $this->data  = array();
    $this->page  = "";
    $this->header = "";
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
    if(file_exists(__DIR__ . "/../templates/" . $this->page . ".header")){
    	$this->header = file_get_contents(__DIR__ . "/../templates/" . $this->page . ".header");
    }
    ob_start();
    include(__DIR__ . "/../templates/header.html");
    include(__DIR__ . "/../templates/" . $this->page . ".html");
    include(__DIR__ . "/../templates/footer.html");
    $out = ob_get_clean();
    if (isset($_GET['useskin']))
    {
    	$pattern = array();
    	$replacement = array();
    	$pattern[0] = "/(<a\s[^>]*href=\"[^\"]*)index\.php(\"[^>]*)>/siU";
    	$replacement[0] = '${1}index.php?useskin='.$_GET['useskin'];
    	$pattern[1] = "/(<a\s[^>]*href=\"[^\"]*)index\.php\?([^\"]*\"[^>]*>)/siU";
    	$replacement[1] = $replacement[0].'&${2}';
    	$pattern[2] = "/(<form\s[^>]*action=\")index\.php(\"[^>]*>)/siU";
    	$replacement[2] = $replacement[0].'${2}';
    	$out = preg_replace($pattern, $replacement, $out);
	}
    ob_start("ob_gzhandler");
    echo $out;
    ob_end_flush();
    exit;
  }
}
