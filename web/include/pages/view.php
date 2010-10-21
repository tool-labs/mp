<?php

class ViewPage implements Page
{
  private $db;

  function __construct($db)
  {
    $this->db = $db; 
  }

  public function display()
  {
    if (!isset($_GET["id"]) || empty($_GET["id"]))
    {
      return "No id.";
    }
    $id = $_GET['id'];
    $mentor = $this->db->getMentorById($id);
    if (empty($mentor))
      return "Es existiert kein Mentor mit der ID <tt>$id</tt>.";

    $rv = array();
    $rv['page'] = "view";
    # note: getMenteeCountByMentor returns an array → everything’s fine
    #       though it looks strange ;)
    $rv['data'] = $this->db->getMenteeCountByMentor($id);
    $rv['data']['mentor']    = $mentor;
    $rv['data']['mentees']   = $this->db->getMenteesByMentor($id);
    foreach ($rv['data']['mentees'] as &$m)
    {
      $m['mentee_active'] = $this->db->is_user_active($m['mentee_user_id']);
    }
    $rv['data']['comentors'] = $this->db->get_comentors_by_mentor_id($id);
    $rv['title']   = "Mentor {$rv['data']['mentor']['mentor_user_name']}";
    $rv['heading'] = "Mentor <em>{$rv['data']['mentor']['mentor_user_name']}</em>";
    return $rv;
  }
}

?>
