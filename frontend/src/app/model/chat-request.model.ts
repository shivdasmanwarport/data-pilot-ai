export interface ChatRequest {
  question: string;
  table_name?: string;
  session_id?: number;
  user_id?: number;
}