"""
EDIFACT REMADV Remittance Advice Mapper.

Maps between EDIFACT REMADV and semantic RemittanceAdvice model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Amount,
    BillingReference,
    CustomerParty,
    DocumentReference,
    Identifier,
    Party,
    PartyIdentification,
    PartyName,
    RemittanceAdvice,
    RemittanceAdviceLine,
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


class EdifactRemittanceAdviceMapper(SemanticMapper[RemittanceAdvice]):
    """
    Maps EDIFACT REMADV to/from semantic RemittanceAdvice model.

    EDIFACT REMADV Structure:
    - BGM: Beginning of Message
    - DTM: Date/Time/Period
    - NAD: Name and Address (payer, payee)
    - DOC: Document details (invoices being paid)
    - MOA: Monetary Amount
    """

    @property
    def semantic_type(self) -> type[RemittanceAdvice]:
        return RemittanceAdvice

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "REMADV"

    def to_semantic(self, source: "MessageInstance") -> RemittanceAdvice:
        """Convert EDIFACT REMADV to semantic RemittanceAdvice."""
        if source.message_type != "REMADV":
            raise ValueError(f"Expected REMADV, got {source.message_type}")

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

        # Create remittance advice
        remittance = RemittanceAdvice(
            id=doc_id,
            issue_date=issue_date,
            document_currency_code="USD",
            remittance_advice_lines=[],
        )

        # Parse parties from NAD
        for seg in source.segments:
            if seg.tag == "NAD":
                party_qual = get_element_value(seg, 1)
                party_name = get_element_value(seg, 4, 0)
                party_id = get_element_value(seg, 2, 0)

                party = Party()
                if party_name:
                    party.party_names.append(PartyName(name=party_name))
                if party_id:
                    party.party_identifications.append(
                        PartyIdentification(id=Identifier(value=party_id))
                    )

                if party_qual == "PR":  # Payer
                    remittance.accounting_customer_party = CustomerParty(party=party)
                elif party_qual == "PE":  # Payee
                    remittance.accounting_supplier_party = SupplierParty(party=party)
                    remittance.payee_party = party

        # Parse total amount from MOA
        for seg in source.segments:
            if seg.tag == "MOA":
                moa_qual = get_element_value(seg, 1, 0)
                if moa_qual in ("9", "12"):  # Amount due/Total payment
                    amount_val = parse_decimal(get_element_value(seg, 1, 1))
                    currency = get_element_value(seg, 1, 2) or "USD"
                    if amount_val:
                        remittance.total_payment_amount = Amount(
                            value=amount_val, currency=currency
                        )
                        remittance.document_currency_code = currency
                    break

        # Parse DOC segments for remittance lines
        line_num = 1
        for seg in source.segments:
            if seg.tag == "DOC":
                invoice_id = get_element_value(seg, 2, 0)
                if invoice_id:
                    line = RemittanceAdviceLine(
                        id=str(line_num),
                        invoicing_party_reference=invoice_id,
                        billing_references=[
                            BillingReference(
                                invoice_document_reference=DocumentReference(id=invoice_id)
                            )
                        ],
                    )
                    remittance.remittance_advice_lines.append(line)
                    line_num += 1

        remittance.line_count = len(remittance.remittance_advice_lines)

        remittance._source_format = "edifact"
        remittance._source_version = source.version
        return remittance

    def from_semantic(self, model: RemittanceAdvice) -> object:
        """Convert semantic RemittanceAdvice to EDIFACT REMADV."""
        segments = []

        # BGM segment
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"components": ["481"]},  # Remittance advice
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

        # NAD segments for parties
        if model.accounting_customer_party:
            party = model.accounting_customer_party.party
            nad_elements = ["PR"]
            if party.party_identifications:
                nad_elements.append({"components": [party.party_identifications[0].id.value]})
            else:
                nad_elements.append("")
            nad_elements.append("")
            if party.party_names:
                nad_elements.append({"components": [party.party_names[0].name]})
            else:
                nad_elements.append("")
            segments.append({"tag": "NAD", "elements": nad_elements})

        if model.payee_party:
            party = model.payee_party
            nad_elements = ["PE"]
            if party.party_identifications:
                nad_elements.append({"components": [party.party_identifications[0].id.value]})
            else:
                nad_elements.append("")
            nad_elements.append("")
            if party.party_names:
                nad_elements.append({"components": [party.party_names[0].name]})
            else:
                nad_elements.append("")
            segments.append({"tag": "NAD", "elements": nad_elements})
        elif model.accounting_supplier_party:
            party = model.accounting_supplier_party.party
            nad_elements = ["PE"]
            if party.party_identifications:
                nad_elements.append({"components": [party.party_identifications[0].id.value]})
            else:
                nad_elements.append("")
            nad_elements.append("")
            if party.party_names:
                nad_elements.append({"components": [party.party_names[0].name]})
            else:
                nad_elements.append("")
            segments.append({"tag": "NAD", "elements": nad_elements})

        # MOA segment for total
        if model.total_payment_amount:
            segments.append(
                {
                    "tag": "MOA",
                    "elements": [
                        {
                            "components": [
                                "12",  # Total payment amount
                                str(model.total_payment_amount.value),
                                model.total_payment_amount.currency,
                            ]
                        },
                    ],
                }
            )

        # DOC segments for lines
        for line in model.remittance_advice_lines:
            invoice_ref = line.invoicing_party_reference
            if not invoice_ref and line.billing_references:
                ref = line.billing_references[0]
                if ref.invoice_document_reference:
                    invoice_ref = ref.invoice_document_reference.id
            if invoice_ref:
                segments.append(
                    {
                        "tag": "DOC",
                        "elements": [
                            {"components": ["380"]},  # Invoice
                            {"components": [invoice_ref]},
                        ],
                    }
                )

        return {"message_type": "REMADV", "segments": segments}
