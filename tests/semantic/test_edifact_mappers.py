"""
Tests for EDIFACT Semantic Mappers.

Tests the mapping between EDIFACT messages and semantic models.
"""

from datetime import date
from decimal import Decimal

import pytest

from edi_schema.edifact.ast import (
    MessageInstance,
    ParsedComponent,
    ParsedElement,
    ParsedSegment,
    RawComponent,
    RawElement,
    RawSegment,
    SegmentGroupInstance,
    SourcePosition,
)
from edi_schema.semantic.mappers.edifact import (
    EdifactDespatchAdviceMapper,
    EdifactInvoiceMapper,
    EdifactOrderMapper,
)
from edi_schema.semantic.mappers.edifact.utils import (
    format_edifact_date,
    format_edifact_time,
    map_nad_party_qualifier,
    map_product_id_qualifier,
    map_reference_qualifier,
    parse_decimal,
    parse_edifact_date,
    parse_edifact_time,
)
from edi_schema.semantic.models import (
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
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    Shipment,
    SupplierParty,
)

# =============================================================================
# Test Fixtures - Mock EDIFACT AST Building Helpers
# =============================================================================


def make_position() -> SourcePosition:
    """Create a dummy source position."""
    return SourcePosition(offset=0, line=1, column=1)


def make_raw_component(value: str, index: int) -> RawComponent:
    """Create a RawComponent."""
    return RawComponent(value=value, position=make_position(), component_index=index)


def make_raw_element(
    value: str | None, index: int, components: list[str] | None = None
) -> RawElement:
    """Create a RawElement."""
    if components is not None:
        raw_components = [make_raw_component(v, i + 1) for i, v in enumerate(components)]
        return RawElement(
            value=None,
            position=make_position(),
            element_index=index,
            components=raw_components,
        )
    return RawElement(
        value=value or "",
        position=make_position(),
        element_index=index,
        components=None,
    )


def make_raw_segment(tag: str, elements: list) -> RawSegment:
    """
    Create a RawSegment from tag and element values.

    Elements can be:
    - str: Simple element value
    - list[str]: Composite element with components
    """
    raw_elements = []
    for i, elem in enumerate(elements):
        if isinstance(elem, list):
            raw_elements.append(make_raw_element(None, i + 1, elem))
        else:
            raw_elements.append(make_raw_element(elem, i + 1))

    return RawSegment(
        tag=tag,
        elements=raw_elements,
        position=make_position(),
        raw_text=f"{tag}+...'",
    )


def make_parsed_element(raw: RawElement) -> ParsedElement:
    """Create a ParsedElement from RawElement."""
    components = None
    if raw.components:
        components = [ParsedComponent(value=rc.value, raw=rc) for rc in raw.components]
    return ParsedElement(raw=raw, components=components)


def make_parsed_segment(tag: str, elements: list) -> ParsedSegment:
    """
    Create a ParsedSegment from tag and element values.

    Elements can be:
    - str: Simple element value
    - list[str]: Composite element with components
    """
    raw = make_raw_segment(tag, elements)
    parsed_elements = [make_parsed_element(raw_elem) for raw_elem in raw.elements]
    return ParsedSegment(tag=tag, elements=parsed_elements, raw=raw)


def make_segment_group(
    group_number: int,
    segments: list[ParsedSegment],
    children: list[SegmentGroupInstance] | None = None,
) -> SegmentGroupInstance:
    """Create a SegmentGroupInstance."""
    return SegmentGroupInstance(
        group_number=group_number,
        segments=segments,
        children=children or [],
    )


def make_message_instance(
    message_type: str,
    content: list,
    version: str = "D",
    release: str = "23A",
) -> MessageInstance:
    """Create a MessageInstance."""
    return MessageInstance(
        reference_number="1",
        message_type=message_type,
        version=version,
        release=release,
        controlling_agency="UN",
        content=content,
    )


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestEdifactUtilityFunctions:
    """Test EDIFACT utility functions."""

    def test_parse_edifact_date_8char(self):
        """Test parsing CCYYMMDD format."""
        result = parse_edifact_date("20241215")
        assert result == date(2024, 12, 15)

    def test_parse_edifact_date_6char_2000s(self):
        """Test parsing YYMMDD format for 2000s."""
        result = parse_edifact_date("241215")
        assert result == date(2024, 12, 15)

    def test_parse_edifact_date_6char_1900s(self):
        """Test parsing YYMMDD format for 1900s."""
        result = parse_edifact_date("991215")
        assert result == date(1999, 12, 15)

    def test_parse_edifact_date_none(self):
        """Test parsing None returns None."""
        assert parse_edifact_date(None) is None
        assert parse_edifact_date("") is None

    def test_parse_edifact_date_invalid(self):
        """Test parsing invalid date returns None."""
        assert parse_edifact_date("invalid") is None
        assert parse_edifact_date("20241315") is None  # Invalid month

    def test_parse_edifact_time_4char(self):
        """Test parsing HHMM format."""
        from datetime import time

        result = parse_edifact_time("1430")
        assert result == time(14, 30)

    def test_parse_edifact_time_6char(self):
        """Test parsing HHMMSS format."""
        from datetime import time

        result = parse_edifact_time("143025")
        assert result == time(14, 30, 25)

    def test_parse_edifact_time_none(self):
        """Test parsing None returns None."""
        assert parse_edifact_time(None) is None
        assert parse_edifact_time("") is None

    def test_parse_decimal(self):
        """Test parse_decimal."""
        assert parse_decimal("123.45") == Decimal("123.45")
        assert parse_decimal(None) is None
        assert parse_decimal("invalid") is None

    def test_format_edifact_date(self):
        """Test formatting date to EDIFACT."""
        result = format_edifact_date(date(2024, 12, 15))
        assert result == "20241215"

    def test_format_edifact_date_none(self):
        """Test formatting None date."""
        assert format_edifact_date(None) == ""

    def test_format_edifact_time(self):
        """Test formatting time to EDIFACT."""
        from datetime import time

        result = format_edifact_time(time(14, 30))
        assert result == "1430"

    def test_map_nad_party_qualifier(self):
        """Test NAD party qualifier mapping."""
        assert map_nad_party_qualifier("BY") == "buyer"
        assert map_nad_party_qualifier("SU") == "supplier"
        assert map_nad_party_qualifier("SE") == "seller"
        assert map_nad_party_qualifier("XX") == "XX"  # Unknown returns original

    def test_map_product_id_qualifier(self):
        """Test product ID qualifier mapping."""
        assert map_product_id_qualifier("EN") == ("standard", "EAN")
        assert map_product_id_qualifier("UP") == ("standard", "UPC")
        assert map_product_id_qualifier("VP") == ("sellers", None)
        assert map_product_id_qualifier("XX") == ("additional", None)

    def test_map_reference_qualifier(self):
        """Test reference qualifier mapping."""
        assert map_reference_qualifier("ON") == "purchase_order"
        assert map_reference_qualifier("VN") == "vendor_order"
        assert map_reference_qualifier("IV") == "invoice"
        assert map_reference_qualifier("XX") == "XX"


# =============================================================================
# EDIFACT Order Mapper Tests
# =============================================================================


class TestEdifactOrderMapper:
    """Test EDIFACT ORDERS message mapping."""

    @pytest.fixture
    def mapper(self):
        return EdifactOrderMapper()

    @pytest.fixture
    def simple_orders_message(self) -> MessageInstance:
        """Create a simple ORDERS message for testing."""
        # BGM segment - Beginning of Message
        bgm = make_parsed_segment(
            "BGM",
            [
                ["220"],  # C002 - Document type (Order)
                ["PO12345"],  # C106 - Document ID
                "9",  # Original
            ],
        )

        # DTM segment - Document date
        dtm = make_parsed_segment(
            "DTM",
            [
                ["137", "20241215", "102"],  # C507 - Date qualifier, date, format
            ],
        )

        # CUX segment - Currency
        cux = make_parsed_segment(
            "CUX",
            [
                ["2", "USD", "4"],  # C504 - Currency details
            ],
        )

        # SG2 - Buyer party group
        nad_by = make_parsed_segment(
            "NAD",
            [
                "BY",  # Party qualifier
                ["ACME001", "", "92"],  # C082 - Party ID
                ["Acme Corp"],  # C080 - Party name
                "",  # C059 - Street
                ["123 Main Street"],  # C059 - Street detail
                "Chicago",  # City
                "IL",  # State
                "60601",  # Postal
                "US",  # Country
            ],
        )
        sg2_buyer = make_segment_group(2, [nad_by])

        # SG2 - Seller party group
        nad_su = make_parsed_segment(
            "NAD",
            [
                "SU",
                ["SUPP001", "", "1"],
                ["Widget Supplier"],
            ],
        )
        sg2_seller = make_segment_group(2, [nad_su])

        # SG25 - Line item group
        lin = make_parsed_segment(
            "LIN",
            [
                "1",  # Line number
                "",  # Action
                ["012345678901", "EN"],  # C212 - Product ID (EAN)
            ],
        )
        qty = make_parsed_segment(
            "QTY",
            [
                ["21", "10", "EA"],  # C186 - Quantity details
            ],
        )
        imd = make_parsed_segment(
            "IMD",
            [
                "F",  # Description format
                "",
                ["", "", "", "Industrial Widget"],  # C273 - Item description
            ],
        )
        sg25 = make_segment_group(25, [lin, qty, imd])

        # UNS segment - Section control
        uns = make_parsed_segment("UNS", ["S"])

        # CNT segment - Control total
        cnt = make_parsed_segment("CNT", [["2", "1"]])

        content = [bgm, dtm, cux, sg2_buyer, sg2_seller, sg25, uns, cnt]

        return make_message_instance("ORDERS", content)

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == Order
        assert mapper.source_format.value == "edifact"
        assert mapper.transaction_id == "ORDERS"

    def test_to_semantic_basic(self, mapper, simple_orders_message):
        """Test converting EDIFACT ORDERS to semantic Order."""
        order = mapper.to_semantic(simple_orders_message)

        # Basic order info
        assert order.id == "PO12345"
        assert order.issue_date == date(2024, 12, 15)
        assert order.document_currency_code == "USD"
        assert order.order_type_code == "220"

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

        # Line items
        assert len(order.order_lines) == 1
        line = order.order_lines[0]
        assert line.id == "1"
        assert line.quantity.value == Decimal("10")
        assert line.quantity.unit_code == "EA"
        assert line.item.description == "Industrial Widget"
        assert line.item.standard_item_identification.id.value == "012345678901"

        # Source tracking
        assert order._source_format == "edifact"
        assert order._source_version == "D23A"

    def test_to_semantic_wrong_message(self, mapper):
        """Test error when wrong message type."""
        msg = make_message_instance("INVOIC", [])
        with pytest.raises(ValueError, match="Expected ORDERS"):
            mapper.to_semantic(msg)

    def test_to_semantic_missing_bgm(self, mapper):
        """Test error when BGM segment missing."""
        msg = make_message_instance("ORDERS", [])
        with pytest.raises(ValueError, match="Missing required BGM segment"):
            mapper.to_semantic(msg)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic Order to EDIFACT segments."""
        order = Order(
            id="PO99999",
            issue_date=date(2024, 6, 15),
            document_currency_code="EUR",
            order_type_code="220",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Test Buyer")],
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="BUYER001", scheme_id="91"))
                    ],
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    price=Price(price_amount=Amount(value=Decimal("100.00"), currency="EUR")),
                    item=Item(
                        description="Test Product",
                        sellers_item_identification=ItemIdentification(
                            id=Identifier(value="SKU-123")
                        ),
                    ),
                )
            ],
        )

        result = mapper.from_semantic(order)

        assert result["message_type"] == "ORDERS"
        segments = result["segments"]

        # Check BGM segment
        bgm = next(s for s in segments if s["tag"] == "BGM")
        assert bgm["elements"][1]["components"][0] == "PO99999"

        # Check DTM segment
        dtm = next(s for s in segments if s["tag"] == "DTM")
        assert dtm["elements"][0]["components"][1] == "20240615"

        # Check CUX segment
        cux = next(s for s in segments if s["tag"] == "CUX")
        assert cux["elements"][0]["components"][1] == "EUR"

        # Check NAD segment for buyer
        nad_segments = [s for s in segments if s["tag"] == "NAD"]
        buyer_nad = next((n for n in nad_segments if n["elements"][0] == "BY"), None)
        assert buyer_nad is not None

        # Check QTY segment
        qty = next(s for s in segments if s["tag"] == "QTY")
        assert qty["elements"][0]["components"][1] == "5"


# =============================================================================
# EDIFACT Invoice Mapper Tests
# =============================================================================


class TestEdifactInvoiceMapper:
    """Test EDIFACT INVOIC message mapping."""

    @pytest.fixture
    def mapper(self):
        return EdifactInvoiceMapper()

    @pytest.fixture
    def simple_invoic_message(self) -> MessageInstance:
        """Create a simple INVOIC message for testing."""
        # BGM segment
        bgm = make_parsed_segment(
            "BGM",
            [
                ["380"],  # C002 - Invoice type
                ["INV-001"],  # C106 - Document ID
                "9",
            ],
        )

        # DTM segment - Invoice date
        dtm_doc = make_parsed_segment(
            "DTM",
            [
                ["137", "20241220", "102"],
            ],
        )

        # DTM segment - Due date
        dtm_due = make_parsed_segment(
            "DTM",
            [
                ["13", "20250120", "102"],
            ],
        )

        # SG1 - Reference group (Order reference)
        rff = make_parsed_segment(
            "RFF",
            [
                ["ON", "PO12345"],
            ],
        )
        sg1 = make_segment_group(1, [rff])

        # CUX segment
        cux = make_parsed_segment(
            "CUX",
            [
                ["2", "USD", "4"],
            ],
        )

        # SG2 - Seller party group
        nad_su = make_parsed_segment(
            "NAD",
            [
                "SU",
                ["SUPP001", "", "1"],
                ["Widget Supplier"],
                "",
                ["100 Industrial Way"],
                "Memphis",
                "TN",
                "38118",
                "US",
            ],
        )
        sg2_seller = make_segment_group(2, [nad_su])

        # SG2 - Buyer party group
        nad_by = make_parsed_segment(
            "NAD",
            [
                "BY",
                ["ACME001", "", "92"],
                ["Acme Corp"],
            ],
        )
        sg2_buyer = make_segment_group(2, [nad_by])

        # SG25 - Line item group
        lin = make_parsed_segment(
            "LIN",
            [
                "1",
                "",
                ["012345678901", "EN"],
            ],
        )
        qty = make_parsed_segment(
            "QTY",
            [
                ["47", "10", "EA"],  # Invoiced quantity
            ],
        )
        moa = make_parsed_segment(
            "MOA",
            [
                ["203", "250.00"],  # Line amount
            ],
        )
        sg25 = make_segment_group(25, [lin, qty, moa])

        # UNS - Section control
        uns = make_parsed_segment("UNS", ["S"])

        # MOA - Total amounts
        moa_total = make_parsed_segment(
            "MOA",
            [
                ["9", "250.00"],  # Amount due
            ],
        )
        moa_tax = make_parsed_segment(
            "MOA",
            [
                ["176", "25.00"],  # Tax amount
            ],
        )

        content = [
            bgm,
            dtm_doc,
            dtm_due,
            sg1,
            cux,
            sg2_seller,
            sg2_buyer,
            sg25,
            uns,
            moa_total,
            moa_tax,
        ]

        return make_message_instance("INVOIC", content)

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == Invoice
        assert mapper.source_format.value == "edifact"
        assert mapper.transaction_id == "INVOIC"

    def test_to_semantic_basic(self, mapper, simple_invoic_message):
        """Test converting EDIFACT INVOIC to semantic Invoice."""
        invoice = mapper.to_semantic(simple_invoic_message)

        # Basic invoice info
        assert invoice.id == "INV-001"
        assert invoice.issue_date == date(2024, 12, 20)
        assert invoice.due_date == date(2025, 1, 20)
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

        # Monetary totals
        assert invoice.legal_monetary_total is not None
        assert invoice.legal_monetary_total.payable_amount.value == Decimal("250.00")

        # Tax totals
        assert len(invoice.tax_total) == 1
        assert invoice.tax_total[0].tax_amount.value == Decimal("25.00")

    def test_to_semantic_wrong_message(self, mapper):
        """Test error when wrong message type."""
        msg = make_message_instance("ORDERS", [])
        with pytest.raises(ValueError, match="Expected INVOIC"):
            mapper.to_semantic(msg)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic Invoice to EDIFACT segments."""
        invoice = Invoice(
            id="INV-999",
            issue_date=date(2024, 7, 1),
            due_date=date(2024, 8, 1),
            document_currency_code="USD",
            order_reference=OrderReference(id="PO-REF-001"),
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Test Seller")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Test Buyer")])
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

        result = mapper.from_semantic(invoice)

        assert result["message_type"] == "INVOIC"
        segments = result["segments"]

        # Check BGM segment
        bgm = next(s for s in segments if s["tag"] == "BGM")
        assert bgm["elements"][1]["components"][0] == "INV-999"

        # Check RFF segment for order reference
        rff = next(s for s in segments if s["tag"] == "RFF")
        assert rff["elements"][0]["components"][1] == "PO-REF-001"


# =============================================================================
# EDIFACT DespatchAdvice Mapper Tests
# =============================================================================


class TestEdifactDespatchAdviceMapper:
    """Test EDIFACT DESADV message mapping."""

    @pytest.fixture
    def mapper(self):
        return EdifactDespatchAdviceMapper()

    @pytest.fixture
    def simple_desadv_message(self) -> MessageInstance:
        """Create a simple DESADV message for testing."""
        # BGM segment
        bgm = make_parsed_segment(
            "BGM",
            [
                ["351"],  # C002 - Despatch advice
                ["ASN-001"],  # C106 - Document ID
                "9",
            ],
        )

        # DTM segment - Document date
        dtm_doc = make_parsed_segment(
            "DTM",
            [
                ["137", "20241218", "102"],
            ],
        )

        # DTM segment - Despatch date
        dtm_ship = make_parsed_segment(
            "DTM",
            [
                ["11", "20241219", "102"],
            ],
        )

        # SG1 - Reference group
        rff = make_parsed_segment(
            "RFF",
            [
                ["ON", "PO12345"],
            ],
        )
        sg1 = make_segment_group(1, [rff])

        # SG2 - Ship from party
        nad_sf = make_parsed_segment(
            "NAD",
            [
                "SF",
                ["WH001", "", "92"],
                ["Warehouse Alpha"],
                "",
                ["100 Industrial Blvd"],
                "Memphis",
                "TN",
                "38118",
                "US",
            ],
        )
        sg2_sf = make_segment_group(2, [nad_sf])

        # SG2 - Consignee party
        nad_uc = make_parsed_segment(
            "NAD",
            [
                "UC",
                ["ACME001", "", "92"],
                ["Acme Corp"],
            ],
        )
        sg2_uc = make_segment_group(2, [nad_uc])

        # SG10 - Transport details
        tdt = make_parsed_segment(
            "TDT",
            [
                "20",  # Stage qualifier
                "",
                ["30"],  # C220 - Mode (Road)
                "",
                ["FEDX"],  # C040 - Carrier ID
            ],
        )
        sg10 = make_segment_group(10, [tdt])

        # SG25 - Consignment packing
        cps = make_parsed_segment("CPS", ["1"])

        # SG26 - Line item (nested in SG25)
        lin = make_parsed_segment(
            "LIN",
            [
                "1",
                "",
                ["012345678901", "EN"],
            ],
        )
        qty = make_parsed_segment(
            "QTY",
            [
                ["12", "10", "EA"],  # Despatch quantity
            ],
        )
        sg26 = make_segment_group(26, [lin, qty])
        sg25 = make_segment_group(25, [cps], children=[sg26])

        # CNT segment
        cnt = make_parsed_segment("CNT", [["2", "1"]])

        content = [
            bgm,
            dtm_doc,
            dtm_ship,
            sg1,
            sg2_sf,
            sg2_uc,
            sg10,
            sg25,
            cnt,
        ]

        return make_message_instance("DESADV", content)

    def test_mapper_properties(self, mapper):
        """Test mapper property methods."""
        assert mapper.semantic_type == DespatchAdvice
        assert mapper.source_format.value == "edifact"
        assert mapper.transaction_id == "DESADV"

    def test_to_semantic_basic(self, mapper, simple_desadv_message):
        """Test converting EDIFACT DESADV to semantic DespatchAdvice."""
        advice = mapper.to_semantic(simple_desadv_message)

        # Basic info
        assert advice.id == "ASN-001"
        assert advice.issue_date == date(2024, 12, 18)

        # Order reference
        assert advice.order_reference is not None
        assert advice.order_reference.id == "PO12345"

        # Ship from party
        assert advice.despatch_supplier_party is not None
        ship_from = advice.despatch_supplier_party.party
        assert ship_from.party_names[0].name == "Warehouse Alpha"

        # Consignee party
        assert advice.delivery_customer_party is not None
        consignee = advice.delivery_customer_party.party
        assert consignee.party_names[0].name == "Acme Corp"

        # Shipment details
        assert advice.shipment is not None
        assert advice.shipment.actual_despatch_date == date(2024, 12, 19)

        # Despatch lines
        assert len(advice.despatch_lines) == 1
        line = advice.despatch_lines[0]
        assert line.id == "1"
        assert line.delivered_quantity.value == Decimal("10")
        assert line.delivered_quantity.unit_code == "EA"

    def test_to_semantic_wrong_message(self, mapper):
        """Test error when wrong message type."""
        msg = make_message_instance("ORDERS", [])
        with pytest.raises(ValueError, match="Expected DESADV"):
            mapper.to_semantic(msg)

    def test_from_semantic_basic(self, mapper):
        """Test converting semantic DespatchAdvice to EDIFACT segments."""
        advice = DespatchAdvice(
            id="ASN-999",
            issue_date=date(2024, 8, 1),
            order_reference=OrderReference(id="PO-REF"),
            despatch_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Shipping Warehouse")])
            ),
            delivery_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Customer Inc")])
            ),
            shipment=Shipment(
                id="SHIP-001",
                actual_despatch_date=date(2024, 8, 2),
            ),
            despatch_lines=[
                DespatchLine(
                    id="1",
                    delivered_quantity=Quantity(value=Decimal("20"), unit_code="EA"),
                    item=Item(
                        standard_item_identification=ItemIdentification(
                            id=Identifier(value="999888777666", scheme_id="EAN")
                        ),
                    ),
                )
            ],
        )

        result = mapper.from_semantic(advice)

        assert result["message_type"] == "DESADV"
        segments = result["segments"]

        # Check BGM segment
        bgm = next(s for s in segments if s["tag"] == "BGM")
        assert bgm["elements"][1]["components"][0] == "ASN-999"

        # Check DTM segments
        dtm_segments = [s for s in segments if s["tag"] == "DTM"]
        assert len(dtm_segments) >= 1

        # Check CPS segment exists
        cps = next(s for s in segments if s["tag"] == "CPS")
        assert cps is not None


# =============================================================================
# Round-trip Tests
# =============================================================================


class TestEdifactRoundTrip:
    """Test round-trip conversion accuracy."""

    def test_order_from_semantic_produces_valid_structure(self):
        """Test that Order -> EDIFACT produces valid segment structure."""
        mapper = EdifactOrderMapper()

        original = Order(
            id="RT-001",
            issue_date=date(2024, 3, 15),
            document_currency_code="USD",
            order_type_code="220",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Round Trip Buyer")],
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="BUYER123", scheme_id="92"))
                    ],
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
                            id=Identifier(value="123456789012", scheme_id="EAN")
                        ),
                    ),
                )
            ],
        )

        result = mapper.from_semantic(original)

        # Verify structure
        assert result["message_type"] == "ORDERS"
        segments = result["segments"]

        # Required segments exist
        tags = [s["tag"] for s in segments]
        assert "BGM" in tags
        assert "DTM" in tags
        assert "CUX" in tags
        assert "NAD" in tags
        assert "LIN" in tags
        assert "QTY" in tags

    def test_invoice_from_semantic_produces_valid_structure(self):
        """Test that Invoice -> EDIFACT produces valid segment structure."""
        mapper = EdifactInvoiceMapper()

        original = Invoice(
            id="RT-INV-001",
            issue_date=date(2024, 4, 1),
            document_currency_code="EUR",
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Test Supplier")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Test Customer")])
            ),
            legal_monetary_total=MonetaryTotal(
                payable_amount=Amount(value=Decimal("1000"), currency="EUR"),
            ),
            invoice_lines=[
                InvoiceLine(
                    id="1",
                    invoiced_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    line_extension_amount=Amount(value=Decimal("1000"), currency="EUR"),
                    price=Price(price_amount=Amount(value=Decimal("100"), currency="EUR")),
                    item=Item(description="Test Line Item"),
                )
            ],
        )

        result = mapper.from_semantic(original)

        assert result["message_type"] == "INVOIC"
        segments = result["segments"]

        tags = [s["tag"] for s in segments]
        assert "BGM" in tags
        assert "DTM" in tags
        assert "NAD" in tags
        assert "LIN" in tags
        assert "MOA" in tags
