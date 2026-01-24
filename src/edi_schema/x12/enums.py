"""
X12 005010 Schema Enumerations

This module defines enumerations for X12 EDI standard codes used in the
005010 version schema files. These enums provide type-safe representations
of the various code values found in the X12 data files.

Reference: ASC X12 005010 Batch Standards (readme.txt)
"""

from enum import Enum


class DataElementType(str, Enum):
    """
    Data Element Types as defined in eledetl.txt

    These codes indicate the format and validation rules for data elements.
    """

    AN = "AN"  # Alphanumeric - any character from the basic or extended character set
    ID = "ID"  # Identifier - alphanumeric with code list values
    N = "N"  # Numeric - numeric with implied decimal (no decimal point transmitted)
    N0 = "N0"  # Numeric - numeric with 0 implied decimal places (integer)
    N1 = "N1"  # Numeric - numeric with 1 implied decimal place
    N2 = "N2"  # Numeric - numeric with 2 implied decimal places
    N3 = "N3"  # Numeric - numeric with 3 implied decimal places
    N4 = "N4"  # Numeric - numeric with 4 implied decimal places
    N5 = "N5"  # Numeric - numeric with 5 implied decimal places
    N6 = "N6"  # Numeric - numeric with 6 implied decimal places
    N7 = "N7"  # Numeric - numeric with 7 implied decimal places
    N8 = "N8"  # Numeric - numeric with 8 implied decimal places
    N9 = "N9"  # Numeric - numeric with 9 implied decimal places
    R = "R"  # Decimal - numeric with explicit decimal point
    DT = "DT"  # Date - CCYYMMDD format
    TM = "TM"  # Time - HHMM, HHMMSS, HHMMSSD, or HHMMSSDD format
    B = "B"  # Binary - binary data

    @property
    def description(self) -> str:
        """Return a human-readable description of the data type."""
        descriptions = {
            "AN": "Alphanumeric string",
            "ID": "Identifier (code list value)",
            "N": "Numeric with implied decimal",
            "N0": "Integer (no decimal places)",
            "N1": "Numeric with 1 implied decimal place",
            "N2": "Numeric with 2 implied decimal places",
            "N3": "Numeric with 3 implied decimal places",
            "N4": "Numeric with 4 implied decimal places",
            "N5": "Numeric with 5 implied decimal places",
            "N6": "Numeric with 6 implied decimal places",
            "N7": "Numeric with 7 implied decimal places",
            "N8": "Numeric with 8 implied decimal places",
            "N9": "Numeric with 9 implied decimal places",
            "R": "Decimal (explicit decimal point)",
            "DT": "Date (CCYYMMDD)",
            "TM": "Time (HHMM or HHMMSS)",
            "B": "Binary data",
        }
        return descriptions.get(self.value, "Unknown")

    @property
    def is_numeric(self) -> bool:
        """Check if this type represents numeric data."""
        return self.value in ("N", "N0", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "R")

    @property
    def is_datetime(self) -> bool:
        """Check if this type represents date or time data."""
        return self.value in ("DT", "TM")


class RequirementDesignator(str, Enum):
    """
    Requirement Designators for segment and element usage.

    These codes indicate whether a segment or element is required,
    optional, or conditional in a given context.

    Note: In paper documentation, 'C' changed to 'X' in Version 003020,
    but the data files continue to use 'C' for backward compatibility.
    """

    M = "M"  # Mandatory - must be present
    O = "O"  # Optional - may be present
    C = "C"  # Conditional - dependent on other elements/segments
    X = "X"  # Conditional (alternate representation used in documentation)

    @property
    def description(self) -> str:
        """Return a human-readable description of the requirement."""
        descriptions = {
            "M": "Mandatory",
            "O": "Optional",
            "C": "Conditional",
            "X": "Conditional (documentation format)",
        }
        return descriptions.get(self.value, "Unknown")

    @property
    def is_required(self) -> bool:
        """Check if this designator indicates a required element."""
        return self.value == "M"

    @property
    def is_conditional(self) -> bool:
        """Check if this designator indicates a conditional element."""
        return self.value in ("C", "X")


class TransactionSetArea(str, Enum):
    """
    Transaction Set Area designators.

    Transaction sets are divided into areas (also known as tables)
    that organize the segments into logical groups.
    """

    HEADING = "1"  # Table 1 - Heading area
    DETAIL = "2"  # Table 2 - Detail area
    SUMMARY = "3"  # Table 3 - Summary area

    @property
    def description(self) -> str:
        """Return a human-readable description of the area."""
        descriptions = {
            "1": "Heading Area (Table 1)",
            "2": "Detail Area (Table 2)",
            "3": "Summary Area (Table 3)",
        }
        return descriptions.get(self.value, "Unknown")


class FreeformTextType(str, Enum):
    """
    Freeform text types as defined in freeform.txt

    These tags identify the type of free-form textual data in the FREEFORM.TXT file.
    """

    SETPUR = "SETPUR"  # Transaction Set Purpose/Scope
    SETNTE = "SETNTE"  # Transaction Set Notes/Comments
    SEGPUR = "SEGPUR"  # Segment Purpose
    SEGNTE = "SEGNTE"  # Segment Notes/Comments
    COMPUR = "COMPUR"  # Composite Data Element Purpose
    COMNTE = "COMNTE"  # Composite Data Element Notes/Comments
    ELEDEF = "ELEDEF"  # Simple Data Element Definitions
    ELECOD = "ELECOD"  # Simple Data Element Code Definitions
    ELENTE = "ELENTE"  # Simple Data Element Code Explanations
    CSSRCE = "CSSRCE"  # Source of Referenced Code List
    CSFROM = "CSFROM"  # Available From Address for Code Source Maintainer
    CSINET = "CSINET"  # Internet Address of Code Source Maintainer
    CSABST = "CSABST"  # Abstract for Code List
    CSNOTE = "CSNOTE"  # Code Source Notes

    @property
    def description(self) -> str:
        """Return a human-readable description of the text type."""
        descriptions = {
            "SETPUR": "Transaction Set Purpose/Scope",
            "SETNTE": "Transaction Set Notes/Comments",
            "SEGPUR": "Segment Purpose",
            "SEGNTE": "Segment Notes/Comments",
            "COMPUR": "Composite Data Element Purpose",
            "COMNTE": "Composite Data Element Notes/Comments",
            "ELEDEF": "Simple Data Element Definitions",
            "ELECOD": "Simple Data Element Code Definitions",
            "ELENTE": "Simple Data Element Code Explanations",
            "CSSRCE": "Source of Referenced Code List",
            "CSFROM": "Available From Address for Code Source Maintainer",
            "CSINET": "Internet Address of Code Source Maintainer",
            "CSABST": "Abstract for Code List",
            "CSNOTE": "Code Source Notes",
        }
        return descriptions.get(self.value, "Unknown")


class NoteType(str, Enum):
    """
    Note Type codes for segment and composite notes.

    These indicate the type of note associated with a segment or composite element.
    """

    N = "N"  # Syntax Note (codified per X12.6-1989)
    S = "S"  # Semantic Note
    C = "C"  # Comment

    @property
    def description(self) -> str:
        """Return a human-readable description of the note type."""
        descriptions = {
            "N": "Syntax Note",
            "S": "Semantic Note",
            "C": "Comment",
        }
        return descriptions.get(self.value, "Unknown")


class UsageIndicator(str, Enum):
    """
    Usage Indicator for interchange headers (ISA15).

    Indicates whether the interchange is for production or test purposes.
    """

    P = "P"  # Production data
    T = "T"  # Test data
    I = "I"  # Information (replays)

    @property
    def description(self) -> str:
        """Return a human-readable description of the usage."""
        descriptions = {
            "P": "Production",
            "T": "Test",
            "I": "Information",
        }
        return descriptions.get(self.value, "Unknown")


class AcknowledgmentRequested(str, Enum):
    """
    Acknowledgment Requested codes (ISA14).

    Indicates whether an acknowledgment (TA1) is requested.
    """

    NO_ACK = "0"  # No interchange acknowledgment requested
    ACK = "1"  # Interchange acknowledgment requested (TA1)

    @property
    def description(self) -> str:
        """Return a human-readable description."""
        descriptions = {
            "0": "No Interchange Acknowledgment Requested",
            "1": "Interchange Acknowledgment Requested (TA1)",
        }
        return descriptions.get(self.value, "Unknown")


class RepetitionIndicator(str, Enum):
    """
    Repetition indicator values for maximum use in transaction set details.

    Indicates how many times a segment or loop can repeat.
    """

    ONCE = "1"  # Appears exactly once
    UNLIMITED = ">1"  # Unlimited repetition (represented as ">1" in data)

    @classmethod
    def from_value(cls, value: str) -> "RepetitionIndicator | int":
        """
        Parse a repetition value from the data files.

        Args:
            value: The raw value from the data file

        Returns:
            RepetitionIndicator enum for special cases, or int for numeric values
        """
        if value == ">1":
            return cls.UNLIMITED
        try:
            return int(value)
        except ValueError:
            return cls.ONCE


class HierarchicalChildCode(str, Enum):
    """
    Hierarchical Child Code (HL03) values.

    Indicates whether the hierarchical level has subordinate levels.
    """

    NO_CHILD = "0"  # No subordinate HL segment
    HAS_CHILD = "1"  # Additional subordinate HL data segment follows

    @property
    def description(self) -> str:
        """Return a human-readable description."""
        descriptions = {
            "0": "No subordinate HL segment in this hierarchical structure",
            "1": "Additional subordinate HL data segment in this hierarchical structure",
        }
        return descriptions.get(self.value, "Unknown")


# Mapping of common functional group codes (from sethead.txt)
FUNCTIONAL_GROUP_CODES = {
    "AA": "Account Analysis",
    "AB": "Logistics Service Request",
    "AC": "Associated Data",
    "AD": "Individual Life, Annuity and Disability Application",
    "AE": "Premium Audit Request and Return",
    "AF": "Application for Admission to Educational Institutions",
    "AG": "Application Advice",
    "AH": "Logistics Service Response",
    "AI": "Automotive Inspection Detail",
    "AK": "Acknowledgment",
    "AL": "Set Cancellation",
    "AM": "Item Information Request",
    "AN": "Return Merchandise Authorization",
    "AO": "Income or Asset Offset",
    "AQ": "Customs Manifest",
    "AR": "Warehouse Stock Transfer Shipment Advice",
    "AS": "Transportation Appointment Schedule",
    "AT": "Animal Toxicological Data",
    "AU": "Customs Status Information",
    "AV": "Customs Carrier General Order Status",
    "AW": "Warehouse Inventory Adjustment Advice",
    "AX": "Customs Events Advisory Details",
    "AY": "Customs Automated Manifest Archive Status",
    "AZ": "Customs Acceptance/Rejection",
    "BA": "Customs Permit to Transfer Request",
    "BB": "Customs In-Bond Information",
    "BC": "Business Credit Report",
    "BD": "Customs Consist Information",
    "BE": "Benefit Enrollment and Maintenance",
    "BF": "Business Entity Filings",
    "BL": "Motor Carrier Bill of Lading",
    "BS": "Shipment and Billing Notice",
    "CA": "Purchase Order Change Acknowledgment",
    "CB": "Unemployment Insurance Tax Claim",
    "CD": "Credit/Debit Adjustment",
    "CE": "Cartage Work Assignment",
    "CF": "Product Transfer Account Adjustment",
    "CH": "Car Handling Information",
    "CI": "Consolidated Service Invoice",
    "CJ": "Manufacturer Coupon Family Code",
    "CK": "Canadian Grain Information",
    "CL": "Election Campaign and Lobbyist Reporting",
    "CM": "Component Parts Content",
    "CN": "Coupon Notification",
    "CO": "Cooperative Advertising Agreements",
    "CP": "Pricing Support",
    "CQ": "Commodity Movement Services Response",
    "CR": "Rail Carhire Settlements",
    "CS": "Cryptographic Service Message",
    "CT": "Application Control Totals",
    "CU": "Commodity Movement Services",
    "CV": "Commercial Vehicle Safety",
    "CW": "Educational Institution Record",
    "D3": "Contract Completion Status",
    "D4": "Contract Abstract",
    "D5": "Contract Payment Management Report",
    "DA": "Debit Authorization",
    "DD": "Shipment Delivery Discrepancy",
    "DF": "Market Development Fund Allocation",
    "DI": "Dealer Information",
    "DM": "Equipment Order",
    "DS": "Data Status Tracking",
    "DX": "Direct Store Delivery",
    "EC": "Educational Course Inventory",
    "ED": "Student Educational Record",
    "EI": "Railroad Equipment Inquiry",
    "EN": "Equipment Inspection Report",
    "EP": "Environmental Compliance Reporting",
    "ER": "Revenue Receipts Statement",
    "ES": "Notice of Employment Status",
    "EV": "Railroad Event Report",
    "EX": "Excavation Communication",
    "FA": "Functional Acknowledgment",
    "FB": "Freight Invoice",
    "FC": "Court and Law Enforcement",
    "FG": "Motor Carrier Loading and Route Guide",
    "FR": "Financial Information Reporting",
    "FT": "File Transfer",
    "GC": "Loss or Damage Claim",
    "GE": "General Request/Response",
    "GF": "Response to a Load Tender",
    "GL": "Intermodal Group Loading Plan",
    "GP": "Grocery Products Invoice",
    "GR": "Statistical Government Information",
    "GT": "Grant or Assistance Application",
    "HB": "Eligibility, Coverage or Benefit Information",
    "HC": "Health Care Claim",
    "HI": "Health Care Services Review",
    "HN": "Health Care Information Status",
    "HP": "Health Care Claim Payment",
    "HR": "Health Care Claim Status Request",
    "HS": "Eligibility Inquiry",
    "HU": "Human Resource Information",
    "HV": "Health Care Benefit Coordination",
    "IA": "Air Freight Details",
    "IB": "Inventory Inquiry/Advice",
    "IC": "Rail Advance Interchange Consist",
    "ID": "Insurance/Annuity Application Status",
    "IE": "Insurance Producer Administration",
    "IF": "Individual Insurance Policy",
    "IG": "Direct Store Delivery Summary",
    "IH": "Commercial Vehicle Safety Reports",
    "IJ": "Report of Injury",
    "IM": "Motor Carrier Freight Details",
    "IN": "Invoice",
    "IO": "Ocean Freight Details",
    "IR": "Rail Carrier Freight Details",
    "IS": "Estimated Time of Arrival",
    "JB": "Joint Interest Billing",
    "KM": "Commercial Vehicle Credentials",
    "LA": "FCC License Application",
    "LB": "Lockbox",
    "LI": "Locomotive Information",
    "LN": "Property and Casualty Loss",
    "LR": "Logistics Reassignment",
    "LS": "Asset Schedule",
    "LT": "Student Loan Transfer",
    "MA": "Motor Carrier Summary Freight",
    "MC": "Request for Motor Carrier Rate",
    "MD": "Material Due-In and Receipt",
    "ME": "Mortgage Related",
    "MF": "Market Development Fund Settlement",
    "MG": "Secondary Mortgage Market",
    "MH": "Motor Carrier Rate Proposal",
    "MI": "Motor Carrier Shipment Status Inquiry",
    "MJ": "Secondary Mortgage Market Loan",
    "MK": "Response to Motor Carrier Rate",
    "MM": "Medical Event Reporting",
    "MN": "Mortgage Note",
    "MO": "Maintenance Service Order",
    "MP": "Motion Picture Booking",
    "MQ": "Consolidators Freight Bill",
    "MR": "Multilevel Railcar Load",
    "MS": "Material Safety Data Sheet",
    "MT": "Electronic Form Structure",
    "MV": "Material Obligation Validation",
    "MX": "Material Claim",
    "MY": "Response to Cartage Work Assignment",
    "MZ": "Motor Carrier Package Status",
    "NC": "Nonconformance Report",
    "NL": "Name and Address Lists",
    "NP": "Notice of Power of Attorney",
    "NR": "Secured Receipt",
    "NT": "Notice of Tax Adjustment",
    "OC": "Cargo Insurance",
    "OG": "Grocery Products Purchase Order",
    "OR": "Organizational Relationships",
    "OW": "Warehouse Shipping Order",
    "PA": "Price Authorization",
    "PB": "Railroad Parameter Trace",
    "PC": "Purchase Order Change",
    "PD": "Product Activity Data",
    "PE": "Periodic Compensation",
    "PF": "Annuity Activity",
    "PG": "Insurance Plan Description",
    "PH": "Pricing History",
    "PI": "Patient Information",
    "PJ": "Project Schedule Reporting",
    "PK": "Contractor Cost Data",
    "PL": "Railroad Problem Log",
    "PN": "Product Source Information",
    "PO": "Purchase Order",
    "PQ": "Property Damage Report",
    "PR": "Purchase Order Acknowledgment",
    "PS": "Planning Schedule",
    "PT": "Product Transfer and Resale",
    "PU": "Motor Carrier Shipment Pickup",
    "PV": "Purchase Order Shipment Management",
    "PW": "Healthcare Provider Information",
    "PY": "Payment Cancellation Request",
    "QG": "Product Information",
    "QM": "Transportation Carrier Shipment Status",
    "QO": "Ocean Shipment Status",
    "RA": "Payment Order/Remittance Advice",
    "RB": "Railroad Clearance",
    "RC": "Receiving Advice",
    "RD": "Royalty Regulatory Report",
    "RE": "Warehouse Stock Transfer Receipt",
    "RF": "Request for Routing Instructions",
    "RG": "Routing Instructions",
    "RH": "Railroad Reciprocal Switch File",
    "RI": "Routing and Carrier Instruction",
    "RJ": "Railroad Mark Register",
    "RK": "Standard Transportation Commodity Code",
    "RL": "Rail Industrial Switch List",
    "RM": "Railroad Station Master File",
    "RN": "Requisition",
    "RO": "Ocean Booking",
    "RP": "Commission Sales Report",
    "RQ": "Request for Quotation",
    "RR": "Response to Request for Quotation",
    "RS": "Order Status",
    "RT": "Report of Test Results",
    "RU": "Railroad Retirement Activity",
    "RV": "Railroad Junctions",
    "RW": "Rail Revenue Waybill",
    "RX": "Rail Deprescription",
    "RY": "Request for Student Educational Record",
    "RZ": "Response to Student Educational Record Request",
    "SA": "Air Shipment Information",
    "SB": "Rail Carrier Services Settlement",
    "SC": "Price/Sales Catalog",
    "SD": "Student Loan Pre-Claims",
    "SE": "U.S. Customs Export Shipment",
    "SH": "Ship Notice/Manifest",
    "SI": "Shipment Information",
    "SJ": "Transportation Automatic Equipment",
    "SL": "Student Loan",
    "SM": "Motor Carrier Load Tender",
    "SN": "Rail Route File Maintenance",
    "SO": "Ocean Shipment Information",
    "SP": "Specifications/Technical Information",
    "SQ": "Production Sequence",
    "SR": "Rail Carrier Shipment",
    "SS": "Shipping Schedule",
    "ST": "Railroad Service Commitment",
    "SU": "Account Assignment/Inquiry",
    "SV": "Student Enrollment Verification",
    "SW": "Warehouse Shipping Advice",
    "TA": "Electronic Filing of Tax Return",
    "TB": "Trailer or Container Repair Billing",
    "TD": "Trading Partner Profile",
    "TE": "Tax Exemption Certification",
    "TF": "Electronic Filing of Tax Return Data",
    "TI": "Tax Information Exchange",
    "TJ": "Tax Jurisdiction Sourcing",
    "TM": "Motor Carrier Delivery Trailer Manifest",
    "TN": "Tax Rate Notification",
    "TO": "Real Estate Title",
    "TP": "Rail Rate/Pricing",
    "TR": "Train Sheet",
    "TS": "Transportation Services Tender",
    "TT": "Educational Testing",
    "TU": "Trailer Usage Report",
    "TX": "Text Message",
    "UA": "Retail Account Characteristics",
    "UB": "Customer Call Reporting",
    "UC": "Secured Interest Filing",
    "UD": "Deduction Research Report",
    "UI": "Underwriting Information Services",
    "UP": "Motor Carrier Pickup Manifest",
    "UW": "Insurance Underwriting Requirements",
    "VA": "Vehicle Application Advice",
    "VB": "Vehicle Baying Order",
    "VC": "Vehicle Shipping Order",
    "VD": "Vehicle Damage",
    "VE": "Vessel Content Details",
    "VH": "Vehicle Carrier Rate Update",
    "VI": "Voter Registration Information",
    "VS": "Vehicle Service",
    "WA": "Product Service Related",
    "WB": "Rail Carrier Waybill Interchange",
    "WG": "Vendor Performance Review",
    "WI": "Wage Determination",
    "WL": "Well Information",
    "WR": "Shipment Weights",
    "WT": "Rail Waybill Request",
}
