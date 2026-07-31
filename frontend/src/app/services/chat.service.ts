import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatRequest } from '../model/chat-request.model';
import { ChatHistoryItem, ChatResponse, ChatSessionItem, CurrentUser } from '../model/chat-response.model';

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  askQuestion(request: ChatRequest): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.apiUrl}/chat`, request);
  }

  getHistory(params: { tableName?: string; sessionId?: number }): Observable<{ history: ChatHistoryItem[] }> {
    const query = new URLSearchParams();
    if (params.tableName) {
      query.set('table_name', params.tableName);
    }
    if (params.sessionId !== undefined) {
      query.set('session_id', String(params.sessionId));
    }
    return this.http.get<{ history: ChatHistoryItem[] }>(`${this.apiUrl}/history?${query.toString()}`);
  }

  getCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${this.apiUrl}/me`);
  }

  getSessions(tableName?: string, userId?: number): Observable<{ sessions: ChatSessionItem[]; count: number }> {
    const query = new URLSearchParams();
    if (tableName) {
      query.set('table_name', tableName);
    }
    if (userId !== undefined) {
      query.set('user_id', String(userId));
    }
    return this.http.get<{ sessions: ChatSessionItem[]; count: number }>(`${this.apiUrl}/sessions?${query.toString()}`);
  }

  createSession(payload: { table_name: string; user_id?: number; title?: string }): Observable<ChatSessionItem> {
    return this.http.post<ChatSessionItem>(`${this.apiUrl}/sessions`, payload);
  }

  selectSession(sessionId: number): Observable<{
    session: ChatSessionItem;
    table: { table_name: string; columns: string[]; row_count: number; prompt: string | null };
  }> {
    return this.http.post<{
      session: ChatSessionItem;
      table: { table_name: string; columns: string[]; row_count: number; prompt: string | null };
    }>(`${this.apiUrl}/sessions/select`, { session_id: sessionId });
  }
}