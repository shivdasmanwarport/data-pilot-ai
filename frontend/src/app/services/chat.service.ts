import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { ChatRequest } from "../model/chat-request.model";
import { ChatResponse } from "../model/chat-response.model";

@Injectable({
    providedIn:'root'
})
export class ChatService{
    private api_url = 'http://localhost:8000/chat';
    
    constructor(private http: HttpClient) {}

    askQuestion(request: ChatRequest): Observable<ChatResponse> {
        return this.http.post<ChatResponse>(
            this.api_url,
            request
        );
    }
}