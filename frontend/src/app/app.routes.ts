import { Routes } from '@angular/router';
import { ChatComponent } from './components/chat/chat';
export const routes: Routes = [
  { path: '', component: ChatComponent },  // make it the default
  // other routes...
];