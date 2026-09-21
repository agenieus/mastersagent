export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface Memory {
  memory_id: string;
  fact_text: string;
  importance_weight: number;
  decay_score: number;
  retrieval_count: number;
  created_at: string;
  last_retrieved_at: string;
  validity_flag: boolean;
  superseded_by?: string;
}

export interface MemoryStats {
  active_count: number;
  archived_count: number;
  average_decay_score: number;
  average_importance: number;
  threshold: number;
}

export interface DecayReport {
  user_id: string;
  processed: number;
  archived: number;
  active: number;
  threshold: number;
}
