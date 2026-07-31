export interface ChatResultPayload {
    type: 'scalar' | 'table';
    columns: string[];
    rows: Record<string, string | number | boolean | null>[];
    row_count: number;
    truncated: boolean;
}

export interface ChatResponse {
    answer: string;
    sql_query: string | null;
    session_id: number | null;
    result_payload: ChatResultPayload | null;
}

export interface ChatHistoryItem {
    session_id: number | null;
    user_id: number | null;
    user_message: string;
    assistant_response: string | null;
    sql_query: string | null;
    result_payload: ChatResultPayload | null;
    timestamp: string;
}

export interface ChatSessionItem {
    id: number;
    user_id: number;
    table_name: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
    last_message_at: string | null;
}

export interface CurrentUser {
    id: number;
    display_name: string;
    email: string;
    avatar_initials: string;
}