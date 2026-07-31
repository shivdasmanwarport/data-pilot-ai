import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TableService {
  private apiUrl = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  getTables(): Observable<{ tables: string[], count: number }> {
    return this.http.get<{ tables: string[], count: number }>(`${this.apiUrl}/tables`);
  }

  selectTable(tableName: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/table/select`, { table_name: tableName });
  }

  // New method name used in upload.ts
  createTableWithMetadata(request: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/create-table`, request);
  }

  // Alias for consistency (used in modal)
  createTable(request: any): Observable<any> {
    return this.createTableWithMetadata(request);
  }

  clearData(): Observable<any> {
    return this.http.delete(`${this.apiUrl}/data`);
  }
}