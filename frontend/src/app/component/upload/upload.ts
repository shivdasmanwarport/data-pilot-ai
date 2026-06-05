import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { UploadService } from '../../services/upload.service';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';
@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule,
            FormsModule
            ],
  templateUrl: './upload.html',
  styleUrl: './upload.css'
})
export class UploadComponent {
  question='';
  answer = '';
  selectedFile: File | null = null;
  message = '';

  columns:string[]=[];
  preview: Record<string,any>[]=[];
  row_count: number=0;

  constructor(
  private uploadService: UploadService,
  private chatService: ChatService
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
          this.row_count=response.row_count
          this.message = 'File Uploaded successfully';
          console.log(this.message)
        },
        error: (error) => {
          console.error(error);
          this.message = 'Upload failed';
        }
      });
  }

  askQuestion():void{
    this.chatService
    .askQuestion({
      question:this.question
    })
    .subscribe({
      next:(response)=>{
        console.log(response);
        this.answer=response.answer;
      },
      error:(error)=>{
        console.log(error);
      }
      
    })
  }
}

