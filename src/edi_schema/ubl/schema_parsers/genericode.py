"""
Genericode Parser.

Parses OASIS Genericode (.gc) files to extract code lists.
"""

from pathlib import Path

from lxml import etree

from ..models import CodeList, CodeListColumn, CodeValue

# Genericode namespace
GC_NS = "http://docs.oasis-open.org/codelist/ns/genericode/1.0/"
GC_NSMAP = {"gc": GC_NS}


def parse_genericode(path: Path) -> CodeList:
    """
    Parse a Genericode file.

    Args:
        path: Path to the .gc file

    Returns:
        CodeList object with all values
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    # Parse identification
    ident = root.find("Identification", namespaces=None)
    if ident is None:
        # Try with namespace
        ident = root.find("{%s}Identification" % GC_NS)

    short_name = _get_text(ident, "ShortName") if ident is not None else path.stem
    long_name = _get_text(ident, "LongName") if ident is not None else ""
    version = _get_text(ident, "Version") if ident is not None else ""
    canonical_uri = _get_text(ident, "CanonicalUri") if ident is not None else ""

    # Parse agency info
    agency_name = ""
    agency_id = ""
    if ident is not None:
        agency = ident.find("Agency", namespaces=None)
        if agency is None:
            agency = ident.find("{%s}Agency" % GC_NS)
        if agency is not None:
            agency_name = _get_text(agency, "LongName")
            agency_id = _get_text(agency, "Identifier")

    # Generate ID from filename or short name
    code_list_id = path.stem

    # Parse columns
    columns: list[CodeListColumn] = []
    column_set = root.find("ColumnSet", namespaces=None)
    if column_set is None:
        column_set = root.find("{%s}ColumnSet" % GC_NS)

    if column_set is not None:
        for col in column_set.findall("Column", namespaces=None):
            col_id = col.get("Id", "")
            use = col.get("Use", "optional")
            short = _get_text(col, "ShortName")
            data_elem = col.find("Data", namespaces=None)
            data_type = data_elem.get("Type", "string") if data_elem is not None else "string"
            lang = data_elem.get("Lang") if data_elem is not None else None

            columns.append(
                CodeListColumn(
                    id=col_id,
                    short_name=short,
                    data_type=data_type,
                    required=use == "required",
                    lang=lang,
                )
            )

    # Parse values
    values: list[CodeValue] = []
    simple_list = root.find("SimpleCodeList", namespaces=None)
    if simple_list is None:
        simple_list = root.find("{%s}SimpleCodeList" % GC_NS)

    if simple_list is not None:
        for row in simple_list.findall("Row", namespaces=None):
            row_data: dict[str, str] = {}

            for value in row.findall("Value", namespaces=None):
                col_ref = value.get("ColumnRef", "")
                simple_value = value.find("SimpleValue", namespaces=None)
                if simple_value is not None and simple_value.text:
                    row_data[col_ref] = simple_value.text.strip()

            # Extract standard columns
            code = row_data.get("code", "")
            name = row_data.get("name", "")
            description = row_data.get("description", "")

            if code:
                # Store remaining columns as metadata
                metadata = {
                    k: v for k, v in row_data.items() if k not in ("code", "name", "description")
                }

                values.append(
                    CodeValue(
                        code=code,
                        name=name,
                        description=description,
                        metadata=metadata,
                    )
                )

    code_list = CodeList(
        id=code_list_id,
        short_name=short_name,
        long_name=long_name,
        version=version,
        canonical_uri=canonical_uri,
        agency_name=agency_name,
        agency_id=agency_id,
        columns=columns,
        values=values,
    )

    return code_list


def _get_text(parent: etree._Element | None, tag: str) -> str:
    """Get text content of a child element."""
    if parent is None:
        return ""

    # Try without namespace first
    elem = parent.find(tag, namespaces=None)
    if elem is None:
        # Try with Genericode namespace
        elem = parent.find("{%s}%s" % (GC_NS, tag))

    if elem is not None and elem.text:
        return elem.text.strip()
    return ""


def parse_all_code_lists(code_list_path: Path) -> dict[str, CodeList]:
    """
    Parse all code list files in a directory.

    Args:
        code_list_path: Path to directory containing .gc files

    Returns:
        Dictionary mapping code list IDs to CodeList objects
    """
    result: dict[str, CodeList] = {}

    for gc_file in code_list_path.glob("*.gc"):
        try:
            code_list = parse_genericode(gc_file)
            result[code_list.id] = code_list
        except Exception:
            # Skip malformed files
            continue

    return result
