import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { TableCreationRequest, CreateTableResponse } from '../model/table-creation-request.model';

@Injectable({
  providedIn: 'root'
})
export class TableService {
  private apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  createTableWithMetadata(request: TableCreationRequest): Observable<CreateTableResponse> {
    return this.http.post<CreateTableResponse>(
      `${this.apiUrl}/create-table`,
      request
    );
  }

  getMetadata(): Observable<any> {
    return this.http.get(`${this.apiUrl}/metadata`);
  }

  clearData(): Observable<any> {
    return this.http.delete(`${this.apiUrl}/data`);
  }
}