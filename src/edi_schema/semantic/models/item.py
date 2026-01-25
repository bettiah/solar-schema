"""
Semantic Item Models.

Product and service item representations with identification,
classification, and pricing.
"""

from decimal import Decimal

from pydantic import Field

from .base import SemanticModel
from .primitives import Amount, Identifier, Quantity


class ItemIdentification(SemanticModel):
    """
    Item identifier (UPC, EAN, SKU, etc.).

    Maps to:
    - UBL: cac:*ItemIdentification
    - X12: PO1/IT1 product ID pairs (qualifier + value)
    - EDIFACT: LIN/PIA segments
    """

    id: Identifier = Field(description="The item identifier")
    barcode_symbology_id: str | None = Field(
        default=None,
        description="Barcode symbology (e.g., EAN-13, UPC-A)",
    )
    extended_id: str | None = Field(
        default=None,
        description="Extended identifier",
    )
    physical_attribute: str | None = Field(
        default=None,
        description="Physical attribute description",
    )
    measurement_dimension: str | None = Field(
        default=None,
        description="Measurement dimension",
    )

    def __str__(self) -> str:
        return str(self.id)


class CommodityClassification(SemanticModel):
    """
    Commodity classification code.

    Maps to:
    - UBL: cac:CommodityClassification
    - X12: LIN segment product codes
    - EDIFACT: GIR segment
    """

    nature_code: str | None = Field(
        default=None,
        description="Nature of cargo code",
    )
    cargo_type_code: str | None = Field(
        default=None,
        description="Cargo type code",
    )
    commodity_code: str | None = Field(
        default=None,
        description="Commodity classification code",
    )
    item_classification_code: str | None = Field(
        default=None,
        description="Item classification code (UNSPSC, etc.)",
    )

    def __str__(self) -> str:
        return self.commodity_code or self.item_classification_code or "unclassified"


class AdditionalItemProperty(SemanticModel):
    """
    Additional property of an item.

    Maps to:
    - UBL: cac:AdditionalItemProperty
    - X12: PID segment
    - EDIFACT: IMD segment
    """

    name: str = Field(description="Property name")
    value: str | None = Field(
        default=None,
        description="Property value",
    )
    value_quantity: Quantity | None = Field(
        default=None,
        description="Property value as quantity",
    )
    value_qualifier: str | None = Field(
        default=None,
        description="Qualifier for the value",
    )

    def __str__(self) -> str:
        if self.value:
            return f"{self.name}: {self.value}"
        return self.name


class HazardousItem(SemanticModel):
    """
    Hazardous item information.

    Maps to:
    - UBL: cac:HazardousItem
    - X12: H1/H2/H3 segments
    - EDIFACT: DGS segment
    """

    id: str | None = Field(
        default=None,
        description="UN dangerous goods ID",
    )
    undg_code: str | None = Field(
        default=None,
        description="UN dangerous goods code",
    )
    hazard_class_id: str | None = Field(
        default=None,
        description="Hazard class",
    )
    technical_name: str | None = Field(
        default=None,
        description="Technical name of substance",
    )
    category_name: str | None = Field(
        default=None,
        description="Category name",
    )
    packing_group: str | None = Field(
        default=None,
        description="Packing group (I, II, III)",
    )


class ItemInstance(SemanticModel):
    """
    Specific instance of an item (serial number, lot, etc.).

    Maps to:
    - UBL: cac:ItemInstance
    - X12: SN1 segment
    - EDIFACT: GIN segment
    """

    product_trace_id: str | None = Field(
        default=None,
        description="Product trace identifier",
    )
    manufacture_date: str | None = Field(
        default=None,
        description="Date of manufacture",
    )
    manufacture_time: str | None = Field(
        default=None,
        description="Time of manufacture",
    )
    best_before_date: str | None = Field(
        default=None,
        description="Best before date",
    )
    registration_id: str | None = Field(
        default=None,
        description="Registration identifier",
    )
    serial_id: str | None = Field(
        default=None,
        description="Serial number",
    )
    lot_number_id: str | None = Field(
        default=None,
        description="Lot/batch number",
    )


class Item(SemanticModel):
    """
    Product or service item.

    Central entity representing any item (product, service, or
    other line item content) in a business document.

    Maps to:
    - UBL: cac:Item
    - X12: PO1/IT1 loop with PID
    - EDIFACT: LIN segment group
    """

    # Description
    description: str | None = Field(
        default=None,
        description="Item description",
    )
    name: str | None = Field(
        default=None,
        description="Short item name",
    )
    pack_quantity: Quantity | None = Field(
        default=None,
        description="Quantity per pack",
    )
    pack_size_numeric: Decimal | None = Field(
        default=None,
        description="Pack size",
    )
    keyword: str | None = Field(
        default=None,
        description="Search keyword",
    )
    brand_name: str | None = Field(
        default=None,
        description="Brand name",
    )
    model_name: str | None = Field(
        default=None,
        description="Model name",
    )

    # Identifiers
    buyers_item_identification: ItemIdentification | None = Field(
        default=None,
        description="Buyer's item identifier",
    )
    sellers_item_identification: ItemIdentification | None = Field(
        default=None,
        description="Seller's item identifier",
    )
    manufacturers_item_identification: ItemIdentification | None = Field(
        default=None,
        description="Manufacturer's item identifier",
    )
    standard_item_identification: ItemIdentification | None = Field(
        default=None,
        description="Standard identifier (UPC, EAN, GTIN)",
    )
    catalogue_item_identification: ItemIdentification | None = Field(
        default=None,
        description="Catalogue item identifier",
    )
    additional_item_identifications: list[ItemIdentification] = Field(
        default_factory=list,
        description="Additional identifiers",
    )

    # Classification
    commodity_classifications: list[CommodityClassification] = Field(
        default_factory=list,
        description="Commodity classifications",
    )

    # Properties
    additional_item_properties: list[AdditionalItemProperty] = Field(
        default_factory=list,
        description="Additional properties",
    )

    # Origin
    origin_country_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="Country of origin (ISO 3166)",
    )
    origin_country_name: str | None = Field(
        default=None,
        description="Country of origin name",
    )

    # Hazmat
    hazardous_items: list[HazardousItem] = Field(
        default_factory=list,
        description="Hazardous item information",
    )

    # Instances
    item_instances: list[ItemInstance] = Field(
        default_factory=list,
        description="Specific item instances",
    )

    @property
    def display_name(self) -> str:
        """Get best available display name."""
        return self.name or self.description or "unnamed item"

    @property
    def primary_id(self) -> str | None:
        """Get the primary identifier value."""
        if self.standard_item_identification:
            return self.standard_item_identification.id.value
        if self.sellers_item_identification:
            return self.sellers_item_identification.id.value
        if self.buyers_item_identification:
            return self.buyers_item_identification.id.value
        return None

    def __str__(self) -> str:
        return self.display_name


class Price(SemanticModel):
    """
    Unit price for an item.

    Maps to:
    - UBL: cac:Price
    - X12: PO1*04 (unit price), PO1*05 (basis)
    - EDIFACT: PRI segment
    """

    price_amount: Amount = Field(description="Unit price amount")
    base_quantity: Quantity | None = Field(
        default=None,
        description="Quantity on which price is based",
    )
    price_type_code: str | None = Field(
        default=None,
        description="Price type (e.g., catalog, contract, spot)",
    )
    price_type: str | None = Field(
        default=None,
        description="Price type description",
    )
    orderable_unit_factor_rate: Decimal | None = Field(
        default=None,
        description="Factor for orderable units",
    )
    allowance_charges: list["AllowanceCharge"] = Field(
        default_factory=list,
        description="Price-level allowances/charges",
    )

    def __str__(self) -> str:
        return str(self.price_amount)


# Forward reference for circular import
from .allowance_charge import AllowanceCharge  # noqa: E402

Price.model_rebuild()
