<?php

class ViewMentorPage implements Page
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
    {
      $id = htmlspecialchars($id);
      return "Es existiert kein Mentor mit der ID <tt>$id</tt>.";
    }

    $rv = array();
    $rv['page'] = "viewmentor";
    # note: getMenteeCountByMentor returns an array → everything’s fine
    #       though it looks strange ;)
    $rv['data'] = $this->db->getMenteeCountByMentor($id);
    $rv['data']['mentor']    = $mentor;
    $rv['data']['mentees']   = $this->db->getMenteesByMentor($id);
    foreach ($rv['data']['mentees'] as &$m)
    {
      $m['mentee_active'] = $this->db->is_user_active($m['mentee_user_id']);
      $m['mentee_entrance'] = 0;
      foreach ($rv['data']['mentees'] as &$mm)
      {
         if ($m['mentee_user_id'] == $mm['mentee_user_id']) {
            $m['mentee_entrance'] += 1;
         }
      }
    }
    $rv['data']['metadata'] = $this->db->get_meta_data_by_mentor_name($mentor['mentor_user_name']);
    $rv['title']   = "Mentor {$rv['data']['mentor']['mentor_user_name']}";
    $rv['heading'] = "Mentor <em>{$rv['data']['mentor']['mentor_user_name']}</em>";
#print_r($rv);
#die();
    return $rv;
  }
}

?>
