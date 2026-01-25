"""
Semantic Delivery and Shipment Models.

Delivery, shipping, and transport handling structures.
"""

from datetime import date, time

from pydantic import Field

from .base import SemanticModel
from .party import Address, Party
from .primitives import Measure, Period, Quantity


class DeliveryTerms(SemanticModel):
    """
    Delivery terms (Incoterms, etc.).

    Maps to:
    - UBL: cac:DeliveryTerms
    - X12: FOB segment
    - EDIFACT: TOD segment
    """

    id: str | None = Field(
        default=None,
        description="Delivery terms identifier",
    )
    special_terms: str | None = Field(
        default=None,
        description="Special terms description",
    )
    loss_risk_responsibility_code: str | None = Field(
        default=None,
        description="Risk transfer code",
    )
    loss_risk: str | None = Field(
        default=None,
        description="Risk transfer description",
    )
    amount: "Amount | None" = Field(
        default=None,
        description="Associated amount",
    )
    delivery_location: Address | None = Field(
        default=None,
        description="Named delivery location",
    )

    def __str__(self) -> str:
        return self.id or self.special_terms or "unspecified terms"


class TransportEquipment(SemanticModel):
    """
    Transport equipment (container, trailer, etc.).

    Maps to:
    - UBL: cac:TransportEquipment
    - X12: TD3 segment
    - EDIFACT: EQD segment
    """

    id: str | None = Field(
        default=None,
        description="Equipment identifier (container number)",
    )
    transport_equipment_type_code: str | None = Field(
        default=None,
        description="Equipment type code",
    )
    description: str | None = Field(
        default=None,
        description="Equipment description",
    )
    size_type_code: str | None = Field(
        default=None,
        description="Size/type code (ISO 6346)",
    )
    disposition_code: str | None = Field(
        default=None,
        description="Disposition code",
    )
    fullness_indication_code: str | None = Field(
        default=None,
        description="Fullness indicator",
    )
    power_indicator: bool | None = Field(
        default=None,
        description="Whether powered (e.g., reefer)",
    )
    refrigeration_on_indicator: bool | None = Field(
        default=None,
        description="Whether refrigeration is active",
    )
    return_indicator: bool | None = Field(
        default=None,
        description="Whether equipment should be returned",
    )
    owner_party: Party | None = Field(
        default=None,
        description="Equipment owner",
    )

    def __str__(self) -> str:
        return self.id or self.transport_equipment_type_code or "equipment"


class TransportMeans(SemanticModel):
    """
    Means of transport (vehicle, vessel, etc.).

    Maps to:
    - UBL: cac:TransportMeans
    - X12: TD5 segment
    - EDIFACT: TDT segment
    """

    journey_id: str | None = Field(
        default=None,
        description="Journey identifier",
    )
    registration_nationality_id: str | None = Field(
        default=None,
        description="Registration nationality",
    )
    registration_nationality: str | None = Field(
        default=None,
        description="Nationality name",
    )
    direction_code: str | None = Field(
        default=None,
        description="Direction code (inbound/outbound)",
    )
    transport_means_type_code: str | None = Field(
        default=None,
        description="Transport means type (truck, ship, etc.)",
    )
    trade_service_code: str | None = Field(
        default=None,
        description="Trade service code",
    )

    # Identification
    air_transport_id: str | None = Field(
        default=None,
        description="Flight number",
    )
    rail_transport_id: str | None = Field(
        default=None,
        description="Train number",
    )
    road_transport_id: str | None = Field(
        default=None,
        description="Vehicle registration",
    )
    maritime_transport_id: str | None = Field(
        default=None,
        description="Vessel identification (IMO number)",
    )
    maritime_transport_name: str | None = Field(
        default=None,
        description="Vessel name",
    )

    def __str__(self) -> str:
        return (
            self.maritime_transport_name
            or self.road_transport_id
            or self.air_transport_id
            or "transport"
        )


class ShipmentStage(SemanticModel):
    """
    Stage in a shipment journey.

    Maps to:
    - UBL: cac:ShipmentStage
    - X12: TD5 segment (one per leg)
    - EDIFACT: TDT segment
    """

    id: str | None = Field(
        default=None,
        description="Stage identifier",
    )
    transport_mode_code: str | None = Field(
        default=None,
        description="Mode of transport (1=Sea, 2=Rail, 3=Road, 4=Air)",
    )
    transport_means_type_code: str | None = Field(
        default=None,
        description="Type of transport means",
    )
    transit_direction_code: str | None = Field(
        default=None,
        description="Transit direction",
    )
    pre_carriage_indicator: bool | None = Field(
        default=None,
        description="Pre-carriage stage",
    )
    on_carriage_indicator: bool | None = Field(
        default=None,
        description="On-carriage stage",
    )

    # Period
    transit_period: Period | None = Field(
        default=None,
        description="Transit time period",
    )
    estimated_delivery_date: date | None = Field(
        default=None,
        description="Estimated delivery date",
    )
    estimated_delivery_time: time | None = Field(
        default=None,
        description="Estimated delivery time",
    )

    # Parties
    carrier_party: Party | None = Field(
        default=None,
        description="Carrier for this stage",
    )

    # Transport
    transport_means: TransportMeans | None = Field(
        default=None,
        description="Transport means used",
    )

    def __str__(self) -> str:
        return self.id or self.transport_mode_code or "stage"


class TransportHandlingUnit(SemanticModel):
    """
    Transport handling unit (pallet, carton, etc.).

    Maps to:
    - UBL: cac:TransportHandlingUnit
    - X12: HL loop with P (Pack) level, MAN segment
    - EDIFACT: PAC segment group
    """

    id: str | None = Field(
        default=None,
        description="Handling unit ID (e.g., SSCC-18)",
    )
    transport_handling_unit_type_code: str | None = Field(
        default=None,
        description="Unit type code (pallet, carton, etc.)",
    )
    handling_code: str | None = Field(
        default=None,
        description="Handling instructions code",
    )
    handling_instructions: str | None = Field(
        default=None,
        description="Handling instructions text",
    )
    hazardous_risk_indicator: bool | None = Field(
        default=None,
        description="Contains hazardous goods",
    )
    total_goods_item_quantity: int | None = Field(
        default=None,
        description="Total items in unit",
    )
    total_package_quantity: int | None = Field(
        default=None,
        description="Total packages in unit",
    )

    # Dimensions
    actual_package_quantity: Quantity | None = Field(
        default=None,
        description="Actual package quantity",
    )
    gross_weight_measure: Measure | None = Field(
        default=None,
        description="Gross weight",
    )
    net_weight_measure: Measure | None = Field(
        default=None,
        description="Net weight",
    )
    gross_volume_measure: Measure | None = Field(
        default=None,
        description="Gross volume",
    )

    # Nested units
    transport_handling_units: list["TransportHandlingUnit"] = Field(
        default_factory=list,
        description="Nested handling units",
    )

    # Equipment
    transport_equipment: list[TransportEquipment] = Field(
        default_factory=list,
        description="Associated equipment",
    )

    # References
    shipment_document_reference: "DocumentReference | None" = Field(
        default=None,
        description="Shipment document reference",
    )

    def __str__(self) -> str:
        return self.id or self.transport_handling_unit_type_code or "unit"


class Shipment(SemanticModel):
    """
    Shipment information.

    Maps to:
    - UBL: cac:Shipment
    - X12: HL loop with S (Shipment) level
    - EDIFACT: TDT/LOC/MEA segment groups
    """

    id: str | None = Field(
        default=None,
        description="Shipment identifier",
    )
    shipping_priority_level_code: str | None = Field(
        default=None,
        description="Shipping priority",
    )
    handling_code: str | None = Field(
        default=None,
        description="Handling code",
    )
    handling_instructions: str | None = Field(
        default=None,
        description="Handling instructions",
    )
    information: str | None = Field(
        default=None,
        description="Additional information",
    )

    # Weights and measures
    gross_weight_measure: Measure | None = Field(
        default=None,
        description="Total gross weight",
    )
    net_weight_measure: Measure | None = Field(
        default=None,
        description="Total net weight",
    )
    net_net_weight_measure: Measure | None = Field(
        default=None,
        description="Net-net weight",
    )
    gross_volume_measure: Measure | None = Field(
        default=None,
        description="Total gross volume",
    )
    net_volume_measure: Measure | None = Field(
        default=None,
        description="Total net volume",
    )
    total_goods_item_quantity: int | None = Field(
        default=None,
        description="Total goods items",
    )
    total_transport_handling_unit_quantity: int | None = Field(
        default=None,
        description="Total handling units",
    )
    insurance_value_amount: "Amount | None" = Field(
        default=None,
        description="Insurance value",
    )
    declared_customs_value_amount: "Amount | None" = Field(
        default=None,
        description="Customs declared value",
    )
    declared_for_carriage_value_amount: "Amount | None" = Field(
        default=None,
        description="Value declared for carriage",
    )
    declared_statistics_value_amount: "Amount | None" = Field(
        default=None,
        description="Value for statistics",
    )
    free_on_board_value_amount: "Amount | None" = Field(
        default=None,
        description="FOB value",
    )

    # Parties
    consignor_party: Party | None = Field(
        default=None,
        description="Consignor (shipper)",
    )
    consignee_party: Party | None = Field(
        default=None,
        description="Consignee (receiver)",
    )
    carrier_party: Party | None = Field(
        default=None,
        description="Carrier",
    )
    shipper_party: Party | None = Field(
        default=None,
        description="Shipper party",
    )
    freight_forwarder_party: Party | None = Field(
        default=None,
        description="Freight forwarder",
    )

    # Terms
    delivery_terms: DeliveryTerms | None = Field(
        default=None,
        description="Delivery terms",
    )

    # Stages
    shipment_stages: list[ShipmentStage] = Field(
        default_factory=list,
        description="Shipment stages/legs",
    )

    # Handling units
    transport_handling_units: list[TransportHandlingUnit] = Field(
        default_factory=list,
        description="Transport handling units",
    )

    # Origin/destination
    origin_address: Address | None = Field(
        default=None,
        description="Origin address",
    )
    first_arrival_port_location: Address | None = Field(
        default=None,
        description="First arrival port",
    )
    last_exit_port_location: Address | None = Field(
        default=None,
        description="Last exit port",
    )

    def __str__(self) -> str:
        return self.id or "shipment"


class Delivery(SemanticModel):
    """
    Delivery information.

    Maps to:
    - UBL: cac:Delivery
    - X12: N1 ST loop, DTM segments
    - EDIFACT: NAD+DP, DTM
    """

    id: str | None = Field(
        default=None,
        description="Delivery identifier",
    )

    # Quantity
    quantity: Quantity | None = Field(
        default=None,
        description="Delivered quantity",
    )
    minimum_quantity: Quantity | None = Field(
        default=None,
        description="Minimum quantity",
    )
    maximum_quantity: Quantity | None = Field(
        default=None,
        description="Maximum quantity",
    )

    # Dates/times
    actual_delivery_date: date | None = Field(
        default=None,
        description="Actual delivery date",
    )
    actual_delivery_time: time | None = Field(
        default=None,
        description="Actual delivery time",
    )
    latest_delivery_date: date | None = Field(
        default=None,
        description="Latest acceptable delivery date",
    )
    latest_delivery_time: time | None = Field(
        default=None,
        description="Latest acceptable delivery time",
    )
    release_id: str | None = Field(
        default=None,
        description="Release identifier",
    )
    tracking_id: str | None = Field(
        default=None,
        description="Tracking identifier",
    )

    # Location
    delivery_location: Address | None = Field(
        default=None,
        description="Delivery address",
    )
    alternative_delivery_location: Address | None = Field(
        default=None,
        description="Alternative delivery address",
    )

    # Periods
    requested_delivery_period: Period | None = Field(
        default=None,
        description="Requested delivery period",
    )
    promised_delivery_period: Period | None = Field(
        default=None,
        description="Promised delivery period",
    )
    estimated_delivery_period: Period | None = Field(
        default=None,
        description="Estimated delivery period",
    )

    # Parties
    delivery_party: Party | None = Field(
        default=None,
        description="Delivery party",
    )
    carrier_party: Party | None = Field(
        default=None,
        description="Carrier",
    )
    notify_party: Party | None = Field(
        default=None,
        description="Notify party",
    )

    # Terms
    delivery_terms: DeliveryTerms | None = Field(
        default=None,
        description="Delivery terms",
    )

    # Despatch
    despatch: "Despatch | None" = Field(
        default=None,
        description="Despatch information",
    )

    # Shipment
    shipment: Shipment | None = Field(
        default=None,
        description="Shipment details",
    )

    def __str__(self) -> str:
        if self.actual_delivery_date:
            return f"Delivery on {self.actual_delivery_date}"
        return self.id or "delivery"


class Despatch(SemanticModel):
    """
    Despatch (shipment) information.

    Maps to:
    - UBL: cac:Despatch
    - X12: BSN segment
    - EDIFACT: BGM in DESADV
    """

    id: str | None = Field(
        default=None,
        description="Despatch identifier",
    )
    requested_despatch_date: date | None = Field(
        default=None,
        description="Requested despatch date",
    )
    requested_despatch_time: time | None = Field(
        default=None,
        description="Requested despatch time",
    )
    estimated_despatch_date: date | None = Field(
        default=None,
        description="Estimated despatch date",
    )
    estimated_despatch_time: time | None = Field(
        default=None,
        description="Estimated despatch time",
    )
    actual_despatch_date: date | None = Field(
        default=None,
        description="Actual despatch date",
    )
    actual_despatch_time: time | None = Field(
        default=None,
        description="Actual despatch time",
    )
    guaranteed_despatch_date: date | None = Field(
        default=None,
        description="Guaranteed despatch date",
    )
    guaranteed_despatch_time: time | None = Field(
        default=None,
        description="Guaranteed despatch time",
    )
    release_id: str | None = Field(
        default=None,
        description="Release identifier",
    )
    instructions: str | None = Field(
        default=None,
        description="Despatch instructions",
    )
    despatch_address: Address | None = Field(
        default=None,
        description="Despatch address",
    )
    despatch_location: Address | None = Field(
        default=None,
        description="Despatch location",
    )
    despatch_party: Party | None = Field(
        default=None,
        description="Despatch party",
    )
    carrier_party: Party | None = Field(
        default=None,
        description="Carrier",
    )
    notify_party: list[Party] = Field(
        default_factory=list,
        description="Notify parties",
    )
    contact: "Contact | None" = Field(
        default=None,
        description="Despatch contact",
    )
    estimated_despatch_period: Period | None = Field(
        default=None,
        description="Estimated despatch period",
    )
    requested_despatch_period: Period | None = Field(
        default=None,
        description="Requested despatch period",
    )

    def __str__(self) -> str:
        if self.actual_despatch_date:
            return f"Despatch on {self.actual_despatch_date}"
        return self.id or "despatch"


# Forward references
from .party import Contact  # noqa: E402
from .primitives import Amount  # noqa: E402
from .reference import DocumentReference  # noqa: E402

TransportHandlingUnit.model_rebuild()
Shipment.model_rebuild()
Delivery.model_rebuild()
Despatch.model_rebuild()
DeliveryTerms.model_rebuild()
