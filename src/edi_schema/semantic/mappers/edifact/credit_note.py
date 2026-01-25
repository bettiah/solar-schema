"""
EDIFACT CREMUL Credit Memo Mapper.

Maps between EDIFACT CREMUL and semantic CreditNote model.
Note: CREMUL is a multiple credit advice message, but we map it to CreditNote.
"""

from typing import TYPE_CHECKING

from ...models import (
    Amount,
    CreditNote,
    CustomerParty,
    MonetaryTotal,
    Party,
    PartyName,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    format_edifact_date,
    get_element_value,
    parse_decimal,
    parse_edifact_date,
)

if TYPE_CHECKING:
    from edi_schema.edifact.ast import MessageInstance


class EdifactCreditNoteMapper(SemanticMapper[CreditNote]):
    """
    Maps EDIFACT CREMUL to/from semantic CreditNote model.

    EDIFACT CREMUL Structure:
    - BGM: Beginning of Message
    - DTM: Date/Time/Period
    - NAD: Name and Address
    - MOA: Monetary Amount
    """

    @property
    def semantic_type(self) -> type[CreditNote]:
        return CreditNote

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "CREMUL"

    def to_semantic(self, source: "MessageInstance") -> CreditNote:
        """Convert EDIFACT CREMUL to semantic CreditNote."""
        if source.message_type != "CREMUL":
            raise ValueError(f"Expected CREMUL, got {source.message_type}")

        # Find BGM segment
        bgm = None
        for seg in source.segments:
            if seg.tag == "BGM":
                bgm = seg
                break

        if not bgm:
            raise ValueError("Missing required BGM segment")

        doc_id = get_element_value(bgm, 2, 0) or ""

        # Find issue date
        issue_date = None
        for seg in source.segments:
            if seg.tag == "DTM":
                dtm_qual = get_element_value(seg, 1, 0)
                if dtm_qual == "137":
                    date_str = get_element_value(seg, 1, 1)
                    issue_date = parse_edifact_date(date_str)
                    break

        if not issue_date:
            from datetime import date

            issue_date = date.today()

        # Parse parties
        accounting_supplier_party = SupplierParty(party=Party())
        accounting_customer_party = CustomerParty(party=Party())

        for seg in source.segments:
            if seg.tag == "NAD":
                party_qual = get_element_value(seg, 1)
                party_name = get_element_value(seg, 4, 0)
                party = Party()
                if party_name:
                    party.party_names.append(PartyName(name=party_name))

                if party_qual in ("SE", "SU"):
                    accounting_supplier_party = SupplierParty(party=party)
                elif party_qual == "BY":
                    accounting_customer_party = CustomerParty(party=party)

        # Parse total amount
        total_amount = None
        for seg in source.segments:
            if seg.tag == "MOA":
                moa_qual = get_element_value(seg, 1, 0)
                if moa_qual in ("9", "86"):  # Amount due/Total
                    amount_val = parse_decimal(get_element_value(seg, 1, 1))
                    currency = get_element_value(seg, 1, 2) or "USD"
                    if amount_val:
                        total_amount = Amount(value=amount_val, currency=currency)
                    break

        credit_note = CreditNote(
            id=doc_id,
            issue_date=issue_date,
            document_currency_code=total_amount.currency if total_amount else "USD",
            accounting_supplier_party=accounting_supplier_party,
            accounting_customer_party=accounting_customer_party,
            legal_monetary_total=MonetaryTotal(payable_amount=total_amount),
            credit_note_lines=[],
        )

        credit_note._source_format = "edifact"
        credit_note._source_version = source.version
        return credit_note

    def from_semantic(self, model: CreditNote) -> object:
        """Convert semantic CreditNote to EDIFACT CREMUL."""
        segments = []

        # BGM segment
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"components": ["381"]},  # Credit note
                    {"components": [model.id]},
                    "9",  # Original
                ],
            }
        )

        # DTM segment
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

        # NAD segments
        if model.accounting_supplier_party and model.accounting_supplier_party.party.party_names:
            segments.append(
                {
                    "tag": "NAD",
                    "elements": [
                        "SU",
                        "",
                        "",
                        {"components": [model.accounting_supplier_party.party.party_names[0].name]},
                    ],
                }
            )

        if model.accounting_customer_party and model.accounting_customer_party.party.party_names:
            segments.append(
                {
                    "tag": "NAD",
                    "elements": [
                        "BY",
                        "",
                        "",
                        {"components": [model.accounting_customer_party.party.party_names[0].name]},
                    ],
                }
            )

        # MOA segment
        if model.legal_monetary_total and model.legal_monetary_total.payable_amount:
            segments.append(
                {
                    "tag": "MOA",
                    "elements": [
                        {
                            "components": [
                                "9",
                                str(model.legal_monetary_total.payable_amount.value),
                                model.legal_monetary_total.payable_amount.currency,
                            ]
                        },
                    ],
                }
            )

        return {"message_type": "CREMUL", "segments": segments}
