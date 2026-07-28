import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { UploadService } from '../../services/upload.service';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './upload.html',
  styleUrl: './upload.css'
})
export class UploadComponent {
  question = '';
  answer = '';
  selectedFile: File | null = null;
  tableName = '';
  message = '';
  isLoading = false;
  isChatLoading = false;

  columns: string[] = [];
  preview: Record<string, any>[] = [];
  row_count = 0;
  uploadedTableName = '';

  constructor(
    private uploadService: UploadService,
    private chatService: ChatService
  ) {}

  onFileSelected(event: any): void {
    this.selectedFile = event.target.files[0];
    if (this.selectedFile) {
      // Auto-generate table name from filename
      const baseName = this.selectedFile.name.replace('.csv', '');
      this.tableName = baseName.replace(/[^a-zA-Z0-9_]/g, '_');
    }
  }

  uploadFile(): void {
    if (!this.selectedFile) {
      this.message = 'Please select a file first';
      return;
    }

    if (!this.tableName || this.tableName.trim() === '') {
      this.message = 'Please enter a table name';
      return;
    }

    // Validate table name
    const validTableName = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(this.tableName);
    if (!validTableName) {
      this.message = 'Table name can only contain letters, numbers, and underscores. Must start with a letter or underscore.';
      return;
    }

    this.isLoading = true;
    this.message = 'Uploading...';

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploadService.uploadFile(formData, this.tableName).subscribe({
      next: (response) => {
        this.preview = response.preview;
        this.columns = response.columns;
        this.row_count = response.row_count;
        this.uploadedTableName = response.table_name;
        this.message = `✅ ${response.message}`;
        this.isLoading = false;
        console.log('Upload successful:', response);
      },
      error: (error) => {
        console.error('Upload error:', error);
        this.message = `❌ Upload failed: ${error.error?.detail || 'Unknown error'}`;
        this.isLoading = false;
      }
    });
  }

  askQuestion(): void {
    if (!this.question || this.question.trim() === '') {
      return;
    }

    this.isChatLoading = true;
    this.answer = 'Thinking...';

    this.chatService.askQuestion({
      question: this.question
    }).subscribe({
      next: (response) => {
        console.log('Chat response:', response);
        this.answer = response.answer;
        this.isChatLoading = false;
      },
      error: (error) => {
        console.error('Chat error:', error);
        this.answer = `❌ Error: ${error.error?.detail || 'Failed to get response'}`;
        this.isChatLoading = false;
      }
    });
  }

  clearData(): void {
    this.columns = [];
    this.preview = [];
    this.row_count = 0;
    this.answer = '';
    this.question = '';
    this.selectedFile = null;
    this.tableName = '';
    this.uploadedTableName = '';
    this.message = 'Data cleared';
  }
}