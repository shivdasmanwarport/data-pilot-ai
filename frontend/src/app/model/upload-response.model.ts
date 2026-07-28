export interface UploadResponse {
    success: boolean;
    message: string;
    columns: string[];
    preview: Record<string, any>[];
    row_count: number;
    table_name: string;
}