<?php
/*
 * main.php
 *
 * Klasse Main
 * Die Main-Klasse ist sozusagen die Oberklasse, die den Rest einleitet.
 */

# notwendige Einbindungen
require_once('database.php');
require_once('output.php');
require_once('access.php');
require_once('validator.php');
require_once('page.php');
require_once('aboutpage.php');
require_once('changepwpage.php');
require_once('editpage.php');
require_once('errorpage.php');
require_once('infopage.php');
require_once('lmpage.php');
require_once('loginpage.php');
require_once('logoutpage.php');
require_once('searchpage.php');
require_once('statpage.php');
require_once('viewpage.php');
require_once('viewmpage.php');

# format date
function fd($d, $def = '-')
{
  if ($d == 0)
  {
    return $def;
  }
  $date = new DateTime($d);
  return $date->format('j.n.Y');
}
# format date and time
function fdt($dt, $def = '-')
{
  if ($dt == 0)
  {
    return $def;
  }
  $date = new DateTime($dt);
  return $date->format('j.n.Y, G:s');
}

class Main
{
  # Datenbank-Interface (database.php)
  private $db_wp;
  private $db_mp;
  # anzeigbare Seiten (page.php)
  private $pages = array();
  # Ausgabe
  private $output;
  # Loginmodul
  private $access;

  # void __construct()
  # Konstruktor
  public function __construct()
  {
    # initialisiere Datenbank
    $this->db_mp = new Database();
    $this->db_wp = new Database('dewiki_p');

    $this->access = new Access($this->db_mp);
    $this->output = new Output($this->access);

    # lade Seiten
    $this->pages['']            = new InfoPage    ($this->db_mp);
    $this->pages['about']       = new AboutPage   ();
    $this->pages['changepw']    = new ChangePWPage($this->db_mp, $this->access);
    $this->pages['edit']        = new EditPage    ($this->db_mp, $this->access);
    $this->pages['error']       = new ErrorPage   ($this->db_mp);
    $this->pages['list']        = new LMPage      ($this->db_mp);
    $this->pages['view']        = new ViewPage    ($this->db_mp);
    $this->pages['viewmentee']  = new ViewMPage   ($this->db_mp);
    $this->pages['search']      = new SearchPage  ($this->db_mp);
    $this->pages['stat']        = new StatPage    ($this->db_mp);
    $this->pages['login']       = new LoginPage   ($this->db_mp, $this->access);
    $this->pages['logout']      = new LogoutPage  ($this->access);
  }

  # void run()
  # Gibt die gewählte Seite aus.
  public function run()
  {
    $pagename = '';
    if (isset($_GET['action']))
      $pagename = trim($_GET['action']);

    if (!isset($this->pages[$pagename]))
      $pagename = 'error';

    $page = $this->pages[$pagename];
    $tmp  = $page->display();
    $cd   = array_merge($this->db_mp->getCountsDB(), $this->db_wp->getCountsWP());

    if (gettype($tmp) == 'string')
    {
      $this->output->critical($tmp, $cd);
    }

    $this->output->title = $tmp['title'];
    $this->output->page  = $tmp['page'];
    $this->output->data  = array_merge($this->output->data, $tmp['data'], $cd);
    $this->output->printOutput();
  }
}
