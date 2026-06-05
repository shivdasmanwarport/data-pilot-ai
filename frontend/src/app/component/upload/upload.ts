import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { UploadService } from '../../services/upload.service';
@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './upload.html',
  styleUrl: './upload.css'
})
export class UploadComponent {
  selectedFile: File | null = null;
  message = '';

  columns:string[]=[];
  preview: Record<string,any>[]=[];

  constructor(
  private uploadService: UploadService
  ) {}

  onFileSelected(event: any): void {
    this.selectedFile = event.target.files[0];
  }

  uploadFile(): void {
    if (!this.selectedFile) return;

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploadService
      .uploadFile(formData)
      .subscribe({
        next: (response) => {
          this.preview = response.preview;
          this.columns = response.columns;
          this.message = 'File Uploaded successfully';
          console.log(this.message)
        },
        error: (error) => {
          console.error(error);
          this.message = 'Upload failed';
        }
      });
  }
}

