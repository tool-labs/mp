<?php
/*
 * main.php
 * Copyright (C) 2010 by Robin Krahl, Merlissimo and others
 *
 * This file is published under the terms of the MIT license
 * (http://www.opensource.org/licenses/mit-license.php) and the
 * LGPL (http://www.gnu.org/licenses/lgpl.html).
 *
 * For more information, see http://toolserver.org/~dewpmp.
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
require_once('editmmpage.php');
require_once('errorpage.php');
require_once('infopage.php');
require_once('lmpage.php');
require_once('loginpage.php');
require_once('logoutpage.php');
require_once('searchpage.php');
require_once('statpage.php');
require_once('viewpage.php');
require_once('viewmpage.php');

/**
 * Format a date stamp.
 * @param int $d the date to format
 * @param string $def the default value if $d = 0
 * @returns string the formatted date $d in ‘d.m.Y’ or $def if $d = 0
 */
function fd($d, $def = '-')
{
  if ($d == 0)
  {
    return $def;
  }
  $date = new DateTime($d);
  return $date->format('d.m.Y');
}

/**
 * Format a date-and-time stamp.
 * @param int $dt the date and time to format
 * @param string $def the default value if $dt = 0
 * @returns string the formatted date-time $dt in ‘d.m.Y, G:s’ form or $def if
 *                 $d = 0
 */
function fdt($dt, $def = '-')
{
  if ($dt == 0)
  {
    return $def;
  }
  $date = new DateTime($dt);
  return $date->format('d.m.Y, G:s');
}

/**
 * This class is – as the name states – the interface’s main class. It co-
 * ordinates the different sub-classes.
 */
class Main
{
  /**
   * The database object representing the Wikipedia database.
   */
  private $db_wp;
  /**
   * The database object representing the MP database.
   */
  private $db_mp;
  /**
   * The existing pages in form ‘access-name’ → ‘instance’. A page can be
   * called with ?action=access-name.
   */
  private $pages = array();
  /**
   * The object handling the output.
   */
  private $output;
  /**
   * The object providing login and acces group functionality.
   */
  private $access;

  /**
   * Constructor. Initialises the databases, other objects, loads the existing
   * pages.
   */
  public function __construct()
  {
    # initialise databases
    $this->db_mp = new Database();
    $this->db_wp = new Database('dewiki_p');

    $this->access = new Access($this->db_mp);
    $this->output = new Output($this->access);

    # load pages
    $this->pages['']            = new InfoPage    ();
    $this->pages['about']       = new AboutPage   ();
    $this->pages['changepw']    = new ChangePWPage($this->db_mp, $this->access);
    $this->pages['edit']        = new EditPage    ($this->db_mp, $this->access);
    $this->pages['editmm']      = new EditMMPage  ($this->db_mp, $this->access);
    $this->pages['error']       = new ErrorPage   ($this->db_mp);
    $this->pages['list']        = new LMPage      ($this->db_mp);
    $this->pages['view']        = new ViewPage    ($this->db_mp);
    $this->pages['viewmentee']  = new ViewMPage   ($this->db_mp);
    $this->pages['search']      = new SearchPage  ($this->db_mp);
    $this->pages['stat']        = new StatPage    ($this->db_mp);
    $this->pages['login']       = new LoginPage   ($this->db_mp, $this->access);
    $this->pages['logout']      = new LogoutPage  ($this->access);
  }

  /**
   * Does the main action: Figures out which page to load, tries to load it,
   * agregates data etc.
   */
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

    $this->output->heading = $tmp['heading'];
    $this->output->title   = $tmp['title'];
    $this->output->page    = $tmp['page'];
    $this->output->data    = array_merge($this->output->data, $tmp['data'], $cd);
    $this->output->printOutput();
  }
}
