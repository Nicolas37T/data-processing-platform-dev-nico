"""Utility module to dynamically update DAG tags and doc_md in Airflow."""

import os
import re
import logging

logger = logging.getLogger(__name__)


def find_dag_file(dag_id: str, process_type: str) -> str | None:
    """Locate the Python file of a DAG inside or outside Docker."""
    clean_id = dag_id.strip()
    candidates = [
        f"/opt/airflow/dags/{process_type}/{clean_id}.py",
        os.path.join(os.path.dirname(__file__), "..", process_type, f"{clean_id}.py"),
        os.path.join(os.getcwd(), "dags", process_type, f"{clean_id}.py"),
    ]
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    return None


def update_dag_tag_and_doc(dag_id: str, process_type: str, new_date: str) -> bool:
    """
    Updates the date tag and doc_md date field in the DAG file.
    
    Args:
        dag_id: Code of the DAG (e.g., 'D_BO_000000462' or 'C_BO_000000462')
        process_type: 'download' or 'conversion'
        new_date: String or date object representing the new execution date (YYYY-MM-DD)
    """
    if not new_date:
        return False

    new_date_str = str(new_date).strip()
    # Normalize to YYYY-MM-DD if datetime object string or extra time present
    match_date = re.search(r'\d{4}-\d{2}-\d{2}', new_date_str)
    if match_date:
        new_date_str = match_date.group(0)

    dag_path = find_dag_file(dag_id, process_type)
    if not dag_path:
        logger.warning(f"Could not find DAG file for {dag_id} ({process_type}) to update tags.")
        return False

    try:
        with open(dag_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Update tags list
        def replace_date_in_tags(match):
            tags_content = match.group(1)
            # Check if there is already a YYYY-MM-DD date tag
            if re.search(r"['\"]\d{4}-\d{2}-\d{2}['\"]", tags_content):
                updated_tags = re.sub(
                    r"['\"]\d{4}-\d{2}-\d{2}['\"]",
                    f"'{new_date_str}'",
                    tags_content,
                    count=1
                )
            else:
                updated_tags = tags_content.strip()
                if updated_tags:
                    updated_tags += f", '{new_date_str}'"
                else:
                    updated_tags = f"'{new_date_str}'"
            return f"tags= [{updated_tags}]"

        updated_content = re.sub(r"tags\s*=\s*\[(.*?)\]", replace_date_in_tags, content, count=1, flags=re.DOTALL)

        # 2. Update doc_md table date (supports both Markdown and HTML table formats)
        if process_type == 'download':
            updated_content = re.sub(
                r"(\|\s*\*\*📅 Última Descarga\*\*\s*\|\s*\*\*)[^*]+(\*\*\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r'(📅 Última Descarga</td>\s*<td[^>]*><b[^>]*>)[^<]+(</b>)',
                rf'\g<1>{new_date_str}\g<2>',
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*Última Descarga \(`updated_to`\)\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*updated_to\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
        elif process_type == 'conversion':
            updated_content = re.sub(
                r"(\|\s*\*\*📅 Última Conversión\*\*\s*\|\s*\*\*)[^*]+(\*\*\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r'(📅 Última Conversión</td>\s*<td[^>]*><b[^>]*>)[^<]+(</b>)',
                rf'\g<1>{new_date_str}\g<2>',
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*Última Conversión \(`converted_to`\)\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*converted_to\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
        elif process_type == 'migration':
            updated_content = re.sub(
                r"(\|\s*\*\*📅 Última Migración\*\*\s*\|\s*\*\*)[^*]+(\*\*\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r'(📅 Última Migración</td>\s*<td[^>]*><b[^>]*>)[^<]+(</b>)',
                rf'\g<1>{new_date_str}\g<2>',
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*Última Migración \(`migrated_to`\)\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )
            updated_content = re.sub(
                r"(\|\s*\*\*migrated_to\*\*\s*\|\s*`)[^`]+(`\s*\|)",
                rf"\g<1>{new_date_str}\g<2>",
                updated_content
            )

        if updated_content != content:
            with open(dag_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            logger.info(f"Successfully updated DAG {dag_id} with new date {new_date_str} in tags and doc_md.")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating DAG metadata for {dag_id}: {e}")
        return False
