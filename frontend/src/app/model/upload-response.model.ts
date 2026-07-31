export interface UploadColumnInfo {
  name: string;
  original_name: string;
  type: string;
  sample_values: Array<string | number | boolean | null>;
  null_count: number;
  unique_count: number;
  description: string;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  columns: string[];
  column_info: UploadColumnInfo[];
  preview: Record<string, unknown>[];
  row_count: number;
  table_name: string;
}