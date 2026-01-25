"""
X12 810 Invoice Mapper.

Maps between X12 810 Invoice and semantic Invoice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    AllowanceCharge,
    Amount,
    CustomerParty,
    Identifier,
    Invoice,
    InvoiceLine,
    Item,
    ItemIdentification,
    MonetaryTotal,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    PaymentTerms,
    Price,
    Quantity,
    SupplierParty,
    TaxCategory,
    TaxSubtotal,
    TaxTotal,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_loops,
    find_all_segments_in_loop,
    find_segment,
    find_segment_in_loop,
    get_element_value,
    map_id_qualifier,
    map_product_id_qualifier,
    parse_decimal,
    parse_x12_amount,
    parse_x12_date,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, TransactionSetInstance


class X12InvoiceMapper(SemanticMapper[Invoice]):
    """
    Maps X12 810 Invoice to/from semantic Invoice model.

    X12 810 Structure:
    - BIG: Beginning Invoice (invoice number, date, PO reference)
    - CUR: Currency
    - REF: References
    - N1 Loop: Party Information
    - ITD: Payment Terms
    - IT1 Loop: Line Items
      - IT1: Baseline Item Data
      - PID: Product Description
      - SAC: Allowances/Charges
      - TXI: Tax Information
    - TDS: Total Monetary Value Summary
    - CAD: Carrier Details
    - ISS: Invoice Ship Summary
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[Invoice]:
        return Invoice

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "810"

    def to_semantic(self, source: "TransactionSetInstance") -> Invoice:
        """Convert X12 810 to semantic Invoice."""
        if source.transaction_id != "810":
            raise ValueError(f"Expected 810, got {source.transaction_id}")

        content = source.content

        # Extract BIG segment (required)
        big = find_segment(content, "BIG")
        if not big:
            raise ValueError("Missing required BIG segment")

        # Parse BIG fields
        issue_date = parse_x12_date(get_element_value(big, 1))
        if not issue_date:
            raise ValueError("Missing or invalid date in BIG01")

        invoice_number = get_element_value(big, 2) or ""
        po_date = parse_x12_date(get_element_value(big, 3))
        po_number = get_element_value(big, 4)
        invoice_type_code = get_element_value(big, 7)

        # Extract currency from CUR segment
        cur = find_segment(content, "CUR")
        currency = "USD"
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # Initialize parties (required for Invoice)
        supplier_party = SupplierParty(party=Party())
        customer_party = CustomerParty(party=Party())

        # Extract parties from N1 loops
        n1_loops = find_all_loops(content, "N1")
        payee_party = None
        for n1_loop in n1_loops:
            party_code = get_element_value(find_segment_in_loop(n1_loop, "N1"), 1)
            party = self._build_party_from_n1_loop(n1_loop)

            if party_code == "SE":  # Seller
                supplier_party = SupplierParty(party=party)
            elif party_code == "BY":  # Buyer
                customer_party = CustomerParty(party=party)
            elif party_code == "RI":  # Remit To (Payee)
                payee_party = party

        # Create base invoice
        invoice = Invoice(
            id=invoice_number,
            issue_date=issue_date,
            document_currency_code=currency,
            invoice_type_code=invoice_type_code,
            accounting_supplier_party=supplier_party,
            accounting_customer_party=customer_party,
            legal_monetary_total=MonetaryTotal(),  # Will be populated later
        )

        if payee_party:
            invoice.payee_party = payee_party

        # Add order reference if present
        if po_number:
            invoice.order_reference = OrderReference(
                id=po_number,
                issue_date=po_date,
            )

        # Extract payment terms from ITD
        itd = find_segment(content, "ITD")
        if itd:
            invoice.payment_terms.append(self._parse_itd_segment(itd))

        # Extract line items from IT1 loops
        it1_loops = find_all_loops(content, "IT1")
        for i, it1_loop in enumerate(it1_loops, 1):
            line = self._parse_it1_loop(it1_loop, i, currency)
            invoice.invoice_lines.append(line)

        # Extract TDS (Total Monetary Value)
        tds = find_segment(content, "TDS")
        if tds:
            # TDS amounts are in cents (implied 2 decimals)
            total_amount = parse_x12_amount(get_element_value(tds, 1))
            if total_amount:
                invoice.legal_monetary_total.tax_inclusive_amount = Amount(
                    value=total_amount, currency=currency
                )
                invoice.legal_monetary_total.payable_amount = Amount(
                    value=total_amount, currency=currency
                )

        # Calculate line extension total
        line_total = sum(
            (line.line_extension_amount.value for line in invoice.invoice_lines
             if line.line_extension_amount),
            Decimal("0")
        )
        if line_total > 0:
            invoice.legal_monetary_total.line_extension_amount = Amount(
                value=line_total, currency=currency
            )

        # Extract CTT for line count
        ctt = find_segment(content, "CTT")
        if ctt:
            count_str = get_element_value(ctt, 1)
            if count_str:
                invoice.line_count = int(count_str)

        # Set source tracking
        invoice._source_format = "x12"
        invoice._source_version = "005010"

        return invoice

    def from_semantic(self, model: Invoice) -> object:
        """Convert semantic Invoice to X12 810."""
        segments = []

        # BIG segment
        big_elements = [
            model.issue_date.strftime("%Y%m%d"),  # BIG01
            model.id,  # BIG02
        ]
        if model.order_reference:
            big_elements.append(
                model.order_reference.issue_date.strftime("%Y%m%d")
                if model.order_reference.issue_date else ""
            )  # BIG03
            big_elements.append(model.order_reference.id)  # BIG04
        else:
            big_elements.extend(["", ""])

        segments.append({"tag": "BIG", "elements": big_elements})

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append({
                "tag": "CUR",
                "elements": ["SE", model.document_currency_code],
            })

        # N1 loops for parties
        if model.accounting_supplier_party:
            segments.extend(
                self._build_n1_loop("SE", model.accounting_supplier_party.party)
            )
        if model.accounting_customer_party:
            segments.extend(
                self._build_n1_loop("BY", model.accounting_customer_party.party)
            )
        if model.payee_party:
            segments.extend(self._build_n1_loop("RI", model.payee_party))

        # IT1 loops for line items
        for line in model.invoice_lines:
            segments.extend(self._build_it1_loop(line, model.document_currency_code))

        # TDS segment
        if model.legal_monetary_total.payable_amount:
            # Convert to cents
            cents = int(model.legal_monetary_total.payable_amount.value * 100)
            segments.append({"tag": "TDS", "elements": [str(cents)]})

        # CTT segment
        segments.append({
            "tag": "CTT",
            "elements": [str(len(model.invoice_lines))],
        })

        return segments

    def _build_party_from_n1_loop(self, n1_loop: "LoopInstance") -> Party:
        """Build a Party from an N1 loop."""
        party = Party()

        n1 = find_segment_in_loop(n1_loop, "N1")
        if n1:
            name = get_element_value(n1, 2)
            if name:
                party.party_names.append(PartyName(name=name))

            id_qualifier = get_element_value(n1, 3)
            id_value = get_element_value(n1, 4)
            if id_value:
                scheme = map_id_qualifier(id_qualifier) if id_qualifier else None
                party.party_identifications.append(
                    PartyIdentification(id=Identifier(value=id_value, scheme_id=scheme))
                )

        # N3/N4 for address
        n3 = find_segment_in_loop(n1_loop, "N3")
        n4 = find_segment_in_loop(n1_loop, "N4")
        if n3 or n4:
            party.postal_address = Address(
                street_name=get_element_value(n3, 1) if n3 else None,
                additional_street_name=get_element_value(n3, 2) if n3 else None,
                city_name=get_element_value(n4, 1) if n4 else None,
                country_subentity=get_element_value(n4, 2) if n4 else None,
                postal_zone=get_element_value(n4, 3) if n4 else None,
                country_code=get_element_value(n4, 4) if n4 else None,
            )

        return party

    def _parse_itd_segment(self, itd: "ParsedSegment") -> PaymentTerms:
        """Parse ITD segment into PaymentTerms."""
        discount_percent = parse_decimal(get_element_value(itd, 5))
        _net_days = get_element_value(itd, 7)  # noqa: F841 Parsed for future use
        description = get_element_value(itd, 12)

        return PaymentTerms(
            settlement_discount_percent=discount_percent,
            note=description,
        )

    def _parse_it1_loop(
        self, it1_loop: "LoopInstance", line_num: int, currency: str
    ) -> InvoiceLine:
        """Parse an IT1 loop into an InvoiceLine."""
        it1 = find_segment_in_loop(it1_loop, "IT1")
        if not it1:
            raise ValueError(f"IT1 loop {line_num} missing IT1 segment")

        # Line ID
        line_id = get_element_value(it1, 1) or str(line_num)

        # Quantity
        qty_value = parse_decimal(get_element_value(it1, 2)) or Decimal("0")
        unit_code = get_element_value(it1, 3) or "EA"

        # Unit price
        price_value = parse_decimal(get_element_value(it1, 4))

        # Build item
        item = self._build_item_from_it1(it1, it1_loop)

        # Calculate line extension
        line_amount = Decimal("0")
        if price_value:
            line_amount = qty_value * price_value

        # Create invoice line
        line = InvoiceLine(
            id=line_id,
            invoiced_quantity=Quantity(value=qty_value, unit_code=unit_code),
            line_extension_amount=Amount(value=line_amount, currency=currency),
            item=item,
        )

        if price_value is not None:
            line.price = Price(
                price_amount=Amount(value=price_value, currency=currency)
            )

        # Parse SAC segments
        for sac in find_all_segments_in_loop(it1_loop, "SAC"):
            ac = self._parse_sac_segment(sac, currency)
            if ac:
                line.allowance_charges.append(ac)

        # Parse TXI segments (tax)
        for txi in find_all_segments_in_loop(it1_loop, "TXI"):
            tax = self._parse_txi_segment(txi, currency)
            if tax:
                line.tax_total.append(tax)

        return line

    def _build_item_from_it1(
        self, it1: "ParsedSegment", it1_loop: "LoopInstance"
    ) -> Item:
        """Build Item from IT1 segment and loop."""
        item = Item()

        # Product IDs in pairs starting at IT106
        for i in range(6, 26, 2):
            qualifier = get_element_value(it1, i)
            value = get_element_value(it1, i + 1)
            if qualifier and value:
                field_type, scheme = map_product_id_qualifier(qualifier)
                item_id = ItemIdentification(
                    id=Identifier(value=value, scheme_id=scheme)
                )

                if field_type == "standard":
                    item.standard_item_identification = item_id
                elif field_type == "sellers":
                    item.sellers_item_identification = item_id
                elif field_type == "buyers":
                    item.buyers_item_identification = item_id
                elif field_type == "manufacturers":
                    item.manufacturers_item_identification = item_id

        # PID segment for description
        pid = find_segment_in_loop(it1_loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        return item

    def _parse_sac_segment(
        self, sac: "ParsedSegment", currency: str
    ) -> AllowanceCharge | None:
        """Parse SAC segment into AllowanceCharge."""
        indicator = get_element_value(sac, 1)
        if not indicator:
            return None

        is_charge = indicator == "C"
        amount_value = parse_decimal(get_element_value(sac, 5))
        if amount_value is None:
            return None

        return AllowanceCharge(
            charge_indicator=is_charge,
            amount=Amount(value=amount_value, currency=currency),
            allowance_charge_reason=get_element_value(sac, 12),
            allowance_charge_reason_code=get_element_value(sac, 4),
        )

    def _parse_txi_segment(
        self, txi: "ParsedSegment", currency: str
    ) -> TaxTotal | None:
        """Parse TXI segment into TaxTotal."""
        tax_type = get_element_value(txi, 1)
        tax_amount = parse_decimal(get_element_value(txi, 2))
        tax_percent = parse_decimal(get_element_value(txi, 3))

        if tax_amount is None:
            return None

        return TaxTotal(
            tax_amount=Amount(value=tax_amount, currency=currency),
            tax_subtotals=[
                TaxSubtotal(
                    tax_amount=Amount(value=tax_amount, currency=currency),
                    percent=tax_percent,
                    tax_category=TaxCategory(id=tax_type),
                )
            ],
        )

    def _build_n1_loop(self, party_code: str, party: Party) -> list[dict]:
        """Build N1 loop segments."""
        segments = []

        n1_elements = [party_code]
        if party.party_names:
            n1_elements.append(party.party_names[0].name)
        else:
            n1_elements.append("")

        if party.party_identifications:
            pid = party.party_identifications[0]
            qualifier = self._scheme_to_n1_qualifier(pid.id.scheme_id)
            n1_elements.extend([qualifier, pid.id.value])

        segments.append({"tag": "N1", "elements": n1_elements})

        if party.postal_address:
            addr = party.postal_address
            if addr.street_name:
                n3_elements = [addr.street_name]
                if addr.additional_street_name:
                    n3_elements.append(addr.additional_street_name)
                segments.append({"tag": "N3", "elements": n3_elements})

            if any([addr.city_name, addr.country_subentity, addr.postal_zone]):
                n4_elements = [
                    addr.city_name or "",
                    addr.country_subentity or "",
                    addr.postal_zone or "",
                ]
                if addr.country_code:
                    n4_elements.append(addr.country_code)
                segments.append({"tag": "N4", "elements": n4_elements})

        return segments

    def _build_it1_loop(self, line: InvoiceLine, currency: str) -> list[dict]:
        """Build IT1 loop segments."""
        segments = []

        it1_elements = [
            line.id,
            str(line.invoiced_quantity.value),
            line.invoiced_quantity.unit_code,
        ]

        if line.price:
            it1_elements.append(str(line.price.price_amount.value))
        else:
            it1_elements.append("")

        it1_elements.append("")  # IT105 - Basis

        # Add product IDs
        item = line.item
        if item.standard_item_identification:
            scheme = item.standard_item_identification.id.scheme_id
            qualifier = "UP" if scheme == "UPC" else "EN" if scheme == "EAN" else "UK"
            it1_elements.extend([qualifier, item.standard_item_identification.id.value])

        segments.append({"tag": "IT1", "elements": it1_elements})

        if line.item.description:
            segments.append({
                "tag": "PID",
                "elements": ["F", "", "", "", line.item.description],
            })

        return segments

    def _scheme_to_n1_qualifier(self, scheme: str | None) -> str:
        """Map scheme ID to X12 N1*03 qualifier."""
        if not scheme:
            return "ZZ"
        reverse_map = {
            "DUNS": "1",
            "DUNS+4": "9",
            "SellerAssigned": "91",
            "BuyerAssigned": "92",
        }
        return reverse_map.get(scheme, "ZZ")
