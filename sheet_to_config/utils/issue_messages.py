"""Localized rendering for structured exporter diagnostics."""

from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter


ISSUE_ADVICE_KEYS = {
    'REFERENCE_NOT_FOUND': 'issue.advice.reference_not_found',
    'REFERENCE_TABLE_ERROR': 'issue.advice.reference_table_error',
    'UNDEFINED_TYPE': 'issue.advice.undefined_type',
    'CONVERSION_ERROR': 'issue.advice.conversion_error',
    'CONSTRAINT_ERROR': 'issue.advice.constraint_error',
    'DUPLICATE_VALUE': 'issue.advice.duplicate_value',
    'BYTES_FORMAT_ERROR': 'issue.advice.bytes_format_error',
    'MISSING_PRIMARY_KEY': 'issue.advice.missing_primary_key',
    'INVALID_PRIMARY_KEY': 'issue.advice.invalid_primary_key',
    'INVALID_JSON_ROOT_KEY': 'issue.advice.invalid_json_root_key',
    'PRIMARY_KEY_NOT_EXPORTED': 'issue.advice.primary_key_not_exported',
    'MISSING_CODE': 'issue.advice.missing_code',
    'INVALID_CODE': 'issue.advice.invalid_code',
    'UNKNOWN_OUTPUT_FORMAT': 'issue.advice.unknown_output_format',
    'INVALID_PLATFORM': 'issue.advice.invalid_platform',
    'OUTPUT_PATH_CONFLICT': 'issue.advice.output_path_conflict',
    'WORKBOOK_READ_ERROR': 'issue.advice.workbook_read_error',
    'FORMULA_NO_CACHED_VALUE': 'issue.advice.formula_no_cached_value',
    'SELECTED_FILE_NOT_FOUND': 'issue.advice.selected_file_not_found',
    'NO_WORKBOOKS': 'issue.advice.no_workbooks',
    'EXPORT_ERROR': 'issue.advice.export_error',
    'MANIFEST_OR_COMMIT_ERROR': 'issue.advice.manifest_or_commit_error',
    'INCREMENTAL_MANIFEST_REQUIRED': 'issue.advice.incremental_manifest_required',
    'TYPE_DEFINITION_FILE_ERROR': 'issue.advice.type_definition_file_error',
    'WORKSHEET_ERROR': 'issue.advice.worksheet_error',
    'PROTO_SCHEMA_ERROR': 'issue.advice.proto_schema_error',
}


def localized_issue_message(
    issue: dict[str, Any], *, include_technical_detail: bool = False
) -> str:
    """Render one structured issue without exposing raw locale-specific text."""
    from sheet_to_config.i18n import tr

    code = str(issue.get('code') or 'UNKNOWN')
    key = f"issue.{code.lower()}"
    value = issue.get('rawValue')
    location = str(issue.get('path') or '').strip()
    if not location:
        file_name = str(issue.get('file') or '-').strip()
        sheet_name = str(issue.get('sheet') or '').strip()
        row = str(issue.get('row') or '').strip()
        column = str(issue.get('column') or '').strip()
        try:
            column = get_column_letter(int(column)) if column else ''
        except (TypeError, ValueError):
            pass
        cell = f"{column}{row}" if row and column else ''
        location = "/".join(part for part in (file_name, sheet_name) if part)
        if cell:
            location = f"{location}!{cell}"
    location = location or '-'

    rendered = tr(
        key,
        code=code,
        field=str(issue.get('field') or '-'),
        value='-' if value is None else str(value),
        file=str(issue.get('file') or '-'),
        sheet=str(issue.get('sheet') or '-'),
        row=str(issue.get('row') or '-'),
        column=str(issue.get('column') or '-'),
        location=location,
    )
    if rendered == key:
        rendered = tr('issue.default', code=code)

    context = [tr('issue.location', location=location)]
    if value is not None:
        context.append(tr('issue.actual_value', value=str(value)))
    advice_key = ISSUE_ADVICE_KEYS.get(code, 'issue.advice.generic')
    context.append(tr(advice_key))
    if include_technical_detail:
        detail = str(issue.get('message') or '').strip()
        if detail:
            context.append(tr('issue.technical_detail', detail=detail))
    return f"{rendered} | {'; '.join(context)}"
