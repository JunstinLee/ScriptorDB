export interface SchemaColumn {
  name: string;
  type: string;
  pk: boolean;
  notnull: boolean;
  default_value: string | null;
  autoincrement: boolean;
}

export interface SchemaTable {
  name: string;
  sql: string;
  columns: SchemaColumn[];
}

export interface SchemaResponse {
  tables: SchemaTable[];
}
