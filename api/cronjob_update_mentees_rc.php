<?php
  /**
   * Run 
   */

error_reporting(E_ALL);
ini_set('display_errors', '1');

require('../web/include/database.php');
require('../web/include/validator.php');

$db = new Database();
$db->update_mentees_recentchanges();
//echo("Run completed")
?>
