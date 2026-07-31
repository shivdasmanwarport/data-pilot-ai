import { Component, OnInit, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';
import { TableService } from '../../services/table.service';
import { UploadService } from '../../services/upload.service';
import { UploadColumnInfo, UploadResponse } from '../../model/upload-response.model';
import { ChatResultPayload, ChatSessionItem, CurrentUser } from '../../model/chat-response.model';

interface TableSelectionResponse {
  success: boolean;
  message: string;
  table_name: string;
  columns: string[];
  row_count: number;
  column_descriptions: Record<string, string>;
  prompt: string | null;
}

interface WorkspaceMessage {
  role: 'user' | 'assistant';
  text: string;
  sqlQuery: string | null;
  resultPayload: ChatResultPayload | null;
  timestamp?: string;
}

type WorkspaceMode = 'chat' | 'upload';
type SidebarView = 'sessions' | 'tables';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.html',
  styleUrls: ['./chat.css']
})
export class ChatComponent implements OnInit {
  @ViewChild('messageContainer') private messageContainer!: ElementRef;

  currentUser: CurrentUser | null = null;
  workspaceMode: WorkspaceMode = 'chat';
  sidebarView: SidebarView = 'sessions';
  tables: string[] = [];
  activeTableName: string = '';
  activeTableRowCount = 0;
  activeTablePrompt = '';
  activeColumns: string[] = [];
  sessions: ChatSessionItem[] = [];
  activeSessionId: number | null = null;
  activeSessionTitle = '';
  chatHistory: WorkspaceMessage[] = [];
  newQuestion: string = '';
  isLoading = false;
  isSelectingTable = false;
  isCreatingSession = false;

  selectedFile: File | null = null;
  tableName = '';
  uploadMessage = '';
  isUploading = false;
  uploadSuccess = false;
  columnInfos: UploadColumnInfo[] = [];
  previewData: Record<string, unknown>[] = [];
  previewColumns: string[] = [];
  userPrompt = '';
  isCreating = false;

  constructor(
    private chatService: ChatService,
    private tableService: TableService,
    private uploadService: UploadService
  ) {}

  ngOnInit() {
    this.chatService.getCurrentUser().subscribe({
      next: (user) => {
        this.currentUser = user;
        this.loadTables();
      },
      error: (err) => {
        console.error('Failed to load current user', err);
        this.loadTables();
      }
    });
  }

  loadTables(preferredTable?: string) {
    this.tableService.getTables().subscribe({
      next: (res) => {
        this.tables = res.tables;
        const nextTable = preferredTable || this.activeTableName || this.tables[0];
        if (nextTable && this.tables.includes(nextTable)) {
          this.selectTable(nextTable, { openSidebar: false });
        } else if (!this.tables.length) {
          this.activeTableName = '';
          this.activeTablePrompt = '';
          this.activeColumns = [];
          this.activeTableRowCount = 0;
          this.sessions = [];
          this.activeSessionId = null;
          this.activeSessionTitle = '';
          this.chatHistory = [];
        }
      },
      error: (err) => console.error('Failed to load tables', err)
    });
  }

  setSidebarView(view: SidebarView) {
    this.sidebarView = view;
  }

  switchToUploadMode() {
    this.workspaceMode = 'upload';
    this.resetUploadDraft(false);
  }

  selectTable(table: string, options?: { openSidebar?: boolean; autoCreateSession?: boolean }) {
    if (!table) {
      return;
    }

    this.activeTableName = table;
    this.workspaceMode = 'chat';
    this.sidebarView = options?.openSidebar ? 'tables' : this.sidebarView;
    this.isSelectingTable = true;
    this.tableService.selectTable(table).subscribe({
      next: (res: TableSelectionResponse) => {
        this.activeTableRowCount = res.row_count;
        this.activeColumns = res.columns;
        this.activeTablePrompt = res.prompt || '';
        this.activeSessionId = null;
        this.activeSessionTitle = '';
        this.chatHistory = [];
        this.loadSessions(table, options?.autoCreateSession ?? false);
        this.isSelectingTable = false;
      },
      error: (err) => {
        console.error('Failed to select table', err);
        this.isSelectingTable = false;
      }
    });
  }

  loadSessions(tableName: string, autoCreateSession = false) {
    this.chatService.getSessions(tableName, this.currentUser?.id).subscribe({
      next: (res) => {
        this.sessions = res.sessions;
        if (this.activeSessionId) {
          const matchingSession = this.sessions.find((session) => session.id === this.activeSessionId);
          if (matchingSession) {
            this.activeSessionTitle = matchingSession.title;
            this.loadChatHistory(this.activeSessionId);
            return;
          }
        }

        if (this.sessions.length > 0) {
          this.openSession(this.sessions[0].id);
        } else if (autoCreateSession) {
          this.createSessionForActiveTable();
        } else {
          this.chatHistory = [];
          this.activeSessionId = null;
          this.activeSessionTitle = '';
          this.scrollToBottom();
        }
      },
      error: (err) => console.error('Failed to load sessions', err)
    });
  }

  createSessionForActiveTable(title?: string) {
    if (!this.activeTableName || this.isCreatingSession) {
      return;
    }

    this.isCreatingSession = true;
    this.chatService.createSession({
      table_name: this.activeTableName,
      user_id: this.currentUser?.id,
      title
    }).subscribe({
      next: (session) => {
        this.isCreatingSession = false;
        this.sessions = [session, ...this.sessions];
        this.openSession(session.id);
      },
      error: (err) => {
        console.error('Failed to create session', err);
        this.isCreatingSession = false;
      }
    });
  }

  openSession(sessionId: number) {
    this.chatService.selectSession(sessionId).subscribe({
      next: (res) => {
        this.workspaceMode = 'chat';
        this.sidebarView = 'sessions';
        this.activeSessionId = res.session.id;
        this.activeSessionTitle = res.session.title;
        this.activeTableName = res.table.table_name;
        this.activeTableRowCount = res.table.row_count;
        this.activeColumns = res.table.columns;
        this.activeTablePrompt = res.table.prompt || '';
        this.loadChatHistory(sessionId);
      },
      error: (err) => console.error('Failed to open session', err)
    });
  }

  loadChatHistory(sessionId?: number) {
    if (!sessionId && !this.activeSessionId && !this.activeTableName) return;
    this.chatService.getHistory({ tableName: this.activeTableName, sessionId: sessionId ?? this.activeSessionId ?? undefined }).subscribe({
      next: (res) => {
        this.chatHistory = [];
        res.history.forEach((item) => {
          this.chatHistory.push({ role: 'user', text: item.user_message, sqlQuery: null, resultPayload: null, timestamp: item.timestamp });
          if (item.assistant_response) {
            this.chatHistory.push({
              role: 'assistant',
              text: item.assistant_response,
              sqlQuery: item.sql_query,
              resultPayload: item.result_payload,
              timestamp: item.timestamp
            });
          }
        });
        this.scrollToBottom();
      },
      error: (err) => console.error('Failed to load history', err)
    });
  }

  sendQuestion() {
    if (!this.newQuestion || !this.activeTableName || this.isLoading || this.isCreatingSession) return;
    const question = this.newQuestion.trim();
    this.chatHistory.push({ role: 'user', text: question, sqlQuery: null, resultPayload: null });
    this.newQuestion = '';
    this.isLoading = true;
    this.scrollToBottom();

    this.chatService.askQuestion({
      question,
      table_name: this.activeTableName,
      session_id: this.activeSessionId ?? undefined,
      user_id: this.currentUser?.id
    }).subscribe({
      next: (res) => {
        if (!this.activeSessionId && res.session_id) {
          this.activeSessionId = res.session_id;
          this.loadSessions(this.activeTableName);
        }
        this.chatHistory.push({ role: 'assistant', text: res.answer, sqlQuery: res.sql_query, resultPayload: res.result_payload });
        this.isLoading = false;
        this.scrollToBottom();
      },
      error: (err) => {
        console.error('Chat error', err);
        this.chatHistory.push({ role: 'assistant', text: 'Sorry, an error occurred.', sqlQuery: null, resultPayload: null });
        this.isLoading = false;
      }
    });
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] || null;
    if (this.selectedFile) {
      const baseName = this.selectedFile.name.replace('.csv', '');
      this.tableName = baseName.replace(/[^a-zA-Z0-9_]/g, '_');
      this.uploadMessage = '';
    }
  }

  uploadFile() {
    if (!this.selectedFile || !this.tableName) {
      return;
    }

    const formData = new FormData();
    formData.append('file', this.selectedFile);
    this.isUploading = true;
    this.uploadMessage = 'Uploading CSV and profiling columns...';

    this.uploadService.uploadFile(formData, this.tableName).subscribe({
      next: (response: UploadResponse) => {
        this.columnInfos = response.column_info;
        this.previewData = response.preview as Record<string, unknown>[];
        this.previewColumns = response.columns;
        this.uploadSuccess = true;
        this.uploadMessage = response.message;
        this.isUploading = false;
      },
      error: (err) => {
        this.uploadMessage = err.error?.detail || 'Upload failed.';
        this.isUploading = false;
      }
    });
  }

  createTable() {
    if (!this.tableName || this.isCreating) {
      return;
    }

    this.isCreating = true;
    this.tableService.createTableWithMetadata({
      table_name: this.tableName,
      column_descriptions: this.columnInfos.map((column) => ({
        column_name: column.name,
        description: column.description || ''
      })),
      prompt: this.userPrompt || ''
    }).subscribe({
      next: () => {
        const createdTableName = this.tableName;
        this.isCreating = false;
        this.workspaceMode = 'chat';
        this.sidebarView = 'tables';
        this.resetUploadDraft(true);
        this.loadTables(createdTableName);
      },
      error: (err) => {
        this.uploadMessage = err.error?.detail || 'Failed to create the table.';
        this.isCreating = false;
      }
    });
  }

  resetUploadDraft(clearSelection: boolean) {
    this.uploadSuccess = false;
    this.columnInfos = [];
    this.previewData = [];
    this.previewColumns = [];
    this.userPrompt = '';
    this.uploadMessage = '';
    this.isUploading = false;
    this.isCreating = false;
    if (clearSelection) {
      this.selectedFile = null;
      this.tableName = '';
    }
  }

  formatMessage(text: string): string {
    return this.escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br />');
  }

  getResultSummary(resultPayload: ChatResultPayload): string {
    if (resultPayload.type === 'scalar' && resultPayload.rows.length) {
      return 'Single value result';
    }
    const rowLabel = resultPayload.row_count === 1 ? 'row' : 'rows';
    return `${resultPayload.row_count.toLocaleString()} ${rowLabel}`;
  }

  getScalarEntries(resultPayload: ChatResultPayload): Array<{ label: string; value: string }> {
    const firstRow = resultPayload.rows[0] || {};
    return Object.entries(firstRow).map(([key, value]) => ({
      label: key.replace(/_/g, ' '),
      value: this.formatCellValue(value)
    }));
  }

  formatCellValue(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'number') {
      return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
    if (typeof value === 'boolean') {
      return value ? 'True' : 'False';
    }
    return String(value);
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  scrollToBottom() {
    setTimeout(() => {
      if (this.messageContainer) {
        this.messageContainer.nativeElement.scrollTop = this.messageContainer.nativeElement.scrollHeight;
      }
    }, 100);
  }

  clearAllData() {
    if (confirm('Are you sure you want to clear all data?')) {
      this.tableService.clearData().subscribe(() => {
        this.tables = [];
        this.activeTableName = '';
        this.activeTableRowCount = 0;
        this.activeTablePrompt = '';
        this.activeColumns = [];
        this.sessions = [];
        this.activeSessionId = null;
        this.activeSessionTitle = '';
        this.chatHistory = [];
        this.workspaceMode = 'upload';
        this.sidebarView = 'sessions';
      });
    }
  }

  formatSessionTime(timestamp?: string | null): string {
    if (!timestamp) {
      return 'No activity yet';
    }
    const date = new Date(timestamp);
    return date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  }

  isActiveSession(sessionId: number): boolean {
    return this.activeSessionId === sessionId;
  }

  useSuggestedQuestion(question: string) {
    this.newQuestion = question;
    this.sendQuestion();
  }
}