"""
EDIFACT Invoice Mapper.

Maps between EDIFACT INVOIC and semantic Invoice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    Contact,
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
    PartyLegalEntity,
    PartyName,
    PaymentMeans,
    Price,
    Quantity,
    SupplierParty,
    TaxCategory,
    TaxSubtotal,
    TaxTotal,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_segment_groups,
    find_all_segments,
    find_all_segments_in_group,
    find_segment,
    find_segment_in_group,
    format_edifact_date,
    get_component_value,
    get_dtm_date,
    get_element_value,
    map_nad_party_qualifier,
    map_product_id_qualifier,
    parse_decimal,
)

if TYPE_CHECKING:
    from edi_schema.edifact.ast import (
        MessageInstance,
        ParsedSegment,
        SegmentGroupInstance,
    )


class EdifactInvoiceMapper(SemanticMapper[Invoice]):
    """
    Maps EDIFACT INVOIC to/from semantic Invoice model.

    EDIFACT INVOIC Structure:
    - UNH: Message header
    - BGM: Beginning of message (document type/ID)
    - DTM: Date/time (137=document date, 35=delivery date)
    - PAI: Payment instructions
    - FTX: Free text
    - SG1: Reference segment group (RFF+DTM) - order/contract refs
    - SG2: Party segment group (NAD+LOC+FII+SG3+SG4+SG5)
    - SG7: Currency segment group (CUX)
    - SG8: Payment terms (PAT+DTM+PCD+MOA)
    - SG25: Line item segment group (LIN+PIA+IMD+MEA+QTY+ALI+DTM+MOA+SG26+...)
    - UNS: Section control
    - MOA: Monetary amounts (total amounts)
    - TAX: Tax details
    - UNT: Message trailer
    """

    @property
    def semantic_type(self) -> type[Invoice]:
        return Invoice

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "INVOIC"

    def to_semantic(self, source: "MessageInstance") -> Invoice:
        """Convert EDIFACT INVOIC to semantic Invoice."""
        if source.message_type != "INVOIC":
            raise ValueError(f"Expected INVOIC, got {source.message_type}")

        content = source.content

        # Parse BGM segment for document ID
        bgm = find_segment(content, "BGM")
        if not bgm:
            raise ValueError("Missing required BGM segment")

        invoice_id = get_component_value(bgm, 2, 1) or ""
        invoice_type = get_component_value(bgm, 1, 1)

        # Parse DTM for issue date
        issue_date = get_dtm_date(content, "137")
        if not issue_date:
            raise ValueError("Missing document date (DTM+137)")

        # Parse CUX for currency
        currency = "USD"
        for sg7 in find_all_segment_groups(content, 7):
            cux = find_segment_in_group(sg7, "CUX")
            if cux:
                currency = get_component_value(cux, 1, 2) or "USD"
                break

        cux = find_segment(content, "CUX")
        if cux:
            currency = get_component_value(cux, 1, 2) or currency

        # Parse due date (DTM qualifier 13)
        due_date = get_dtm_date(content, "13")

        # Parse FTX for notes
        notes = []
        for ftx in find_all_segments(content, "FTX"):
            text = get_element_value(ftx, 4)
            if text:
                notes.append(text)

        # Parse references from SG1 groups
        order_reference = None
        for sg1 in find_all_segment_groups(content, 1):
            rff = find_segment_in_group(sg1, "RFF")
            if rff:
                ref_qualifier = get_component_value(rff, 1, 1)
                ref_value = get_component_value(rff, 1, 2)
                if ref_qualifier == "ON" and ref_value:
                    order_reference = OrderReference(id=ref_value)

        # Parse parties from SG2 groups
        accounting_supplier_party = None
        accounting_customer_party = None
        for sg2 in find_all_segment_groups(content, 2):
            nad = find_segment_in_group(sg2, "NAD")
            if nad:
                party_qualifier = get_element_value(nad, 1)
                party = self._build_party_from_nad(nad, sg2)

                role = map_nad_party_qualifier(party_qualifier or "")
                if role in ("supplier", "seller"):
                    accounting_supplier_party = SupplierParty(party=party)
                elif role in ("buyer", "invoicee"):
                    accounting_customer_party = CustomerParty(party=party)

        # Parse payment means from PAI
        payment_means = []
        pai = find_segment(content, "PAI")
        if pai:
            pay_code = get_component_value(pai, 1, 3)
            if pay_code:
                payment_means.append(PaymentMeans(payment_means_code=pay_code))

        # Also check for payment means in SG8
        for sg8 in find_all_segment_groups(content, 8):
            pat = find_segment_in_group(sg8, "PAT")
            if pat:
                # Payment terms notes can be extracted here from element 1
                pass

        # Parse line items from SG25/SG26 groups
        invoice_lines = []
        line_groups = find_all_segment_groups(content, 25)
        if not line_groups:
            line_groups = find_all_segment_groups(content, 26)

        for i, lin_group in enumerate(line_groups, 1):
            line = self._parse_line_group(lin_group, str(i), currency)
            invoice_lines.append(line)

        # Parse summary MOA segments
        legal_monetary_total = self._parse_monetary_totals(content, currency)

        # Parse TAX segments for tax totals
        tax_total_list = []
        tax_total_item = self._parse_tax_totals(content, currency)
        if tax_total_item:
            tax_total_list.append(tax_total_item)

        # Ensure required fields have defaults if not found
        if not accounting_supplier_party:
            accounting_supplier_party = SupplierParty(party=Party())
        if not accounting_customer_party:
            accounting_customer_party = CustomerParty(party=Party())

        # Create invoice with all required fields
        invoice = Invoice(
            id=invoice_id,
            issue_date=issue_date,
            document_currency_code=currency,
            invoice_type_code=invoice_type,
            due_date=due_date,
            note=notes,
            order_reference=order_reference,
            accounting_supplier_party=accounting_supplier_party,
            accounting_customer_party=accounting_customer_party,
            payment_means=payment_means,
            invoice_lines=invoice_lines,
            legal_monetary_total=legal_monetary_total,
            tax_total=tax_total_list,
            line_count=len(invoice_lines),
        )

        # Source tracking
        invoice._source_format = "edifact"
        invoice._source_version = f"{source.version}{source.release}"

        return invoice

    def from_semantic(self, model: Invoice) -> dict:
        """Convert semantic Invoice to EDIFACT INVOIC structure."""
        segments = []

        # BGM - Beginning of message
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"value": model.invoice_type_code or "380"},  # Commercial invoice
                    {"components": [model.id]},
                    "9",  # Original
                ],
            }
        )

        # DTM - Document date
        segments.append(
            {
                "tag": "DTM",
                "elements": [
                    {
                        "components": [
                            "137",
                            format_edifact_date(model.issue_date),
                            "102",
                        ]
                    },
                ],
            }
        )

        # DTM - Due date
        if model.due_date:
            segments.append(
                {
                    "tag": "DTM",
                    "elements": [
                        {
                            "components": [
                                "13",  # Due date
                                format_edifact_date(model.due_date),
                                "102",
                            ]
                        },
                    ],
                }
            )

        # RFF - Order reference
        if model.order_reference:
            segments.append(
                {
                    "tag": "RFF",
                    "elements": [
                        {"components": ["ON", model.order_reference.id]},
                    ],
                }
            )

        # CUX - Currency
        if model.document_currency_code:
            segments.append(
                {
                    "tag": "CUX",
                    "elements": [
                        {
                            "components": [
                                "2",
                                model.document_currency_code,
                                "4",
                            ]
                        },
                    ],
                }
            )

        # NAD - Supplier
        if model.accounting_supplier_party:
            segments.extend(self._build_nad_segments("SU", model.accounting_supplier_party.party))

        # NAD - Customer
        if model.accounting_customer_party:
            segments.extend(self._build_nad_segments("BY", model.accounting_customer_party.party))

        # LIN groups - Line items
        for i, line in enumerate(model.invoice_lines, 1):
            segments.extend(self._build_line_segments(line, i, model.document_currency_code))

        # UNS - Section control
        segments.append({"tag": "UNS", "elements": ["S"]})

        # MOA - Totals
        if model.legal_monetary_total:
            lmt = model.legal_monetary_total
            if lmt.line_extension_amount:
                segments.append(
                    {
                        "tag": "MOA",
                        "elements": [
                            {
                                "components": [
                                    "79",  # Total line items amount
                                    str(lmt.line_extension_amount.value),
                                ]
                            },
                        ],
                    }
                )
            if lmt.tax_exclusive_amount:
                segments.append(
                    {
                        "tag": "MOA",
                        "elements": [
                            {
                                "components": [
                                    "125",  # Taxable amount
                                    str(lmt.tax_exclusive_amount.value),
                                ]
                            },
                        ],
                    }
                )
            if lmt.payable_amount:
                segments.append(
                    {
                        "tag": "MOA",
                        "elements": [
                            {
                                "components": [
                                    "9",  # Amount due
                                    str(lmt.payable_amount.value),
                                ]
                            },
                        ],
                    }
                )

        # TAX - Tax totals
        for tax_total in model.tax_total:
            if tax_total.tax_amount:
                segments.append(
                    {
                        "tag": "TAX",
                        "elements": [
                            "7",  # Tax
                            "VAT",  # Value added tax
                        ],
                    }
                )
                segments.append(
                    {
                        "tag": "MOA",
                        "elements": [
                            {"components": ["124", str(tax_total.tax_amount.value)]},
                        ],
                    }
                )

        # CNT - Control total
        segments.append(
            {
                "tag": "CNT",
                "elements": [
                    {"components": ["2", str(len(model.invoice_lines))]},
                ],
            }
        )

        return {"message_type": "INVOIC", "segments": segments}

    def _build_party_from_nad(self, nad: "ParsedSegment", group: "SegmentGroupInstance") -> Party:
        """Build Party from NAD segment and its group."""
        party = Party()

        # Party identification from NAD C082
        party_id = get_component_value(nad, 2, 1)
        party_id_qualifier = get_component_value(nad, 2, 3)
        if party_id:
            party.party_identifications.append(
                PartyIdentification(id=Identifier(value=party_id, scheme_id=party_id_qualifier))
            )

        # Party name from NAD C080
        party_name = get_component_value(nad, 3, 1)
        if not party_name:
            party_name = get_element_value(nad, 4)
        if party_name:
            party.party_names.append(PartyName(name=party_name))

        # Legal entity from RFF in nested groups
        for child in group.children:
            rff = find_segment_in_group(child, "RFF")
            if rff:
                ref_qual = get_component_value(rff, 1, 1)
                ref_val = get_component_value(rff, 1, 2)
                if ref_qual in ("VA", "FC") and ref_val:
                    # VAT number or company registration
                    party.party_legal_entity = PartyLegalEntity(
                        company_id=Identifier(value=ref_val, scheme_id=ref_qual)
                    )

        # Address from NAD elements 5-9
        street = get_component_value(nad, 5, 1)
        city = get_element_value(nad, 6)
        country_sub = get_element_value(nad, 7)
        postal = get_element_value(nad, 8)
        country = get_element_value(nad, 9)

        if any([street, city, country_sub, postal, country]):
            party.postal_address = Address(
                street_name=street,
                city_name=city,
                country_subentity=country_sub,
                postal_zone=postal,
                country_code=country,
            )

        # Contact from CTA/COM
        for child in group.children:
            cta = find_segment_in_group(child, "CTA")
            if cta:
                contact_name = get_component_value(cta, 2, 2)
                com = find_segment_in_group(child, "COM")
                phone = None
                email = None
                if com:
                    comm_number = get_component_value(com, 1, 1)
                    comm_type = get_component_value(com, 1, 2)
                    if comm_type == "TE":
                        phone = comm_number
                    elif comm_type == "EM":
                        email = comm_number

                if contact_name or phone or email:
                    party.contact = Contact(
                        name=contact_name,
                        telephone=phone,
                        electronic_mail=email,
                    )
                break

        return party

    def _parse_line_group(
        self,
        group: "SegmentGroupInstance",
        line_id: str,
        currency: str,
    ) -> InvoiceLine:
        """Parse a line item group into InvoiceLine."""
        lin = find_segment_in_group(group, "LIN")

        # Line ID from LIN
        line_number = get_element_value(lin, 1) if lin else line_id

        # Item from LIN C212 and PIA
        item = self._build_item_from_group(group)

        # Quantity from QTY
        qty = Quantity(value=Decimal("1"), unit_code="EA")
        for qty_seg in find_all_segments_in_group(group, "QTY"):
            qty_qualifier = get_component_value(qty_seg, 1, 1)
            if qty_qualifier in ("47", "46"):  # Invoiced qty
                qty_value = get_component_value(qty_seg, 1, 2)
                qty_unit = get_component_value(qty_seg, 1, 3)
                if qty_value:
                    qty = Quantity(
                        value=parse_decimal(qty_value) or Decimal("1"),
                        unit_code=qty_unit or "EA",
                    )
                break

        # Price from nested PRI group (SG29)
        price = None
        for child in group.children:
            if child.group_number == 29:
                pri = find_segment_in_group(child, "PRI")
                if pri:
                    price_val = get_component_value(pri, 1, 2)
                    if price_val:
                        price = Price(
                            price_amount=Amount(
                                value=parse_decimal(price_val) or Decimal("0"),
                                currency=currency,
                            )
                        )
                break

        # Line amount from MOA
        line_extension_amount = Amount(value=Decimal("0"), currency=currency)
        for moa in find_all_segments_in_group(group, "MOA"):
            moa_qualifier = get_component_value(moa, 1, 1)
            if moa_qualifier in ("203", "66"):
                amount_val = get_component_value(moa, 1, 2)
                if amount_val:
                    line_extension_amount = Amount(
                        value=parse_decimal(amount_val) or Decimal("0"),
                        currency=currency,
                    )
                break

        line = InvoiceLine(
            id=line_number or line_id,
            invoiced_quantity=qty,
            item=item,
            price=price,
            line_extension_amount=line_extension_amount,
        )

        return line

    def _build_item_from_group(self, group: "SegmentGroupInstance") -> Item:
        """Build Item from LIN, PIA, IMD segments."""
        item = Item()

        lin = find_segment_in_group(group, "LIN")

        # Standard item ID from LIN C212
        if lin:
            item_id = get_component_value(lin, 3, 1)
            item_id_type = get_component_value(lin, 3, 2)
            if item_id:
                field_type, scheme = map_product_id_qualifier(item_id_type or "")
                ident = ItemIdentification(id=Identifier(value=item_id, scheme_id=scheme))
                if field_type == "standard":
                    item.standard_item_identification = ident
                elif field_type == "sellers":
                    item.sellers_item_identification = ident
                elif field_type == "buyers":
                    item.buyers_item_identification = ident

        # Additional IDs from PIA
        for pia in find_all_segments_in_group(group, "PIA"):
            pia_id = get_component_value(pia, 2, 1)
            pia_type = get_component_value(pia, 2, 2)
            if pia_id:
                field_type, scheme = map_product_id_qualifier(pia_type or "")
                ident = ItemIdentification(id=Identifier(value=pia_id, scheme_id=scheme))
                if field_type == "standard" and not item.standard_item_identification:
                    item.standard_item_identification = ident
                elif field_type == "sellers" and not item.sellers_item_identification:
                    item.sellers_item_identification = ident
                elif field_type == "buyers" and not item.buyers_item_identification:
                    item.buyers_item_identification = ident

        # Description from IMD
        for imd in find_all_segments_in_group(group, "IMD"):
            description = get_component_value(imd, 3, 4)
            if not description:
                description = get_component_value(imd, 3, 5)
            if description:
                item.description = description
                break

        return item

    def _parse_monetary_totals(self, content: list, currency: str) -> MonetaryTotal:
        """Parse summary MOA segments into MonetaryTotal."""
        totals = MonetaryTotal()

        for moa in find_all_segments(content, "MOA"):
            qualifier = get_component_value(moa, 1, 1)
            amount_val = get_component_value(moa, 1, 2)

            if not amount_val:
                continue

            amount = Amount(
                value=parse_decimal(amount_val) or Decimal("0"),
                currency=currency,
            )

            if qualifier == "79":  # Total line items amount
                totals.line_extension_amount = amount
            elif qualifier == "125":  # Taxable amount
                totals.tax_exclusive_amount = amount
            elif qualifier == "176":  # Total tax amount
                pass  # Goes in tax_totals
            elif qualifier == "9":  # Amount due
                totals.payable_amount = amount
            elif qualifier == "86":  # Total amount
                totals.tax_inclusive_amount = amount

        return totals

    def _parse_tax_totals(self, content: list, currency: str) -> TaxTotal | None:
        """Parse TAX and MOA segments into TaxTotal."""
        tax_amount = None
        tax_subtotals = []

        # Look for tax MOA (qualifier 176)
        for moa in find_all_segments(content, "MOA"):
            qualifier = get_component_value(moa, 1, 1)
            if qualifier == "176":
                amount_val = get_component_value(moa, 1, 2)
                if amount_val:
                    tax_amount = Amount(
                        value=parse_decimal(amount_val) or Decimal("0"),
                        currency=currency,
                    )
                break

        # Parse TAX segments
        for tax_seg in find_all_segments(content, "TAX"):
            tax_type = get_element_value(tax_seg, 2)
            tax_rate = get_component_value(tax_seg, 5, 4)

            if tax_rate:
                subtotal = TaxSubtotal(
                    tax_category=TaxCategory(
                        id=tax_type or "VAT",
                        percent=parse_decimal(tax_rate),
                    )
                )
                tax_subtotals.append(subtotal)

        if tax_amount or tax_subtotals:
            return TaxTotal(
                tax_amount=tax_amount,
                tax_subtotals=tax_subtotals,
            )

        return None

    def _build_nad_segments(self, qualifier: str, party: Party) -> list[dict]:
        """Build NAD segment(s) for a party."""
        segments = []

        elements = [qualifier]

        # C082 - Party identification
        if party.party_identifications:
            pi = party.party_identifications[0]
            elements.append(
                {
                    "components": [
                        pi.id.value,
                        "",
                        pi.id.scheme_id or "92",
                    ],
                }
            )
        else:
            elements.append("")

        # C080 - Party name
        if party.party_names:
            elements.append({"components": [party.party_names[0].name]})
        else:
            elements.append("")

        # C059 - Street (4)
        elements.append("")

        # Address elements
        if party.postal_address:
            addr = party.postal_address
            elements.append({"components": [addr.street_name or ""]})
            elements.append(addr.city_name or "")
            elements.append(addr.country_subentity or "")
            elements.append(addr.postal_zone or "")
            elements.append(addr.country_code or "")
        else:
            elements.extend(["", "", "", "", ""])

        segments.append({"tag": "NAD", "elements": elements})

        # RFF for legal entity (VAT number)
        if party.party_legal_entity and party.party_legal_entity.company_id:
            legal = party.party_legal_entity
            segments.append(
                {
                    "tag": "RFF",
                    "elements": [
                        {
                            "components": [
                                legal.company_id.scheme_id or "VA",
                                legal.company_id.value,
                            ]
                        },
                    ],
                }
            )

        return segments

    def _build_line_segments(self, line: InvoiceLine, line_num: int, currency: str) -> list[dict]:
        """Build segment dicts for a line item."""
        segments = []

        # LIN - Line item
        lin_elements = [
            str(line_num),
            "",
        ]

        # C212 - Item number
        if line.item.standard_item_identification:
            si = line.item.standard_item_identification
            lin_elements.append(
                {
                    "components": [
                        si.id.value,
                        "EN" if si.id.scheme_id == "EAN" else "SA",
                    ],
                }
            )
        elif line.item.sellers_item_identification:
            si = line.item.sellers_item_identification
            lin_elements.append(
                {
                    "components": [si.id.value, "SA"],
                }
            )
        else:
            lin_elements.append("")

        segments.append({"tag": "LIN", "elements": lin_elements})

        # IMD - Item description
        if line.item.description:
            segments.append(
                {
                    "tag": "IMD",
                    "elements": [
                        "F",
                        "",
                        {"components": ["", "", "", line.item.description]},
                    ],
                }
            )

        # QTY - Quantity
        segments.append(
            {
                "tag": "QTY",
                "elements": [
                    {
                        "components": [
                            "47",  # Invoiced quantity
                            str(line.invoiced_quantity.value),
                            line.invoiced_quantity.unit_code,
                        ]
                    },
                ],
            }
        )

        # PRI - Price
        if line.price:
            segments.append(
                {
                    "tag": "PRI",
                    "elements": [
                        {
                            "components": [
                                "AAA",
                                str(line.price.price_amount.value),
                            ]
                        },
                    ],
                }
            )

        # MOA - Line amount
        if line.line_extension_amount:
            segments.append(
                {
                    "tag": "MOA",
                    "elements": [
                        {
                            "components": [
                                "203",
                                str(line.line_extension_amount.value),
                            ]
                        },
                    ],
                }
            )

        return segments
