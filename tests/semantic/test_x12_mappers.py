"""
Tests for X12 Semantic Mappers.

Tests the mapping between X12 transaction sets and semantic models.
"""

from datetime import date
from decimal import Decimal

import pytest

from edi_schema.semantic.mappers.x12 import (
    X12DespatchAdviceMapper,
    X12InvoiceMapper,
    X12OrderMapper,
)
from edi_schema.semantic.mappers.x12.utils import (
    format_x12_amount,
    format_x12_date,
    format_x12_time,
    map_id_qualifier,
    map_n1_party_code,
    map_product_id_qualifier,
    parse_decimal,
    parse_x12_amount,
    parse_x12_date,
    parse_x12_time,
)
from edi_schema.semantic.models import (
    Address,
    Amount,
    CustomerParty,
    DespatchAdvice,
    DespatchLine,
    Identifier,
    Invoice,
    InvoiceLine,
    Item,
    ItemIdentification,
    MonetaryTotal,
    Order,
    OrderLine,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    Shipment,
    SupplierParty,
)
from edi_schema.x12.ast import (
    HLNode,
    LoopInstance,
    ParsedElement,
    ParsedSegment,
    RawElement,
    RawSegment,
    SourcePosition,
    TransactionSetInstance,
)

# =============================================================================
# Test Fixtures - Mock X12 AST Building Helpers
# =============================================================================


def make_position() -> SourcePosition:
    """Create a dummy source position."""
    return SourcePosition(offset=0, line=1, column=1)


def make_raw_element(value: str, index: int) -> RawElement:
    """Create a RawElement."""
    return RawElement(value=value, position=make_position(), element_index=index)


def make_raw_segment(tag: str, values: list[str]) -> RawSegment:
    """Create a RawSegment from tag and element values."""
    elements = [make_raw_element(v, i + 1) for i, v in enumerate(values)]
    return RawSegment(
        tag=tag,
        elements=elements,
        position=make_position(),
        raw_text=f"{tag}*{'*'.join(values)}~",
    )


def make_parsed_segment(tag: str, values: list[str]) -> ParsedSegment:
    """Create a ParsedSegment from tag and element values."""
    raw = make_raw_segment(tag, values)
    elements = [ParsedElement(value=v, raw=raw.elements[i]) for i, v in enumerate(values)]
    return ParsedSegment(tag=tag, elements=elements, raw=raw)


def make_loop(
    loop_id: str, segments: list[ParsedSegment], children: list[LoopInstance] = None
) -> LoopInstance:
    """Create a LoopInstance."""
    return LoopInstance(
        loop_id=loop_id,
        segments=segments,
        children=children or [],
    )


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestX12UtilityFunctions:
    """Test X12 utility functions."""

    def test_parse_x12_date_8char(self):
        """Test parsing CCYYMMDD format."""
        result = parse_x12_date("20241215")
        assert result == date(2024, 12, 15)

    def test_parse_x12_date_6char_2000s(self):
        """Test parsing YYMMDD format for 2000s."""
        result = parse_x12_date("241215")
        assert result == date(2024, 12, 15)

    def test_parse_x12_date_6char_1900s(self):
        """Test parsing YYMMDD format for 1900s."""
        result = parse_x12_date("991215")
        assert result == date(1999, 12, 15)

    def test_parse_x12_date_none(self):
        """Test parsing None returns None."""
        assert parse_x12_date(None) is None
        assert parse_x12_date("") is None

    def test_parse_x12_date_invalid(self):
        """Test parsing invalid date returns None."""
        assert parse_x12_date("invalid") is None
        assert parse_x12_date("20241315") is None  # Invalid month

    def test_parse_x12_time_4char(self):
        """Test parsing HHMM format."""
        from datetime import time

        result = parse_x12_time("1430")
        assert result == time(14, 30)

    def test_parse_x12_time_6char(self):
        """Test parsing HHMMSS format."""
        from datetime import time

        result = parse_x12_time("143025")
        assert result == time(14, 30, 25)

    def test_parse_x12_time_none(self):
        """Test parsing None returns None."""
        assert parse_x12_time(None) is None
        assert parse_x12_time("") is None

    def test_parse_x12_amount(self):
        """Test parsing amount with implied decimals."""
        # 12345 cents = $123.45
        result = parse_x12_amount("12345", implied_decimals=2)
        assert result == Decimal("123.45")

    def test_parse_x12_amount_no_decimals(self):
        """Test parsing amount without implied decimals."""
        result = parse_x12_amount("12345", implied_decimals=0)
        assert result == Decimal("12345")

    def test_parse_decimal(self):
        """Test parse_decimal."""
        assert parse_decimal("123.45") == Decimal("123.45")
        assert parse_decimal(None) is None
        assert parse_decimal("invalid") is None

    def test_format_x12_date(self):
        """Test formatting date to X12."""
        result = format_x12_date(date(2024, 12, 15))
        assert result == "20241215"

    def test_format_x12_date_none(self):
        """Test formatting None date."""
        assert format_x12_date(None) == ""

    def test_format_x12_time(self):
        """Test formatting time to X12."""
        from datetime import time

        result = format_x12_time(time(14, 30))
        assert result == "1430"

    def test_format_x12_amount(self):
        """Test formatting amount for X12."""
        result = format_x12_amount(Decimal("123.45"), implied_decimals=2)
        assert result == "12345"

    def test_map_n1_party_code(self):
        """Test N1 party code mapping."""
        assert map_n1_party_code("BY") == "buyer"
        assert map_n1_party_code("SE") == "seller"
        assert map_n1_party_code("ST") == "ship_to"
        assert map_n1_party_code("XX") == "XX"  # Unknown returns original

    def test_map_product_id_qualifier(self):
        """Test product ID qualifier mapping."""
        assert map_product_id_qualifier("UP") == ("standard", "UPC")
        assert map_product_id_qualifier("EN") == ("standard", "EAN")
        assert map_product_id_qualifier("VP") == ("sellers", None)
        assert map_product_id_qualifier("XX") == ("additional", None)

    def test_map_id_qualifier(self):
        """Test ID qualifier mapping."""
        assert map_id_qualifier("1") == "DUNS"
        assert map_id_qualifier("9") == "DUNS+4"
        assert map_id_qualifier("ZZ") == "MutuallyDefined"
        assert map_id_qualifier("XX") == "XX"


# =============================================================================
# X12 Order Mapper Tests
# =============================================================================


class TestX12OrderMapper:
    """Test X12 850 Purchase Order mapping."""

    @pytest.fixture
    def mapper(self):
        return X12OrderMapper()

    @pytest.fixture
    def simple_850_transaction(self) -> TransactionSetInstance:
        """Create a simple 850 transaction for testing."""
        # BEG segment
        beg = make_parsed_segment(
            "BEG",
            [
                "00",  # BEG01 - Purpose Code (00=Original)
                "SA",  # BEG02 - Order Type Code (SA=Stand-alone)
                "PO12345",  # BEG03 - PO Number
                "",  # BEG04 - Release Number
                "20241215",  # BEG05 - Date
            ],
        )

        # CUR segment (optional)
        cur = make_parsed_segment(
            "CUR",
            [
                "BY",  # CUR01 - Entity ID
                "USD",  # CUR02 - Currency Code
            ],
        )

        # N1 loop for Buyer
        n1_by = make_parsed_segment(
            "N1",
            [
                "BY",  # N1*01 - Entity ID Code
                "Acme Corp",  # N1*02 - Name
                "92",  # N1*03 - ID Qualifier (Buyer Assigned)
                "ACME001",  # N1*04 - ID Value
            ],
        )
        n3_by = make_parsed_segment(
            "N3",
            [
                "123 Main Street",  # N3*01 - Street
                "Suite 100",  # N3*02 - Additional
            ],
        )
        n4_by = make_parsed_segment(
            "N4",
            [
                "Chicago",  # N4*01 - City
                "IL",  # N4*02 - State
                "60601",  # N4*03 - Postal
                "US",  # N4*04 - Country
            ],
        )
        buyer_loop = make_loop("N1", [n1_by, n3_by, n4_by])

        # N1 loop for Seller
        n1_se = make_parsed_segment(
            "N1",
            [
                "SE",  # N1*01
                "Widget Supplier",  # N1*02
                "1",  # N1*03 - DUNS
                "123456789",  # N1*04
            ],
        )
        seller_loop = make_loop("N1", [n1_se])

        # PO1 loop - Line Item
        po1 = make_parsed_segment(
            "PO1",
            [
                "1",  # PO1*01 - Line Number
                "10",  # PO1*02 - Quantity
                "EA",  # PO1*03 - Unit
                "25.00",  # PO1*04 - Unit Price
                "",  # PO1*05 - Basis
                "UP",  # PO1*06 - Product ID Qualifier (UPC)
                "012345678901",  # PO1*07 - UPC
                "VP",  # PO1*08 - Vendor Part qualifier
                "WIDGET-001",  # PO1*09 - Vendor Part
            ],
        )
        pid = make_parsed_segment(
            "PID",
            [
                "F",  # PID*01 - Item Description Type
                "",  # PID*02
                "",  # PID*03
                "",  # PID*04
                "Industrial Widget",  # PID*05 - Description
            ],
        )
        line_loop = make_loop("PO1", [po1, pid])

        # CTT segment
        ctt = make_parsed_segment("CTT", ["1"])  # 1 line item

        # Build transaction
        return TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[beg, cur, buyer_loop, seller_loop, line_loop, ctt],
        )

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == Order
        assert mapper.source_format.value == "x12"
        assert mapper.transaction_id == "850"

    def test_to_semantic_basic(self, mapper, simple_850_transaction):
        """Test converting X12 850 to semantic Order."""
        order = mapper.to_semantic(simple_850_transaction)

        # Basic order info
        assert order.id == "PO12345"
        assert order.issue_date == date(2024, 12, 15)
        assert order.document_currency_code == "USD"
        assert order.order_type_code == "SA"
        assert order.document_purpose_code == "00"

        # Buyer
        assert order.buyer_customer_party is not None
        buyer = order.buyer_customer_party.party
        assert buyer.party_names[0].name == "Acme Corp"
        assert buyer.postal_address.city_name == "Chicago"
        assert buyer.postal_address.country_subentity == "IL"

        # Seller
        assert order.seller_supplier_party is not None
        seller = order.seller_supplier_party.party
        assert seller.party_names[0].name == "Widget Supplier"
        assert seller.party_identifications[0].id.scheme_id == "DUNS"

        # Line items
        assert len(order.order_lines) == 1
        line = order.order_lines[0]
        assert line.id == "1"
        assert line.quantity.value == Decimal("10")
        assert line.quantity.unit_code == "EA"
        assert line.price.price_amount.value == Decimal("25.00")
        assert line.item.description == "Industrial Widget"
        assert line.item.standard_item_identification.id.value == "012345678901"

        # Line count from CTT
        assert order.line_count == 1

    def test_to_semantic_wrong_transaction(self, mapper):
        """Test error when wrong transaction type."""
        txn = TransactionSetInstance(
            transaction_id="810",
            control_number="0001",
            content=[],
        )
        with pytest.raises(ValueError, match="Expected 850"):
            mapper.to_semantic(txn)

    def test_to_semantic_missing_beg(self, mapper):
        """Test error when BEG segment missing."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],  # No BEG segment
        )
        with pytest.raises(ValueError, match="Missing required BEG segment"):
            mapper.to_semantic(txn)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic Order to X12 segments."""
        order = Order(
            id="PO99999",
            issue_date=date(2024, 6, 15),
            document_currency_code="USD",
            order_type_code="NE",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Test Buyer")],
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="BUYER001", scheme_id="DUNS"))
                    ],
                    postal_address=Address(
                        street_name="456 Oak Ave",
                        city_name="Dallas",
                        country_subentity="TX",
                        postal_zone="75201",
                    ),
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    price=Price(price_amount=Amount(value=Decimal("100.00"), currency="USD")),
                    item=Item(
                        description="Test Product",
                        sellers_item_identification=ItemIdentification(
                            id=Identifier(value="SKU-123")
                        ),
                    ),
                )
            ],
        )

        segments = mapper.from_semantic(order)

        # Check BEG segment
        beg = next(s for s in segments if s["tag"] == "BEG")
        assert beg["elements"][2] == "PO99999"  # PO Number
        assert beg["elements"][4] == "20240615"  # Date

        # Check N1 segment for buyer
        n1_segments = [s for s in segments if s["tag"] == "N1"]
        assert len(n1_segments) >= 1
        buyer_n1 = n1_segments[0]
        assert buyer_n1["elements"][0] == "BY"
        assert buyer_n1["elements"][1] == "Test Buyer"

        # Check PO1 segment
        po1 = next(s for s in segments if s["tag"] == "PO1")
        assert po1["elements"][0] == "1"  # Line ID
        assert po1["elements"][1] == "5"  # Quantity
        assert po1["elements"][2] == "EA"  # Unit

        # Check CTT segment
        ctt = next(s for s in segments if s["tag"] == "CTT")
        assert ctt["elements"][0] == "1"  # 1 line item


# =============================================================================
# X12 Invoice Mapper Tests
# =============================================================================


class TestX12InvoiceMapper:
    """Test X12 810 Invoice mapping."""

    @pytest.fixture
    def mapper(self):
        return X12InvoiceMapper()

    @pytest.fixture
    def simple_810_transaction(self) -> TransactionSetInstance:
        """Create a simple 810 transaction for testing."""
        # BIG segment
        big = make_parsed_segment(
            "BIG",
            [
                "20241220",  # BIG01 - Invoice Date
                "INV-001",  # BIG02 - Invoice Number
                "20241215",  # BIG03 - PO Date
                "PO12345",  # BIG04 - PO Number
            ],
        )

        # CUR segment
        cur = make_parsed_segment("CUR", ["SE", "USD"])

        # N1 loop for Seller
        n1_se = make_parsed_segment(
            "N1",
            [
                "SE",
                "Widget Supplier",
                "1",
                "123456789",
            ],
        )
        seller_loop = make_loop("N1", [n1_se])

        # N1 loop for Buyer
        n1_by = make_parsed_segment(
            "N1",
            [
                "BY",
                "Acme Corp",
                "92",
                "ACME001",
            ],
        )
        buyer_loop = make_loop("N1", [n1_by])

        # IT1 loop - Line Item
        it1 = make_parsed_segment(
            "IT1",
            [
                "1",  # IT1*01 - Line Number
                "10",  # IT1*02 - Quantity Invoiced
                "EA",  # IT1*03 - Unit
                "25.00",  # IT1*04 - Unit Price
                "",  # IT1*05 - Basis
                "UP",  # IT1*06 - UPC qualifier
                "012345678901",  # IT1*07 - UPC
            ],
        )
        line_loop = make_loop("IT1", [it1])

        # TDS segment - Total amount
        tds = make_parsed_segment("TDS", ["25000"])  # $250.00 in cents

        # Build transaction
        return TransactionSetInstance(
            transaction_id="810",
            control_number="0001",
            content=[big, cur, seller_loop, buyer_loop, line_loop, tds],
        )

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == Invoice
        assert mapper.source_format.value == "x12"
        assert mapper.transaction_id == "810"

    def test_to_semantic_basic(self, mapper, simple_810_transaction):
        """Test converting X12 810 to semantic Invoice."""
        invoice = mapper.to_semantic(simple_810_transaction)

        # Basic invoice info
        assert invoice.id == "INV-001"
        assert invoice.issue_date == date(2024, 12, 20)
        assert invoice.document_currency_code == "USD"

        # Order reference
        assert invoice.order_reference is not None
        assert invoice.order_reference.id == "PO12345"

        # Seller
        assert invoice.accounting_supplier_party is not None
        seller = invoice.accounting_supplier_party.party
        assert seller.party_names[0].name == "Widget Supplier"

        # Buyer
        assert invoice.accounting_customer_party is not None
        buyer = invoice.accounting_customer_party.party
        assert buyer.party_names[0].name == "Acme Corp"

        # Line items
        assert len(invoice.invoice_lines) == 1
        line = invoice.invoice_lines[0]
        assert line.id == "1"
        assert line.invoiced_quantity.value == Decimal("10")
        assert line.price.price_amount.value == Decimal("25.00")

        # Total
        assert invoice.legal_monetary_total is not None
        assert invoice.legal_monetary_total.payable_amount.value == Decimal("250.00")

    def test_to_semantic_wrong_transaction(self, mapper):
        """Test error when wrong transaction type."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
        )
        with pytest.raises(ValueError, match="Expected 810"):
            mapper.to_semantic(txn)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic Invoice to X12 segments."""
        invoice = Invoice(
            id="INV-999",
            issue_date=date(2024, 7, 1),
            document_currency_code="USD",
            accounting_supplier_party=SupplierParty(
                party=Party(
                    party_names=[PartyName(name="Test Seller")],
                )
            ),
            accounting_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Test Buyer")],
                )
            ),
            legal_monetary_total=MonetaryTotal(
                payable_amount=Amount(value=Decimal("500"), currency="USD"),
            ),
            invoice_lines=[
                InvoiceLine(
                    id="1",
                    invoiced_quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    line_extension_amount=Amount(value=Decimal("500"), currency="USD"),
                    price=Price(price_amount=Amount(value=Decimal("100.00"), currency="USD")),
                    item=Item(description="Test Item"),
                )
            ],
        )

        segments = mapper.from_semantic(invoice)

        # Check BIG segment
        big = next(s for s in segments if s["tag"] == "BIG")
        assert big["elements"][0] == "20240701"  # Invoice Date
        assert big["elements"][1] == "INV-999"  # Invoice Number

        # Check N1 segment
        n1_segments = [s for s in segments if s["tag"] == "N1"]
        seller_n1 = next((n for n in n1_segments if n["elements"][0] == "SE"), None)
        assert seller_n1 is not None
        assert seller_n1["elements"][1] == "Test Seller"


# =============================================================================
# X12 Despatch Advice Mapper Tests
# =============================================================================


class TestX12DespatchAdviceMapper:
    """Test X12 856 ASN/Despatch Advice mapping."""

    @pytest.fixture
    def mapper(self):
        return X12DespatchAdviceMapper()

    @pytest.fixture
    def simple_856_transaction(self) -> TransactionSetInstance:
        """Create a simple 856 transaction for testing."""
        # BSN segment
        bsn = make_parsed_segment(
            "BSN",
            [
                "00",  # BSN01 - Purpose
                "ASN-001",  # BSN02 - Shipment ID
                "20241218",  # BSN03 - Date
                "1430",  # BSN04 - Time
            ],
        )

        # Build HL hierarchy
        # HL for Shipment level
        hl_ship = make_parsed_segment(
            "HL",
            [
                "1",  # HL01 - ID
                "",  # HL02 - Parent (none for root)
                "S",  # HL03 - Level Code (Shipment)
                "1",  # HL04 - Has children
            ],
        )
        td1 = make_parsed_segment(
            "TD1",
            [
                "CTN",  # TD1*01 - Packaging Code
                "5",  # TD1*02 - Lading Quantity
            ],
        )
        td5 = make_parsed_segment(
            "TD5",
            [
                "B",  # TD5*01 - Routing Sequence
                "2",  # TD5*02 - ID Code Qualifier
                "FEDX",  # TD5*03 - Carrier ID
            ],
        )

        # N1 loop for Ship From
        n1_sf = make_parsed_segment("N1", ["SF", "Warehouse Alpha", "92", "WH001"])
        n3_sf = make_parsed_segment("N3", ["100 Industrial Blvd"])
        n4_sf = make_parsed_segment("N4", ["Memphis", "TN", "38118", "US"])
        sf_loop = make_loop("N1", [n1_sf, n3_sf, n4_sf])

        # HL for Order level
        hl_order = make_parsed_segment(
            "HL",
            [
                "2",  # HL01 - ID
                "1",  # HL02 - Parent (shipment)
                "O",  # HL03 - Level Code (Order)
                "1",  # HL04 - Has children
            ],
        )
        prf = make_parsed_segment(
            "PRF",
            [
                "PO12345",  # PRF*01 - PO Number
                "",  # PRF*02
                "",  # PRF*03
                "20241215",  # PRF*04 - PO Date
            ],
        )

        # HL for Item level
        hl_item = make_parsed_segment(
            "HL",
            [
                "3",  # HL01 - ID
                "2",  # HL02 - Parent (order)
                "I",  # HL03 - Level Code (Item)
                "0",  # HL04 - No children
            ],
        )
        lin = make_parsed_segment(
            "LIN",
            [
                "",  # LIN*01 - Line Number
                "UP",  # LIN*02 - UPC qualifier
                "012345678901",  # LIN*03 - UPC
            ],
        )
        sn1 = make_parsed_segment(
            "SN1",
            [
                "",  # SN1*01 - Line Number
                "10",  # SN1*02 - Quantity Shipped
                "EA",  # SN1*03 - Unit
            ],
        )

        # Build HL tree
        item_node = HLNode(
            hl_id="3",
            parent_id="2",
            level_code="I",
            has_children=False,
            segments=[hl_item, lin, sn1],
        )
        order_node = HLNode(
            hl_id="2",
            parent_id="1",
            level_code="O",
            has_children=True,
            segments=[hl_order, prf],
            children=[item_node],
        )
        shipment_node = HLNode(
            hl_id="1",
            parent_id=None,
            level_code="S",
            has_children=True,
            segments=[hl_ship, td1, td5],
            children=[order_node],
        )

        # Build transaction
        return TransactionSetInstance(
            transaction_id="856",
            control_number="0001",
            content=[bsn, sf_loop],
            hl_root=shipment_node,
        )

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == DespatchAdvice
        assert mapper.source_format.value == "x12"
        assert mapper.transaction_id == "856"

    def test_to_semantic_basic(self, mapper, simple_856_transaction):
        """Test converting X12 856 to semantic DespatchAdvice."""
        advice = mapper.to_semantic(simple_856_transaction)

        # Basic info
        assert advice.id == "ASN-001"
        assert advice.issue_date == date(2024, 12, 18)

        # Shipment
        assert advice.shipment is not None
        assert advice.shipment.id is not None

        # Despatch lines
        assert len(advice.despatch_lines) >= 1

    def test_to_semantic_wrong_transaction(self, mapper):
        """Test error when wrong transaction type."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
        )
        with pytest.raises(ValueError, match="Expected 856"):
            mapper.to_semantic(txn)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic DespatchAdvice to X12 segments."""
        advice = DespatchAdvice(
            id="ASN-999",
            issue_date=date(2024, 8, 1),
            despatch_supplier_party=SupplierParty(
                party=Party(
                    party_names=[PartyName(name="Shipping Warehouse")],
                )
            ),
            shipment=Shipment(
                id="SHIP-001",
            ),
            despatch_lines=[
                DespatchLine(
                    id="1",
                    delivered_quantity=Quantity(value=Decimal("20"), unit_code="EA"),
                    item=Item(
                        standard_item_identification=ItemIdentification(
                            id=Identifier(value="999888777666", scheme_id="UPC")
                        ),
                    ),
                )
            ],
        )

        segments = mapper.from_semantic(advice)

        # Check BSN segment
        bsn = next(s for s in segments if s["tag"] == "BSN")
        assert bsn["elements"][1] == "ASN-999"  # Shipment ID
        assert bsn["elements"][2] == "20240801"  # Date

        # Check HL segments exist
        hl_segments = [s for s in segments if s["tag"] == "HL"]
        assert len(hl_segments) >= 1


# =============================================================================
# Round-trip Tests
# =============================================================================


class TestRoundTrip:
    """Test round-trip conversion accuracy."""

    def test_order_roundtrip_preserves_key_fields(self):
        """Test that Order -> X12 -> Order preserves key fields."""
        mapper = X12OrderMapper()

        original = Order(
            id="RT-001",
            issue_date=date(2024, 3, 15),
            document_currency_code="USD",
            order_type_code="SA",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Round Trip Buyer")],
                    postal_address=Address(
                        street_name="789 Test Blvd",
                        city_name="Austin",
                        country_subentity="TX",
                        postal_zone="78701",
                    ),
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("25"), unit_code="CS"),
                    price=Price(price_amount=Amount(value=Decimal("50.00"), currency="USD")),
                    item=Item(
                        description="Round Trip Product",
                        standard_item_identification=ItemIdentification(
                            id=Identifier(value="123456789012", scheme_id="UPC")
                        ),
                    ),
                )
            ],
        )

        # Convert to X12 segments
        x12_segments = mapper.from_semantic(original)

        # Build segments into a mock transaction
        content = []
        current_loop = None

        for seg_dict in x12_segments:
            tag = seg_dict["tag"]
            values = seg_dict["elements"]
            parsed_seg = make_parsed_segment(tag, values)

            # Detect loop boundaries
            if tag == "N1":
                if current_loop:
                    content.append(current_loop)
                current_loop = make_loop("N1", [parsed_seg])
            elif tag in ("N2", "N3", "N4", "PER") and current_loop and current_loop.loop_id == "N1":
                current_loop.segments.append(parsed_seg)
            elif tag == "PO1":
                if current_loop:
                    content.append(current_loop)
                current_loop = make_loop("PO1", [parsed_seg])
            elif tag in ("PID", "SAC", "DTM") and current_loop and current_loop.loop_id == "PO1":
                current_loop.segments.append(parsed_seg)
            else:
                if current_loop:
                    content.append(current_loop)
                    current_loop = None
                content.append(parsed_seg)

        if current_loop:
            content.append(current_loop)

        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=content,
        )

        # Convert back to semantic
        restored = mapper.to_semantic(txn)

        # Verify key fields preserved
        assert restored.id == original.id
        assert restored.issue_date == original.issue_date
        assert restored.document_currency_code == original.document_currency_code
        assert len(restored.order_lines) == len(original.order_lines)

        # Line item details
        orig_line = original.order_lines[0]
        rest_line = restored.order_lines[0]
        assert rest_line.quantity.value == orig_line.quantity.value
        assert rest_line.quantity.unit_code == orig_line.quantity.unit_code
