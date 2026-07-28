import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { UploadService } from '../../services/upload.service';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';
import { TableService } from '../../services/table.service';
import { ColumnDescription } from '../../model/table-creation-request.model';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './upload.html',
  styleUrls: ['./upload.css']
})
export class UploadComponent {
  // File upload
  selectedFile: File | null = null;
  tableName = '';
  message = '';
  isLoading = false;
  
  // Column descriptions
  columnInfos: any[] = [];
  showColumnDescriptions = false;
  isCreatingTable = false;
  
  // Chat
  question = '';
  answer = '';
  isChatLoading = false;
  userPrompt = '';
  
  // Dataset info
  columns: string[] = [];
  preview: Record<string, any>[] = [];
  row_count = 0;
  uploadedTableName = '';
  tableCreated = false;

  constructor(
    private uploadService: UploadService,
    private chatService: ChatService,
    private tableService: TableService
  ) {}

  // Helper method for template
  hasDescriptions(): boolean {
    return this.columnInfos.some(c => c.description && c.description.trim() !== '');
  }

  onFileSelected(event: any): void {
    this.selectedFile = event.target.files[0];
    if (this.selectedFile) {
      const baseName = this.selectedFile.name.replace('.csv', '');
      this.tableName = baseName.replace(/[^a-zA-Z0-9_]/g, '_');
      this.tableCreated = false;
      this.columnInfos = [];
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
        this.columnInfos = response.column_info || [];
        this.message = `✅ ${response.message}`;
        this.isLoading = false;
        this.showColumnDescriptions = true;
        
        console.log('Upload successful:', response);
      },
      error: (error) => {
        console.error('Upload error:', error);
        this.message = `❌ Upload failed: ${error.error?.detail || 'Unknown error'}`;
        this.isLoading = false;
      }
    });
  }

  createTableWithMetadata(): void {
    // Prepare column descriptions
    const columnDescriptions: ColumnDescription[] = this.columnInfos.map(info => ({
      column_name: info.name,
      description: info.description || ''
    }));

    const request = {
      table_name: this.tableName,
      column_descriptions: columnDescriptions,
      prompt: this.userPrompt || ''
    };

    this.isCreatingTable = true;
    this.message = 'Creating table with metadata...';

    this.tableService.createTableWithMetadata(request).subscribe({
      next: (response) => {
        this.message = `✅ ${response.message}`;
        this.tableCreated = true;
        this.isCreatingTable = false;
        this.showColumnDescriptions = false;
        console.log('Table created:', response);
      },
      error: (error) => {
        console.error('Create table error:', error);
        this.message = `❌ Failed to create table: ${error.error?.detail || 'Unknown error'}`;
        this.isCreatingTable = false;
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
    this.message = '';
    this.columnInfos = [];
    this.userPrompt = '';
    this.tableCreated = false;
    this.showColumnDescriptions = false;
  }

  trackByColumn(index: number, item: any): string {
    return item.name;
  }
}