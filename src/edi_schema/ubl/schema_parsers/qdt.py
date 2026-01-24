"""
QDT (Qualified Data Types) Parser.

Parses UBL-QualifiedDataTypes-2.5.xsd to extract constrained data types.
"""

from pathlib import Path

from ..models import QualifiedDataType
from .base import (
    get_complex_types,
    get_restriction_base,
    parse_type_reference,
    parse_xsd,
)


def parse_qdt(path: Path) -> dict[str, QualifiedDataType]:
    """
    Parse the QualifiedDataTypes XSD file.

    Args:
        path: Path to UBL-QualifiedDataTypes-2.5.xsd

    Returns:
        Dictionary mapping type names to QualifiedDataType objects
    """
    root = parse_xsd(path)
    result: dict[str, QualifiedDataType] = {}

    for complex_type in get_complex_types(root):
        type_name = complex_type.get("name", "")
        if not type_name or not type_name.endswith("Type"):
            continue

        # Extract name without 'Type' suffix
        name = type_name[:-4]

        # Get base type from restriction
        base_ref = get_restriction_base(complex_type)
        if base_ref:
            _, base_local = parse_type_reference(base_ref)
            # Remove 'Type' suffix from base
            if base_local.endswith("Type"):
                base_type = base_local[:-4]
            else:
                base_type = base_local
        else:
            base_type = "Code"  # Default for QDT

        # Map type name to code list (convention: remove 'Type' and match to code list)
        # e.g., CurrencyCodeType -> CurrencyCode -> CurrencyCode-2.4.gc
        code_list_id = _get_code_list_id(name)

        qdt = QualifiedDataType(
            name=name,
            base_type=base_type,
            code_list_id=code_list_id,
        )
        result[name] = qdt

    return result


def _get_code_list_id(name: str) -> str | None:
    """
    Map a QDT name to its associated code list ID.

    Args:
        name: QDT name (e.g., 'CurrencyCode')

    Returns:
        Code list ID if known (e.g., 'CurrencyCode-2.4'), else None
    """
    # Known mappings from QDT names to code list files
    code_list_map = {
        "AllowanceChargeReasonCode": "AllowanceChargeReasonCode-2.4",
        "ChannelCode": "ChannelCode-2.4",
        "CountryIdentificationCode": "CountryIdentificationCode-2.4",
        "CurrencyCode": "CurrencyCode-2.4",
        "LanguageCode": "LanguageCode-2.4",
        "PackagingTypeCode": "PackagingTypeCode-2.4",
        "PaymentMeansCode": "PaymentMeansCode-2.4",
        "TransportEquipmentTypeCode": "TransportEquipmentTypeCode-2.4",
        "TransportModeCode": "TransportModeCode-2.4",
        "UnitOfMeasureCode": "UnitOfMeasureCode-2.4",
    }
    return code_list_map.get(name)
