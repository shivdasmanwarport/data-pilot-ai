export interface ColumnDescription {
    column_name: string;
    description: string;
}

export interface TableCreationRequest {
    table_name: string;
    column_descriptions: ColumnDescription[];
    prompt: string;
}

export interface CreateTableResponse {
    success: boolean;
    message: string;
    table_name: string;
    row_count: number;
    column_count: number;
    column_descriptions: Record<string, string>;
    prompt: string;
}