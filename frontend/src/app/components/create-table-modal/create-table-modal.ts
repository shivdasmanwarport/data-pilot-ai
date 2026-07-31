import { Component, EventEmitter, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UploadService } from '../../services/upload.service';
import { TableService } from '../../services/table.service';

@Component({
  selector: 'app-create-table-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './create-table-modal.html',
  styleUrls: ['./create-table-modal.css']
})
export class CreateTableModalComponent {
  @Output() close = new EventEmitter<void>();
  @Output() tableCreated = new EventEmitter<string>();

  private uploadService = inject(UploadService);
  private tableService = inject(TableService);

  // Step 1
  selectedFile: File | null = null;
  tableName = '';
  uploadMessage = '';
  isUploading = false;
  uploadSuccess = false;

  // Step 2
  columnInfos: any[] = [];
  userPrompt = '';
  isCreating = false;
  previewData: any[] = [];
  columns: string[] = [];

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
    if (this.selectedFile) {
      const baseName = this.selectedFile.name.replace('.csv', '');
      this.tableName = baseName.replace(/[^a-zA-Z0-9_]/g, '_');
    }
  }

  uploadFile() {
    if (!this.selectedFile || !this.tableName) return;
    this.isUploading = true;
    this.uploadMessage = 'Uploading...';

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    this.uploadService.uploadFile(formData, this.tableName).subscribe({
      next: (response) => {
        this.columnInfos = response.column_info || [];
        this.previewData = response.preview;
        this.columns = response.columns;
        this.uploadSuccess = true;
        this.uploadMessage = '✅ Upload successful!';
        this.isUploading = false;
      },
      error: (err) => {
        this.uploadMessage = '❌ Upload failed: ' + (err.error?.detail || 'Unknown error');
        this.isUploading = false;
      }
    });
  }

  createTable() {
    const columnDescriptions = this.columnInfos.map(info => ({
      column_name: info.name,
      description: info.description || ''
    }));

    this.isCreating = true;
    this.tableService.createTable({
      table_name: this.tableName,
      column_descriptions: columnDescriptions,
      prompt: this.userPrompt
    }).subscribe({
      next: (response) => {
        this.isCreating = false;
        this.tableCreated.emit(this.tableName);
        this.close.emit();
      },
      error: (err) => {
        alert('Failed to create table: ' + (err.error?.detail || 'Unknown error'));
        this.isCreating = false;
      }
    });
  }

  closeModal() {
    this.close.emit();
  }
}