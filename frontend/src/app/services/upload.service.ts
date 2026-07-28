import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UploadResponse } from '../model/upload-response.model';

@Injectable({
  providedIn: 'root'
})
export class UploadService {
  private apiUrl = 'http://localhost:8000/upload';

  constructor(private http: HttpClient) {}

  uploadFile(formData: FormData, tableName: string): Observable<UploadResponse> {
    const params = new HttpParams().set('table_name', tableName);
    return this.http.post<UploadResponse>(
      this.apiUrl,
      formData,
      { params }
    );
  }
}