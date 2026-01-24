"""
Tests verifying X12 schema file accessibility and basic format.
"""

from pathlib import Path


class TestX12SchemaPath:
    """Tests verifying X12 schema file accessibility."""

    def test_sethead_exists(self, x12_schema_path: Path):
        """Verify sethead.txt exists."""
        assert (x12_schema_path / "sethead.txt").exists()

    def test_setdetl_exists(self, x12_schema_path: Path):
        """Verify setdetl.txt exists."""
        assert (x12_schema_path / "setdetl.txt").exists()

    def test_seghead_exists(self, x12_schema_path: Path):
        """Verify seghead.txt exists."""
        assert (x12_schema_path / "seghead.txt").exists()

    def test_segdetl_exists(self, x12_schema_path: Path):
        """Verify segdetl.txt exists."""
        assert (x12_schema_path / "segdetl.txt").exists()

    def test_comhead_exists(self, x12_schema_path: Path):
        """Verify comhead.txt exists."""
        assert (x12_schema_path / "comhead.txt").exists()

    def test_comdetl_exists(self, x12_schema_path: Path):
        """Verify comdetl.txt exists."""
        assert (x12_schema_path / "comdetl.txt").exists()

    def test_elehead_exists(self, x12_schema_path: Path):
        """Verify elehead.txt exists."""
        assert (x12_schema_path / "elehead.txt").exists()

    def test_eledetl_exists(self, x12_schema_path: Path):
        """Verify eledetl.txt exists."""
        assert (x12_schema_path / "eledetl.txt").exists()

    def test_freeform_exists(self, x12_schema_path: Path):
        """Verify freeform.txt exists."""
        assert (x12_schema_path / "freeform.txt").exists()

    def test_cshead_exists(self, x12_schema_path: Path):
        """Verify cshead.txt exists."""
        assert (x12_schema_path / "cshead.txt").exists()


class TestX12FileFormat:
    """Tests verifying X12 schema file format."""

    def test_sethead_is_csv_format(self, x12_sethead_path: Path):
        """Verify sethead.txt is quote-comma delimited."""
        content = x12_sethead_path.read_text()
        first_line = content.split("\n")[0]
        # Should be like: "810","Invoice","IN"
        assert first_line.startswith('"')
        assert '","' in first_line
        assert first_line.endswith('"')

    def test_sethead_has_three_fields(self, x12_sethead_path: Path):
        """Verify sethead.txt has expected field count."""
        content = x12_sethead_path.read_text()
        first_line = content.split("\n")[0]
        # Remove quotes and split
        fields = first_line.strip('"').split('","')
        assert len(fields) == 3, f"Expected 3 fields, got {len(fields)}: {fields}"

    def test_seghead_has_two_fields(self, x12_seghead_path: Path):
        """Verify seghead.txt has segment ID and name."""
        content = x12_seghead_path.read_text()
        first_line = content.split("\n")[0]
        fields = first_line.strip('"').split('","')
        assert len(fields) == 2, f"Expected 2 fields, got {len(fields)}: {fields}"

    def test_elehead_has_two_fields(self, x12_elehead_path: Path):
        """Verify elehead.txt has element ID and name."""
        content = x12_elehead_path.read_text()
        first_line = content.split("\n")[0]
        fields = first_line.strip('"').split('","')
        assert len(fields) == 2, f"Expected 2 fields, got {len(fields)}: {fields}"

    def test_freeform_has_tagged_sections(self, x12_freeform_path: Path):
        """Verify freeform.txt has expected tag sections."""
        # freeform.txt uses Windows-1252 encoding (contains special characters)
        content = x12_freeform_path.read_text(encoding="cp1252")
        # Should contain various tag types
        expected_tags = ["SETPUR", "SEGPUR", "ELEDEF", "ELECOD"]
        for tag in expected_tags:
            assert tag in content, f"Expected tag {tag} not found in freeform.txt"


class TestX12TransactionSets:
    """Tests verifying known transaction sets exist."""

    def test_850_purchase_order_exists(self, x12_sethead_path: Path):
        """Verify 850 Purchase Order is defined."""
        content = x12_sethead_path.read_text()
        assert '"850"' in content

    def test_810_invoice_exists(self, x12_sethead_path: Path):
        """Verify 810 Invoice is defined."""
        content = x12_sethead_path.read_text()
        assert '"810"' in content

    def test_856_asn_exists(self, x12_sethead_path: Path):
        """Verify 856 Ship Notice/Manifest is defined."""
        content = x12_sethead_path.read_text()
        assert '"856"' in content

    def test_997_fa_exists(self, x12_sethead_path: Path):
        """Verify 997 Functional Acknowledgment is defined."""
        content = x12_sethead_path.read_text()
        assert '"997"' in content

    def test_837_healthcare_claim_exists(self, x12_sethead_path: Path):
        """Verify 837 Healthcare Claim is defined."""
        content = x12_sethead_path.read_text()
        assert '"837"' in content
