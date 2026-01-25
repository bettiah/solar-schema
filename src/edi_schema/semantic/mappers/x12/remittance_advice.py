"""
X12 820 Payment Order/Remittance Advice Mapper.

Maps between X12 820 and semantic RemittanceAdvice model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    BillingReference,
    CustomerParty,
    DocumentReference,
    FinancialAccount,
    FinancialInstitution,
    FinancialInstitutionBranch,
    Identifier,
    Party,
    PartyIdentification,
    PartyName,
    PaymentMeans,
    RemittanceAdvice,
    RemittanceAdviceLine,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_loops,
    find_all_segments,
    find_segment,
    find_segment_in_loop,
    get_element_value,
    map_id_qualifier,
    parse_decimal,
    parse_x12_date,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, TransactionSetInstance


class X12RemittanceAdviceMapper(SemanticMapper[RemittanceAdvice]):
    """
    Maps X12 820 Payment Order/Remittance Advice to/from semantic RemittanceAdvice model.

    X12 820 Structure:
    - BPR: Beginning Segment for Payment Order/Remittance Advice
    - TRN: Trace Number
    - CUR: Currency
    - REF: References
    - DTM: Date/Time Reference
    - N1 Loop: Party Information (Payer, Payee, Financial Institutions)
    - ENT Loop: Entity (multiple payment details)
      - RMR: Remittance at Invoice Level
      - REF: References
      - DTM: Date/Time
      - ADX: Adjustment
    """

    @property
    def semantic_type(self) -> type[RemittanceAdvice]:
        return RemittanceAdvice

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "820"

    def to_semantic(self, source: "TransactionSetInstance") -> RemittanceAdvice:
        """Convert X12 820 to semantic RemittanceAdvice."""
        if source.transaction_id != "820":
            raise ValueError(f"Expected 820, got {source.transaction_id}")

        content = source.content

        # Extract BPR segment (required)
        bpr = find_segment(content, "BPR")
        if not bpr:
            raise ValueError("Missing required BPR segment")

        # Parse basic fields from BPR
        # BPR01 - Transaction Handling Code (not used yet)
        total_amount = parse_decimal(get_element_value(bpr, 2))  # BPR02 - Total Amount
        credit_debit_flag = get_element_value(bpr, 3)  # BPR03 - Credit/Debit Flag
        payment_method_code = get_element_value(bpr, 4)  # BPR04 - Payment Method Code
        payment_date = parse_x12_date(get_element_value(bpr, 16))  # BPR16 - Payment Date

        # TRN for trace number (remittance advice ID)
        trn = find_segment(content, "TRN")
        remittance_id = ""
        if trn:
            remittance_id = get_element_value(trn, 2) or ""

        # Currency
        currency = "USD"
        cur = find_segment(content, "CUR")
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # DTM for document date
        issue_date = payment_date
        dtm = find_segment(content, "DTM")
        if dtm:
            dtm_date = parse_x12_date(get_element_value(dtm, 2))
            if dtm_date:
                issue_date = dtm_date

        if not issue_date:
            from datetime import date

            issue_date = date.today()

        # Create remittance advice
        remittance = RemittanceAdvice(
            id=remittance_id,
            issue_date=issue_date,
            document_currency_code=currency,
            remittance_advice_lines=[],
        )

        # Set total amount
        if total_amount:
            if credit_debit_flag == "C":
                remittance.total_credit_amount = Amount(value=total_amount, currency=currency)
            else:
                remittance.total_debit_amount = Amount(value=total_amount, currency=currency)
            remittance.total_payment_amount = Amount(value=total_amount, currency=currency)

        # Parse N1 loops for parties
        for n1_loop in find_all_loops(content, "N1"):
            self._parse_party_loop(remittance, n1_loop)

        # Parse RMR segments for line items
        for rmr in find_all_segments(content, "RMR"):
            line = self._parse_rmr_segment(rmr, currency)
            if line:
                remittance.remittance_advice_lines.append(line)

        # Parse ENT loops if present (grouped remittance details)
        for ent_loop in find_all_loops(content, "ENT"):
            for rmr in find_all_segments(ent_loop.content, "RMR"):
                line = self._parse_rmr_segment(rmr, currency)
                if line:
                    remittance.remittance_advice_lines.append(line)

        # Set line count
        remittance.line_count = len(remittance.remittance_advice_lines)

        # Set payment means
        if payment_method_code:
            remittance.payment_means = PaymentMeans(payment_means_code=payment_method_code)

        remittance._source_format = "x12"
        remittance._source_version = source.version
        return remittance

    def _parse_party_loop(self, remittance: RemittanceAdvice, loop: "LoopInstance") -> None:
        """Parse N1 loop and add party to remittance."""
        n1 = find_segment_in_loop(loop, "N1")
        if not n1:
            return

        party_code = get_element_value(n1, 1)
        party = self._build_party(loop)

        if party_code == "PR":  # Payer
            remittance.accounting_customer_party = CustomerParty(party=party)
        elif party_code == "PE":  # Payee
            remittance.accounting_supplier_party = SupplierParty(party=party)
            remittance.payee_party = party
        elif party_code == "RB":  # Receiving Bank
            # Parse financial account from this loop
            remittance.payee_financial_account = self._build_financial_account(loop)
        elif party_code == "OB":  # Originating Bank
            remittance.payer_financial_account = self._build_financial_account(loop)

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

    def _build_financial_account(self, loop: "LoopInstance") -> FinancialAccount:
        """Build FinancialAccount from N1 loop (for bank information)."""
        n1 = find_segment_in_loop(loop, "N1")

        account = FinancialAccount()

        if n1:
            bank_name = get_element_value(n1, 2)
            id_qual = get_element_value(n1, 3)
            id_val = get_element_value(n1, 4)

            if id_val:
                # Check if this looks like a routing number
                if id_qual == "01":  # ABA Routing Number
                    account.financial_institution_branch = FinancialInstitutionBranch(
                        id=Identifier(value=id_val, scheme_id="ABA"),
                        financial_institution=FinancialInstitution(name=bank_name)
                        if bank_name
                        else None,
                    )
                else:
                    account.id = Identifier(value=id_val, scheme_id=id_qual)

        return account

    def _parse_rmr_segment(
        self, rmr: "ParsedSegment", currency: str
    ) -> RemittanceAdviceLine | None:
        """Parse RMR segment into RemittanceAdviceLine."""
        ref_id_qual = get_element_value(rmr, 1)  # RMR01 - Reference ID Qualifier
        ref_id = get_element_value(rmr, 2)  # RMR02 - Reference ID (Invoice #)
        # RMR03 - Payment Action Code (not used yet)
        amount = parse_decimal(get_element_value(rmr, 4))  # RMR04 - Amount Paid
        original_amount = parse_decimal(get_element_value(rmr, 5))  # RMR05 - Original Amount
        # RMR06 - Discount Taken (not used yet)

        if not ref_id:
            return None

        line = RemittanceAdviceLine(
            id=ref_id,
            invoicing_party_reference=ref_id if ref_id_qual == "IV" else None,
        )

        # Set billing reference
        if ref_id:
            line.billing_references.append(
                BillingReference(invoice_document_reference=DocumentReference(id=ref_id))
            )

        # Set amounts
        if amount:
            line.credit_line_amount = Amount(value=amount, currency=currency)

        if original_amount:
            line.debit_line_amount = Amount(value=original_amount, currency=currency)

        # Calculate balance if we have original and paid
        if original_amount and amount:
            balance = original_amount - amount
            if balance != 0:
                line.balance_amount = Amount(value=balance, currency=currency)

        return line

    def from_semantic(self, model: RemittanceAdvice) -> object:
        """Convert semantic RemittanceAdvice to X12 820."""
        segments = []

        # Determine total amount and credit/debit flag
        total_amount = model.total_payment_amount or model.total_credit_amount
        credit_debit_flag = "C" if model.total_credit_amount else "D"

        # BPR segment
        bpr_elements = [
            "C",  # BPR01 - Transaction Handling Code (Payment)
            str(total_amount.value) if total_amount else "0",  # BPR02 - Total Amount
            credit_debit_flag,  # BPR03 - Credit/Debit Flag
            model.payment_means.payment_means_code if model.payment_means else "ACH",  # BPR04
            "",  # BPR05-15 padding
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            model.issue_date.strftime("%Y%m%d"),  # BPR16 - Payment Date
        ]
        segments.append({"tag": "BPR", "elements": bpr_elements})

        # TRN segment
        segments.append(
            {
                "tag": "TRN",
                "elements": [
                    "1",  # TRN01 - Trace Type Code
                    model.id,  # TRN02 - Reference Identification
                ],
            }
        )

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append(
                {
                    "tag": "CUR",
                    "elements": ["PR", model.document_currency_code],
                }
            )

        # N1 loops for parties
        if model.accounting_customer_party:
            segments.extend(self._build_party_segments("PR", model.accounting_customer_party.party))
        if model.payee_party:
            segments.extend(self._build_party_segments("PE", model.payee_party))
        elif model.accounting_supplier_party:
            segments.extend(self._build_party_segments("PE", model.accounting_supplier_party.party))

        # RMR segments for line items
        for line in model.remittance_advice_lines:
            segments.extend(self._build_rmr_segment(line))

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

    def _build_rmr_segment(self, line: RemittanceAdviceLine) -> list[dict]:
        """Build RMR segment for a remittance line."""
        segments = []

        # Get invoice reference
        invoice_ref = ""
        if line.billing_references:
            ref = line.billing_references[0]
            if ref.invoice_document_reference:
                invoice_ref = ref.invoice_document_reference.id
        if not invoice_ref:
            invoice_ref = line.invoicing_party_reference or line.id

        rmr_elements = [
            "IV",  # RMR01 - Reference ID Qualifier (Invoice)
            invoice_ref,  # RMR02 - Reference ID
            "PA",  # RMR03 - Payment Action Code (Payment)
        ]

        # Add amounts
        if line.credit_line_amount:
            rmr_elements.append(str(line.credit_line_amount.value))
        else:
            rmr_elements.append("")

        if line.debit_line_amount:
            rmr_elements.append(str(line.debit_line_amount.value))
        else:
            rmr_elements.append("")

        segments.append({"tag": "RMR", "elements": rmr_elements})

        return segments
