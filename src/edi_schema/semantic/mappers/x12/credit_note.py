"""
X12 812 Credit/Debit Adjustment Mapper.

Maps between X12 812 and semantic CreditNote model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    CreditNote,
    CreditNoteLine,
    CustomerParty,
    Identifier,
    Item,
    ItemIdentification,
    MonetaryTotal,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_loops,
    find_segment,
    find_segment_in_loop,
    get_element_value,
    map_id_qualifier,
    map_product_id_qualifier,
    parse_decimal,
    parse_x12_date,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, TransactionSetInstance


class X12CreditNoteMapper(SemanticMapper[CreditNote]):
    """
    Maps X12 812 Credit/Debit Adjustment to/from semantic CreditNote model.

    X12 812 Structure:
    - BCD: Beginning Credit/Debit Adjustment
    - CUR: Currency
    - REF: References
    - N1 Loop: Party Information
    - IT1 Loop: Line Items
    - TDS: Total Monetary Value Summary
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[CreditNote]:
        return CreditNote

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "812"

    def to_semantic(self, source: "TransactionSetInstance") -> CreditNote:
        """Convert X12 812 to semantic CreditNote."""
        if source.transaction_id != "812":
            raise ValueError(f"Expected 812, got {source.transaction_id}")

        content = source.content

        # Extract BCD segment (required)
        bcd = find_segment(content, "BCD")
        if not bcd:
            raise ValueError("Missing required BCD segment")

        # Parse basic fields
        doc_date = parse_x12_date(get_element_value(bcd, 1))  # BCD01 - Date
        credit_memo_number = get_element_value(bcd, 2)  # BCD02 - Credit/Debit Number
        invoice_number = get_element_value(bcd, 4)  # BCD04 - Invoice Number
        credit_debit_flag = get_element_value(bcd, 10)  # BCD10 - Credit/Debit Flag

        if not doc_date:
            raise ValueError("Missing or invalid date in BCD01")

        # Currency
        currency = "USD"
        cur = find_segment(content, "CUR")
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # Create credit note with required fields
        accounting_supplier_party = SupplierParty(party=Party())
        accounting_customer_party = CustomerParty(party=Party())
        legal_monetary_total = MonetaryTotal()
        credit_note_lines: list[CreditNoteLine] = []

        # Parse N1 loops for parties first
        for n1_loop in find_all_loops(content, "N1"):
            n1 = find_segment_in_loop(n1_loop, "N1")
            if not n1:
                continue
            party_code = get_element_value(n1, 1)
            party = self._build_party(n1_loop)

            if party_code in ("SE", "VN"):
                accounting_supplier_party = SupplierParty(party=party)
            elif party_code == "BY":
                accounting_customer_party = CustomerParty(party=party)

        # Parse IT1 loops for line items
        for it1_loop in find_all_loops(content, "IT1"):
            line = self._parse_line_item(it1_loop, currency)
            if line:
                credit_note_lines.append(line)

        # Parse TDS for totals
        tds = find_segment(content, "TDS")
        if tds:
            total_value = parse_decimal(get_element_value(tds, 1))
            if total_value:
                legal_monetary_total = MonetaryTotal(
                    payable_amount=Amount(value=total_value / 100, currency=currency)
                )

        # Create credit note
        credit_note = CreditNote(
            id=credit_memo_number or "",
            issue_date=doc_date,
            document_currency_code=currency,
            credit_note_type_code=credit_debit_flag,
            accounting_supplier_party=accounting_supplier_party,
            accounting_customer_party=accounting_customer_party,
            legal_monetary_total=legal_monetary_total,
            credit_note_lines=credit_note_lines,
        )

        # Set order reference if invoice number present
        if invoice_number:
            credit_note.billing_references = []
            from ...models import BillingReference, DocumentReference

            credit_note.billing_references.append(
                BillingReference(invoice_document_reference=DocumentReference(id=invoice_number))
            )

        # Parse CTT for line count
        ctt = find_segment(content, "CTT")
        if ctt:
            count = get_element_value(ctt, 1)
            if count:
                credit_note.line_count = int(count)

        credit_note._source_format = "x12"
        credit_note._source_version = source.version
        return credit_note

    def _build_party(self, loop: "LoopInstance") -> Party:
        """Build Party from N1 loop."""
        n1 = find_segment_in_loop(loop, "N1")
        n3 = find_segment_in_loop(loop, "N3")
        n4 = find_segment_in_loop(loop, "N4")

        party = Party()

        if n1:
            name = get_element_value(n1, 2)
            if name:
                party.party_names.append(PartyName(name=name))

            id_qual = get_element_value(n1, 3)
            id_val = get_element_value(n1, 4)
            if id_val:
                party.party_identifications.append(
                    PartyIdentification(
                        id=Identifier(
                            value=id_val,
                            scheme_id=map_id_qualifier(id_qual) if id_qual else None,
                        )
                    )
                )

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

    def _parse_line_item(self, loop: "LoopInstance", currency: str) -> CreditNoteLine | None:
        """Parse IT1 loop into CreditNoteLine."""
        it1 = find_segment_in_loop(loop, "IT1")
        if not it1:
            return None

        line_num = get_element_value(it1, 1) or "1"
        quantity = parse_decimal(get_element_value(it1, 2))
        unit_code = get_element_value(it1, 3) or "EA"
        unit_price = parse_decimal(get_element_value(it1, 4))

        # Build item
        item = Item()

        # Product IDs in IT1 (pairs at positions 6-7, 8-9, etc.)
        for i in range(6, 26, 2):
            qual = get_element_value(it1, i)
            val = get_element_value(it1, i + 1)
            if qual and val:
                self._set_item_id(item, qual, val)

        # PID segment for description
        pid = find_segment_in_loop(loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        # Calculate line extension amount
        line_amount = (quantity or Decimal("0")) * (unit_price or Decimal("0"))

        line = CreditNoteLine(
            id=line_num,
            credited_quantity=Quantity(value=quantity or Decimal("1"), unit_code=unit_code),
            line_extension_amount=Amount(value=line_amount, currency=currency),
            item=item,
        )

        if unit_price:
            line.price = Price(price_amount=Amount(value=unit_price, currency=currency))

        return line

    def _set_item_id(self, item: Item, qualifier: str, value: str) -> None:
        """Set item identifier based on X12 qualifier code."""
        scheme = map_product_id_qualifier(qualifier)
        identification = ItemIdentification(id=Identifier(value=value, scheme_id=scheme))

        if qualifier in ("UP", "EN", "UK"):
            item.standard_item_identification = identification
        elif qualifier in ("VP", "SK"):
            item.sellers_item_identification = identification
        elif qualifier in ("BP", "IN"):
            item.buyers_item_identification = identification
        elif qualifier == "MG":
            item.manufacturers_item_identification = identification

    def from_semantic(self, model: CreditNote) -> object:
        """Convert semantic CreditNote to X12 812."""
        segments = []

        # BCD segment
        bcd_elements = [
            model.issue_date.strftime("%Y%m%d"),  # BCD01 - Date
            model.id,  # BCD02 - Credit/Debit Number
        ]

        # Add invoice reference if available
        if model.billing_references:
            ref = model.billing_references[0]
            if ref.invoice_document_reference:
                bcd_elements.extend(["", ref.invoice_document_reference.id])
            else:
                bcd_elements.extend(["", ""])
        else:
            bcd_elements.extend(["", ""])

        # Padding and credit flag
        bcd_elements.extend(["", "", "", "", "", model.credit_note_type_code or "CR"])

        segments.append({"tag": "BCD", "elements": bcd_elements})

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append(
                {
                    "tag": "CUR",
                    "elements": ["SE", model.document_currency_code],
                }
            )

        # N1 loops for parties
        if model.accounting_supplier_party:
            segments.extend(self._build_party_segments("SE", model.accounting_supplier_party.party))
        if model.accounting_customer_party:
            segments.extend(self._build_party_segments("BY", model.accounting_customer_party.party))

        # IT1 loops for line items
        for line in model.credit_note_lines:
            segments.extend(self._build_line_segments(line, model.document_currency_code))

        # TDS segment for totals
        if model.legal_monetary_total and model.legal_monetary_total.payable_amount:
            # X12 amounts are often in cents
            total_cents = int(model.legal_monetary_total.payable_amount.value * 100)
            segments.append(
                {
                    "tag": "TDS",
                    "elements": [str(total_cents)],
                }
            )

        # CTT segment
        segments.append(
            {
                "tag": "CTT",
                "elements": [str(len(model.credit_note_lines))],
            }
        )

        return segments

    def _build_party_segments(self, code: str, party: Party) -> list[dict]:
        """Build N1/N3/N4 segments for a party."""
        segments = []

        n1_elements = [code]

        if party.party_names:
            n1_elements.append(party.party_names[0].name)
        else:
            n1_elements.append("")

        if party.party_identifications:
            pid = party.party_identifications[0]
            n1_elements.append(pid.id.scheme_id or "92")
            n1_elements.append(pid.id.value)

        segments.append({"tag": "N1", "elements": n1_elements})

        if party.postal_address:
            addr = party.postal_address
            if addr.street_name:
                segments.append(
                    {
                        "tag": "N3",
                        "elements": [
                            addr.street_name,
                            addr.additional_street_name or "",
                        ],
                    }
                )

            if addr.city_name or addr.country_subentity or addr.postal_zone:
                segments.append(
                    {
                        "tag": "N4",
                        "elements": [
                            addr.city_name or "",
                            addr.country_subentity or "",
                            addr.postal_zone or "",
                            addr.country_code or "",
                        ],
                    }
                )

        return segments

    def _build_line_segments(self, line: CreditNoteLine, currency: str) -> list[dict]:
        """Build IT1/PID segments for a line item."""
        segments = []

        it1_elements = [line.id]

        it1_elements.append(str(line.credited_quantity.value))
        it1_elements.append(line.credited_quantity.unit_code)

        if line.price:
            it1_elements.append(str(line.price.price_amount.value))
        else:
            it1_elements.append("")

        it1_elements.append("")  # IT105 - Basis of unit price

        # Add item IDs
        if line.item.standard_item_identification:
            scheme = line.item.standard_item_identification.id.scheme_id or "UP"
            it1_elements.extend([scheme, line.item.standard_item_identification.id.value])
        elif line.item.sellers_item_identification:
            it1_elements.extend(["VP", line.item.sellers_item_identification.id.value])
        elif line.item.buyers_item_identification:
            it1_elements.extend(["BP", line.item.buyers_item_identification.id.value])

        segments.append({"tag": "IT1", "elements": it1_elements})

        # PID segment for description
        if line.item.description:
            segments.append(
                {
                    "tag": "PID",
                    "elements": ["F", "", "", "", line.item.description],
                }
            )

        return segments
