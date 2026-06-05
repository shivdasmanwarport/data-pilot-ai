import { Component } from '@angular/core';
import { UploadComponent } from './component/upload/upload';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [UploadComponent],
  templateUrl: './app.html'
})
export class App {}