"""
EDIFACT ORDRSP Order Response Mapper.

Maps between EDIFACT ORDRSP and semantic OrderResponse model.
"""

from typing import TYPE_CHECKING

from ...models import (
    CustomerParty,
    Identifier,
    OrderReference,
    OrderResponse,
    Party,
    PartyIdentification,
    PartyName,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    format_edifact_date,
    get_element_value,
    parse_edifact_date,
)

if TYPE_CHECKING:
    from edi_schema.edifact.ast import MessageInstance, ParsedSegment


class EdifactOrderResponseMapper(SemanticMapper[OrderResponse]):
    """
    Maps EDIFACT ORDRSP to/from semantic OrderResponse model.

    EDIFACT ORDRSP Structure:
    - BGM: Beginning of Message (document number, function)
    - DTM: Date/Time/Period (issue date)
    - RFF: References (original order number)
    - NAD: Name and Address (parties)
    - LIN: Line Item
    """

    @property
    def semantic_type(self) -> type[OrderResponse]:
        return OrderResponse

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "ORDRSP"

    def to_semantic(self, source: "MessageInstance") -> OrderResponse:
        """Convert EDIFACT ORDRSP to semantic OrderResponse."""
        if source.message_type != "ORDRSP":
            raise ValueError(f"Expected ORDRSP, got {source.message_type}")

        # Find BGM segment
        bgm = None
        for seg in source.segments:
            if seg.tag == "BGM":
                bgm = seg
                break

        if not bgm:
            raise ValueError("Missing required BGM segment")

        # Parse document ID and response code
        doc_id = get_element_value(bgm, 2, 0)  # C106.1004
        response_code = get_element_value(bgm, 3)  # BGM03

        # Find issue date from DTM
        issue_date = None
        for seg in source.segments:
            if seg.tag == "DTM":
                dtm_qual = get_element_value(seg, 1, 0)  # C507.2005
                if dtm_qual == "137":  # Document date
                    date_str = get_element_value(seg, 1, 1)  # C507.2380
                    issue_date = parse_edifact_date(date_str)
                    break

        if not issue_date:
            from datetime import date

            issue_date = date.today()

        # Find order reference from RFF
        order_reference = None
        for seg in source.segments:
            if seg.tag == "RFF":
                ref_qual = get_element_value(seg, 1, 0)  # C506.1153
                if ref_qual == "ON":  # Order number
                    ref_id = get_element_value(seg, 1, 1)  # C506.1154
                    if ref_id:
                        order_reference = OrderReference(id=ref_id)
                    break

        # Create response
        response = OrderResponse(
            id=doc_id or "",
            issue_date=issue_date,
            document_currency_code="USD",
            order_response_code=response_code,
            order_reference=order_reference,
            order_lines=[],
        )

        # Parse parties from NAD segments
        for group in source.segment_groups:
            if group.definition and "NAD" in group.definition.tag:
                for seg in group.segments:
                    if seg.tag == "NAD":
                        self._parse_nad_segment(response, seg)

        response._source_format = "edifact"
        response._source_version = source.version
        return response

    def _parse_nad_segment(self, response: OrderResponse, nad: "ParsedSegment") -> None:
        """Parse NAD segment and add party to response."""
        party_qual = get_element_value(nad, 1)  # NAD01
        party_id = get_element_value(nad, 2, 0)  # C082.3039
        party_name = get_element_value(nad, 4, 0)  # C080.3036

        party = Party()
        if party_name:
            party.party_names.append(PartyName(name=party_name))
        if party_id:
            party.party_identifications.append(PartyIdentification(id=Identifier(value=party_id)))

        if party_qual == "BY":
            response.buyer_customer_party = CustomerParty(party=party)
        elif party_qual in ("SE", "SU"):
            response.seller_supplier_party = SupplierParty(party=party)

    def from_semantic(self, model: OrderResponse) -> object:
        """Convert semantic OrderResponse to EDIFACT ORDRSP."""
        segments = []

        # BGM segment
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"components": ["231"]},  # C002.1001 - Order response
                    {"components": [model.id]},  # C106.1004
                    model.order_response_code or "29",  # BGM03 - Accepted
                ],
            }
        )

        # DTM segment - Document date
        segments.append(
            {
                "tag": "DTM",
                "elements": [
                    {
                        "components": [
                            "137",  # Document date
                            format_edifact_date(model.issue_date),
                            "102",
                        ]
                    },
                ],
            }
        )

        # RFF segment - Order reference
        if model.order_reference:
            segments.append(
                {
                    "tag": "RFF",
                    "elements": [
                        {"components": ["ON", model.order_reference.id]},
                    ],
                }
            )

        # NAD segments for parties
        if model.seller_supplier_party:
            segments.append(self._build_nad_segment("SU", model.seller_supplier_party.party))
        if model.buyer_customer_party:
            segments.append(self._build_nad_segment("BY", model.buyer_customer_party.party))

        # UNS segment - section control
        segments.append({"tag": "UNS", "elements": ["D"]})

        return {"message_type": "ORDRSP", "segments": segments}

    def _build_nad_segment(self, qualifier: str, party: Party) -> dict:
        """Build NAD segment for a party."""
        elements = [qualifier]

        if party.party_identifications:
            elements.append({"components": [party.party_identifications[0].id.value]})
        else:
            elements.append("")

        elements.append("")  # NAD03 - Name and address

        if party.party_names:
            elements.append({"components": [party.party_names[0].name]})
        else:
            elements.append("")

        return {"tag": "NAD", "elements": elements}
