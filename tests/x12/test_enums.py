"""
Tests for X12 enumerations.
"""

from edi_schema.x12.enums import (
    FUNCTIONAL_GROUP_CODES,
    AcknowledgmentRequested,
    DataElementType,
    FreeformTextType,
    HierarchicalChildCode,
    NoteType,
    RepetitionIndicator,
    RequirementDesignator,
    TransactionSetArea,
    UsageIndicator,
)


class TestDataElementType:
    """Tests for DataElementType enum."""

    def test_alphanumeric(self):
        assert DataElementType.AN.value == "AN"
        assert DataElementType.AN.description == "Alphanumeric string"

    def test_identifier(self):
        assert DataElementType.ID.value == "ID"
        assert DataElementType.ID.description == "Identifier (code list value)"

    def test_numeric_types(self):
        assert DataElementType.N0.value == "N0"
        assert DataElementType.N2.value == "N2"
        assert DataElementType.N2.description == "Numeric with 2 implied decimal places"

    def test_decimal(self):
        assert DataElementType.R.value == "R"
        assert DataElementType.R.description == "Decimal (explicit decimal point)"

    def test_date_time(self):
        assert DataElementType.DT.value == "DT"
        assert DataElementType.TM.value == "TM"

    def test_is_numeric(self):
        assert DataElementType.N0.is_numeric is True
        assert DataElementType.N2.is_numeric is True
        assert DataElementType.R.is_numeric is True
        assert DataElementType.AN.is_numeric is False
        assert DataElementType.ID.is_numeric is False

    def test_is_datetime(self):
        assert DataElementType.DT.is_datetime is True
        assert DataElementType.TM.is_datetime is True
        assert DataElementType.AN.is_datetime is False
        assert DataElementType.N2.is_datetime is False


class TestRequirementDesignator:
    """Tests for RequirementDesignator enum."""

    def test_mandatory(self):
        assert RequirementDesignator.M.value == "M"
        assert RequirementDesignator.M.description == "Mandatory"
        assert RequirementDesignator.M.is_required is True
        assert RequirementDesignator.M.is_conditional is False

    def test_optional(self):
        assert RequirementDesignator.O.value == "O"
        assert RequirementDesignator.O.description == "Optional"
        assert RequirementDesignator.O.is_required is False
        assert RequirementDesignator.O.is_conditional is False

    def test_conditional(self):
        assert RequirementDesignator.C.value == "C"
        assert RequirementDesignator.C.description == "Conditional"
        assert RequirementDesignator.C.is_required is False
        assert RequirementDesignator.C.is_conditional is True

    def test_conditional_x(self):
        """X is alternate representation of conditional in documentation."""
        assert RequirementDesignator.X.value == "X"
        assert RequirementDesignator.X.is_conditional is True


class TestTransactionSetArea:
    """Tests for TransactionSetArea enum."""

    def test_heading(self):
        assert TransactionSetArea.HEADING.value == "1"
        assert "Heading" in TransactionSetArea.HEADING.description

    def test_detail(self):
        assert TransactionSetArea.DETAIL.value == "2"
        assert "Detail" in TransactionSetArea.DETAIL.description

    def test_summary(self):
        assert TransactionSetArea.SUMMARY.value == "3"
        assert "Summary" in TransactionSetArea.SUMMARY.description


class TestFreeformTextType:
    """Tests for FreeformTextType enum."""

    def test_transaction_set_types(self):
        assert FreeformTextType.SETPUR.value == "SETPUR"
        assert FreeformTextType.SETNTE.value == "SETNTE"

    def test_segment_types(self):
        assert FreeformTextType.SEGPUR.value == "SEGPUR"
        assert FreeformTextType.SEGNTE.value == "SEGNTE"

    def test_element_types(self):
        assert FreeformTextType.ELEDEF.value == "ELEDEF"
        assert FreeformTextType.ELECOD.value == "ELECOD"

    def test_code_source_types(self):
        assert FreeformTextType.CSSRCE.value == "CSSRCE"
        assert FreeformTextType.CSINET.value == "CSINET"


class TestNoteType:
    """Tests for NoteType enum."""

    def test_syntax_note(self):
        assert NoteType.N.value == "N"
        assert NoteType.N.description == "Syntax Note"

    def test_semantic_note(self):
        assert NoteType.S.value == "S"
        assert NoteType.S.description == "Semantic Note"

    def test_comment(self):
        assert NoteType.C.value == "C"
        assert NoteType.C.description == "Comment"


class TestUsageIndicator:
    """Tests for UsageIndicator enum."""

    def test_production(self):
        assert UsageIndicator.P.value == "P"
        assert UsageIndicator.P.description == "Production"

    def test_test(self):
        assert UsageIndicator.T.value == "T"
        assert UsageIndicator.T.description == "Test"

    def test_information(self):
        assert UsageIndicator.I.value == "I"
        assert UsageIndicator.I.description == "Information"


class TestAcknowledgmentRequested:
    """Tests for AcknowledgmentRequested enum."""

    def test_no_ack(self):
        assert AcknowledgmentRequested.NO_ACK.value == "0"

    def test_ack_requested(self):
        assert AcknowledgmentRequested.ACK.value == "1"


class TestRepetitionIndicator:
    """Tests for RepetitionIndicator enum."""

    def test_once(self):
        assert RepetitionIndicator.ONCE.value == "1"

    def test_unlimited(self):
        assert RepetitionIndicator.UNLIMITED.value == ">1"

    def test_from_value_unlimited(self):
        result = RepetitionIndicator.from_value(">1")
        assert result == RepetitionIndicator.UNLIMITED

    def test_from_value_numeric(self):
        result = RepetitionIndicator.from_value("5")
        assert result == 5

    def test_from_value_invalid(self):
        result = RepetitionIndicator.from_value("invalid")
        assert result == RepetitionIndicator.ONCE


class TestHierarchicalChildCode:
    """Tests for HierarchicalChildCode enum."""

    def test_no_child(self):
        assert HierarchicalChildCode.NO_CHILD.value == "0"

    def test_has_child(self):
        assert HierarchicalChildCode.HAS_CHILD.value == "1"


class TestFunctionalGroupCodes:
    """Tests for FUNCTIONAL_GROUP_CODES dictionary."""

    def test_invoice(self):
        assert FUNCTIONAL_GROUP_CODES["IN"] == "Invoice"

    def test_purchase_order(self):
        assert FUNCTIONAL_GROUP_CODES["PO"] == "Purchase Order"

    def test_ship_notice(self):
        assert FUNCTIONAL_GROUP_CODES["SH"] == "Ship Notice/Manifest"

    def test_functional_acknowledgment(self):
        assert FUNCTIONAL_GROUP_CODES["FA"] == "Functional Acknowledgment"

    def test_healthcare_claim(self):
        assert FUNCTIONAL_GROUP_CODES["HC"] == "Health Care Claim"

    def test_code_count(self):
        """Verify we have a substantial number of functional group codes."""
        assert len(FUNCTIONAL_GROUP_CODES) > 200
