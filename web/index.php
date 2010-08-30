<?php
/*
 * main.php
 */

# Fehler werden nicht verheimlicht
error_reporting(E_ALL);
ini_set("display_errors", "1");

# Einbinden aller Klasse
require_once("include/main.php");

$main = new Main();
$main->run();
?>
