export interface UserSessionItem {
  session_id: string;
  session_type: number;
  last_message: string;
  last_message_time: string;
  first_message: string;
  first_message_time: string;
  user_id: string;
  username: string;
  created_at: string;
  updated_at: string;
  unfinished_task_ids: string[];
}
