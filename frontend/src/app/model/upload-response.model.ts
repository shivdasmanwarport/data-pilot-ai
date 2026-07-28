export interface ColumnInfo {
    name: string;
    original_name: string;
    type: string;
    sample_values: any[];
    null_count: number;
    unique_count: number;
    description: string;
}

export interface UploadResponse {
    success: boolean;
    message: string;
    columns: string[];
    column_info: ColumnInfo[];
    preview: Record<string, any>[];
    row_count: number;
    table_name: string;
}