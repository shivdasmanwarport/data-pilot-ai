import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { UploadResponse } from '../model/upload_response.model';

@Injectable({
  providedIn: 'root'
})
export class UploadService {

  private apiUrl = 'http://localhost:8000/upload';

  constructor(private http: HttpClient) {}

  uploadFile(formData: FormData): Observable<UploadResponse> {
    return this.http.post<UploadResponse>(
      this.apiUrl,
      formData
    );
  }
}