<?php
  /*
   * viewmpage.php
   * viewmentee page
   * information about a single mentee
   */

class ViewMPage implements Page
{
  private $db;

  public function __construct($db)
  {
    $this->db = $db;
  }

  public function display()
  {
    if (!isset($_GET['id']) || empty($_GET['id']))
    {
      return "Keine ID angegeben.";
    }
    $id = $_GET['id'];
    $mentee = $this->db->getMenteeById($id);
    if (empty($mentee))
      return "Es existiert kein Mentee mit der ID <tt>$id</tt>.";

    $rv = array();
    $rv['page'] = 'viewmentee';
    $rv['data'] = array();
    $rv['data']['mentee'] = $mentee;
    $rv['data']['articles']      = $this->db->getArticlesByMenteeId($id);
    $rv['data']['article_count'] = count($rv['data']['articles']);
    $rv['data']['mentors'] = $this->db->getMentorsByMentee($id);
    $rv['title'] = "Neuling {$rv['data']['mentee']['mentee_user_name']}";

    return $rv;
  }
}
