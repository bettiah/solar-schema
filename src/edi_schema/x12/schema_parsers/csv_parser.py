"""
CSV Parser for X12 Schema Files.

Parses the quote-comma delimited files used in X12 005010 schema definitions.
These files use the format: "field1","field2","field3"

Handles:
- Fields enclosed in double quotes
- Embedded quotes (doubled: "")
- Empty fields
"""

import csv
from pathlib import Path
from typing import Iterator


def parse_csv_file(filepath: Path | str) -> list[list[str]]:
    """
    Parse a quote-comma delimited file and return all rows.

    Args:
        filepath: Path to the CSV file

    Returns:
        List of rows, where each row is a list of field values

    Example:
        >>> rows = parse_csv_file("/path/to/sethead.txt")
        >>> rows[0]
        ['100', 'Insurance Plan Description', 'PG']
    """
    filepath = Path(filepath)
    rows = []

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"')
        for row in reader:
            # Skip empty rows
            if row and any(field.strip() for field in row):
                rows.append(row)

    return rows


def iter_csv_file(filepath: Path | str) -> Iterator[list[str]]:
    """
    Iterate over rows in a quote-comma delimited file.

    Yields one row at a time for memory-efficient processing of large files.

    Args:
        filepath: Path to the CSV file

    Yields:
        List of field values for each row
    """
    filepath = Path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"')
        for row in reader:
            if row and any(field.strip() for field in row):
                yield row


def parse_csv_to_dict(
    filepath: Path | str,
    key_index: int = 0,
) -> dict[str, list[str]]:
    """
    Parse a CSV file into a dictionary keyed by a specific field.

    Useful for files like sethead.txt, seghead.txt where the first
    field is a unique identifier.

    Args:
        filepath: Path to the CSV file
        key_index: Index of the field to use as dictionary key (default: 0)

    Returns:
        Dictionary mapping the key field to the full row

    Example:
        >>> sets = parse_csv_to_dict("/path/to/sethead.txt")
        >>> sets["810"]
        ['810', 'Invoice', 'IN']
    """
    filepath = Path(filepath)
    result = {}

    for row in iter_csv_file(filepath):
        if len(row) > key_index:
            key = row[key_index]
            result[key] = row

    return result


def parse_csv_grouped(
    filepath: Path | str,
    group_index: int = 0,
) -> dict[str, list[list[str]]]:
    """
    Parse a CSV file and group rows by a specific field.

    Useful for files like setdetl.txt, segdetl.txt where multiple
    rows share the same identifier.

    Args:
        filepath: Path to the CSV file
        group_index: Index of the field to group by (default: 0)

    Returns:
        Dictionary mapping the group field to a list of matching rows

    Example:
        >>> details = parse_csv_grouped("/path/to/setdetl.txt")
        >>> len(details["810"])  # Number of segments in transaction set 810
        42
    """
    filepath = Path(filepath)
    result: dict[str, list[list[str]]] = {}

    for row in iter_csv_file(filepath):
        if len(row) > group_index:
            key = row[group_index]
            if key not in result:
                result[key] = []
            result[key].append(row)

    return result


# Specific parsers for each file type


def parse_sethead(filepath: Path | str) -> dict[str, tuple[str, str, str]]:
    """
    Parse sethead.txt (Transaction Set definitions).

    Format: "SET_ID","NAME","FUNCTIONAL_GROUP"

    Args:
        filepath: Path to sethead.txt

    Returns:
        Dictionary mapping set_id to (id, name, functional_group)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 3:
            set_id, name, fg = row[0], row[1], row[2]
            result[set_id] = (set_id, name, fg)
    return result


def parse_setdetl(filepath: Path | str) -> dict[str, list[tuple]]:
    """
    Parse setdetl.txt (Transaction Set segment structure).

    Format: "SET_ID","AREA","SEQUENCE","SEGMENT","REQUIREMENT","MAX_USE","LOOP_LEVEL","LOOP_REPEAT","LOOP_ID"

    Args:
        filepath: Path to setdetl.txt

    Returns:
        Dictionary mapping set_id to list of segment tuples
    """
    result: dict[str, list[tuple]] = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 9:
            set_id = row[0]
            segment_info = (
                row[1],  # area
                row[2],  # sequence
                row[3],  # segment_id
                row[4],  # requirement
                row[5],  # max_use
                row[6],  # loop_level
                row[7],  # loop_repeat
                row[8],  # loop_id
            )
            if set_id not in result:
                result[set_id] = []
            result[set_id].append(segment_info)
    return result


def parse_seghead(filepath: Path | str) -> dict[str, tuple[str, str]]:
    """
    Parse seghead.txt (Segment definitions).

    Format: "SEGMENT_ID","NAME"

    Args:
        filepath: Path to seghead.txt

    Returns:
        Dictionary mapping segment_id to (id, name)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 2:
            seg_id, name = row[0], row[1]
            result[seg_id] = (seg_id, name)
    return result


def parse_segdetl(filepath: Path | str) -> dict[str, list[tuple]]:
    """
    Parse segdetl.txt (Segment element structure).

    Format: "SEGMENT_ID","SEQUENCE","ELEMENT_ID","REQUIREMENT"[,"REPETITION"]
    Note: REPETITION column is optional (not present in 004010)

    Args:
        filepath: Path to segdetl.txt

    Returns:
        Dictionary mapping segment_id to list of element tuples
    """
    result: dict[str, list[tuple]] = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 4:
            seg_id = row[0]
            element_info = (
                row[1],  # sequence
                row[2],  # element_id
                row[3],  # requirement
                row[4] if len(row) >= 5 else "1",  # repetition (default to 1)
            )
            if seg_id not in result:
                result[seg_id] = []
            result[seg_id].append(element_info)
    return result


def parse_elehead(filepath: Path | str) -> dict[str, tuple[str, str]]:
    """
    Parse elehead.txt (Element definitions).

    Format: "ELEMENT_ID","NAME"

    Args:
        filepath: Path to elehead.txt

    Returns:
        Dictionary mapping element_id to (id, name)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 2:
            ele_id, name = row[0], row[1]
            result[ele_id] = (ele_id, name)
    return result


def parse_eledetl(filepath: Path | str) -> dict[str, tuple[str, str, str, str]]:
    """
    Parse eledetl.txt (Element attributes).

    Format: "ELEMENT_ID","TYPE","MIN_LENGTH","MAX_LENGTH"

    Args:
        filepath: Path to eledetl.txt

    Returns:
        Dictionary mapping element_id to (id, type, min_length, max_length)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 4:
            ele_id, data_type, min_len, max_len = row[0], row[1], row[2], row[3]
            result[ele_id] = (ele_id, data_type, min_len, max_len)
    return result


def parse_comhead(filepath: Path | str) -> dict[str, tuple[str, str]]:
    """
    Parse comhead.txt (Composite definitions).

    Format: "COMPOSITE_ID","NAME"

    Args:
        filepath: Path to comhead.txt

    Returns:
        Dictionary mapping composite_id to (id, name)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 2:
            com_id, name = row[0], row[1]
            result[com_id] = (com_id, name)
    return result


def parse_comdetl(filepath: Path | str) -> dict[str, list[tuple]]:
    """
    Parse comdetl.txt (Composite element structure).

    Format: "COMPOSITE_ID","SEQUENCE","ELEMENT_ID","REQUIREMENT"

    Args:
        filepath: Path to comdetl.txt

    Returns:
        Dictionary mapping composite_id to list of element tuples
    """
    result: dict[str, list[tuple]] = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 4:
            com_id = row[0]
            element_info = (
                row[1],  # sequence
                row[2],  # element_id
                row[3],  # requirement
            )
            if com_id not in result:
                result[com_id] = []
            result[com_id].append(element_info)
    return result


def parse_cshead(filepath: Path | str) -> dict[str, tuple[str, str]]:
    """
    Parse cshead.txt (Code Source definitions).

    Format: "CODE_SOURCE_ID","NAME"

    Args:
        filepath: Path to cshead.txt

    Returns:
        Dictionary mapping code_source_id to (id, name)
    """
    result = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 2:
            cs_id, name = row[0], row[1]
            result[cs_id] = (cs_id, name)
    return result


def parse_cs_de(filepath: Path | str) -> dict[str, list[str]]:
    """
    Parse cs_de.txt (Code Source to Element mapping).

    Format: "CODE_SOURCE_ID","ELEMENT_ID"

    Args:
        filepath: Path to cs_de.txt

    Returns:
        Dictionary mapping code_source_id to list of element_ids
    """
    result: dict[str, list[str]] = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 2:
            cs_id, ele_id = row[0], row[1]
            if cs_id not in result:
                result[cs_id] = []
            result[cs_id].append(ele_id)
    return result


def parse_cs_cv(filepath: Path | str) -> dict[str, list[tuple[str, str, str]]]:
    """
    Parse cs_cv.txt (Code Source to Code Value mapping).

    Format: "CODE_SOURCE_ID","ELEMENT_ID","CODE_VALUE"

    Args:
        filepath: Path to cs_cv.txt

    Returns:
        Dictionary mapping code_source_id to list of (element_id, code_value) tuples
    """
    result: dict[str, list[tuple[str, str, str]]] = {}
    for row in iter_csv_file(filepath):
        if len(row) >= 3:
            cs_id, ele_id, code_value = row[0], row[1], row[2]
            if cs_id not in result:
                result[cs_id] = []
            result[cs_id].append((cs_id, ele_id, code_value))
    return result
