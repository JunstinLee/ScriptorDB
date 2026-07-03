type Dict = Record<string, string>;

const en: Dict = {
  "tool.status.running": "Running",
  "tool.status.success": "OK",
  "tool.status.error": "Error",
  "tool.summary.ran_python_code": "Ran Python code",
  "tool.summary.created_csv": "Created CSV: {filename}",
  "tool.summary.created_file": "Created file: {filename}",
  "tool.summary.exported_excel": "Exported Excel: {filename}",
  "tool.summary.read_csv": "Read CSV: {filename}",
  "tool.summary.read_file": "Read file: {filename}",
  "tool.summary.listed_directory": "Listed directory: {directory}",
  "tool.summary.queried_database": "Queried database",
  "tool.summary.queried_database_with_sql": "Queried database: {preview}",
  "tool.summary.fetched_schema": "Fetched schema: {table}",
  "tool.summary.fetched_all_schemas": "Fetched all table schemas",
  "tool.summary.generated_chart": "Generated {type} chart",
  "tool.summary.generated_chart_titled": "Generated {type} chart: {title}",
  "tool.summary.created_table": "Created table",
  "tool.summary.created_table_named": "Created table {tableName} ({colCount} columns)",
  "tool.summary.executed_ddl": "Executed DDL",
  "tool.summary.executed_ddl_with_sql": "Executed DDL: {preview}",
  "tool.summary.wrote_data": "Wrote data",
  "tool.summary.inserted_data": "Inserted: {preview}",
  "tool.summary.updated_data": "Updated: {preview}",
  "tool.summary.deleted_data": "Deleted: {preview}",
  "tool.summary.wrote_data_with_sql": "Wrote: {preview}",
  "tool.summary.executed": "Executed",
  "tool.status_text.running": "Running",
  "tool.status_text.success_empty": "Done",
  "tool.status_text.error_no_code": "Failed",
  "tool.no_output": "(no output)",
  "tool.copy": "Copy",
  "tool.copied": "Copied",
  "tool.copy_error_id": "Copy error ID",
  "tool.default_csv_filename": "output.csv",
  "tool.default_filename": "file",
  "tool.default_chart_type": "chart",
  "tool.preview_ellipsis": "...",
  "tool.dml_insert": "Inserted",
  "tool.dml_update": "Updated",
  "tool.dml_delete": "Deleted",
  "tool.dml_write": "Wrote",
};

const dictionaries: Record<string, Dict> = { en };
let currentLocale = "en";

export function setLocale(locale: string) {
  if (locale in dictionaries) currentLocale = locale;
}

export function getLocale(): string {
  return currentLocale;
}

export function t(key: string, params?: Record<string, string | number>): string {
  const dict = dictionaries[currentLocale] ?? dictionaries.en;
  let s = dict[key] ?? dictionaries.en[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}
