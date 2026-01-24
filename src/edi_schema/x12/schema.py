"""
X12 Schema Loader.

Main schema loader that builds complete X12 transaction set schemas
from the 005010 schema definition files.

Implements the interface expected by SchemaRepository:
- exists(schema_id) - Check if a transaction set exists
- load(schema_id) - Load a transaction set schema
- list_schemas() - List all available transaction set IDs
"""

from dataclasses import dataclass, field
from pathlib import Path

from edi_schema.x12.enums import (
    DataElementType,
    NoteType,
    RequirementDesignator,
    TransactionSetArea,
)
from edi_schema.x12.models import (
    CodeSource,
    Composite,
    CompositeElement,
    DataElement,
    Segment,
    SegmentElement,
    SegmentNote,
    TransactionSet,
    TransactionSetSegment,
)
from edi_schema.x12.schema_parsers import (
    FreeformData,
    parse_comdetl,
    parse_comhead,
    parse_cs_cv,
    parse_cs_de,
    parse_cshead,
    parse_eledetl,
    parse_elehead,
    parse_freeform_file,
    parse_segdetl,
    parse_seghead,
    parse_setdetl,
    parse_sethead,
)


@dataclass
class X12Schema:
    """
    Represents a loaded X12 transaction set schema.

    Implements the SchemaLike protocol expected by the repository.

    Attributes:
        transaction_set: The transaction set definition
        segments: Dictionary of all segments used by this transaction set
        elements: Dictionary of all data elements used
        composites: Dictionary of all composites used
        code_sources: Dictionary of all code sources referenced
        version: Schema version (e.g., "005010")
    """

    transaction_set: TransactionSet
    segments: dict[str, Segment] = field(default_factory=dict)
    elements: dict[str, DataElement] = field(default_factory=dict)
    composites: dict[str, Composite] = field(default_factory=dict)
    code_sources: dict[str, CodeSource] = field(default_factory=dict)
    version: str = "005010"

    @property
    def format(self) -> str:
        """EDI format ('x12')."""
        return "x12"

    @property
    def id(self) -> str:
        """Schema identifier (transaction set ID)."""
        return self.transaction_set.id

    @property
    def name(self) -> str:
        """Human-readable name of the transaction set."""
        return self.transaction_set.name

    def get_segment(self, segment_id: str) -> Segment | None:
        """Look up a segment definition by ID."""
        return self.segments.get(segment_id)

    def get_element(self, element_id: str) -> DataElement | None:
        """Look up an element definition by ID."""
        return self.elements.get(element_id)

    def get_composite(self, composite_id: str) -> Composite | None:
        """Look up a composite definition by ID."""
        return self.composites.get(composite_id)

    def get_structure(self) -> list[TransactionSetSegment]:
        """Get the hierarchical structure of the transaction set."""
        return self.transaction_set.structure

    def get_segment_element_definition(
        self,
        segment_id: str,
        element_position: int,
    ) -> tuple["DataElement | Composite | None", "SegmentElement | None"]:
        """
        Get element definition for a position within a segment.

        Navigates from segment tag and element position to the full
        DataElement or Composite definition with all type/length/code info.

        Args:
            segment_id: Segment tag (e.g., "NM1", "CLM")
            element_position: 1-based element position

        Returns:
            Tuple of (DataElement or Composite, SegmentElement reference)
            Returns (None, None) if segment or element not found
        """
        segment = self.get_segment(segment_id)
        if not segment:
            return None, None

        # Convert position to sequence string (01, 02, ...)
        sequence = f"{element_position:02d}"
        seg_elem = segment.get_element(sequence)

        if not seg_elem:
            return None, None

        # Get the actual element/composite definition
        elem_id = seg_elem.element_id
        if elem_id.startswith("C"):
            return self.get_composite(elem_id), seg_elem
        else:
            return self.get_element(elem_id), seg_elem

    def __str__(self) -> str:
        return (
            f"X12Schema({self.transaction_set.id}: {self.transaction_set.name}, "
            f"{len(self.segments)} segments, {len(self.elements)} elements)"
        )


class X12SchemaLoader:
    """
    Loader for X12 005010 schema definitions.

    Loads and parses the schema definition files from the specified directory
    and builds complete transaction set schemas.

    Usage:
        loader = X12SchemaLoader("/path/to/005010")
        if loader.exists("850"):
            schema = loader.load("850")
            print(schema.name)  # "Purchase Order"
    """

    def __init__(self, schema_path: Path | str):
        """
        Initialize the schema loader.

        Args:
            schema_path: Path to the X12 schema directory containing
                         sethead.txt, seghead.txt, etc.
        """
        self._path = Path(schema_path)
        self._loaded = False

        # Raw parsed data (lazy loaded)
        self._set_headers: dict[str, tuple[str, str, str]] = {}
        self._set_details: dict[str, list[tuple]] = {}
        self._seg_headers: dict[str, tuple[str, str]] = {}
        self._seg_details: dict[str, list[tuple]] = {}
        self._ele_headers: dict[str, tuple[str, str]] = {}
        self._ele_details: dict[str, tuple[str, str, str, str]] = {}
        self._com_headers: dict[str, tuple[str, str]] = {}
        self._com_details: dict[str, list[tuple]] = {}
        self._cs_headers: dict[str, tuple[str, str]] = {}
        self._cs_elements: dict[str, list[str]] = {}
        self._cs_values: dict[str, list[tuple[str, str, str]]] = {}
        self._freeform: FreeformData | None = None

        # Built objects cache
        self._elements_cache: dict[str, DataElement] = {}
        self._composites_cache: dict[str, Composite] = {}
        self._segments_cache: dict[str, Segment] = {}
        self._code_sources_cache: dict[str, CodeSource] = {}
        self._schemas_cache: dict[str, X12Schema] = {}

    def _ensure_loaded(self) -> None:
        """Ensure all schema files have been loaded."""
        if self._loaded:
            return

        # Load all CSV files
        self._set_headers = parse_sethead(self._path / "sethead.txt")
        self._set_details = parse_setdetl(self._path / "setdetl.txt")
        self._seg_headers = parse_seghead(self._path / "seghead.txt")
        self._seg_details = parse_segdetl(self._path / "segdetl.txt")
        self._ele_headers = parse_elehead(self._path / "elehead.txt")
        self._ele_details = parse_eledetl(self._path / "eledetl.txt")
        self._com_headers = parse_comhead(self._path / "comhead.txt")
        self._com_details = parse_comdetl(self._path / "comdetl.txt")

        # Code source files are optional (not present in all schema versions)
        cshead_path = self._path / "cshead.txt"
        cs_de_path = self._path / "cs_de.txt"
        cs_cv_path = self._path / "cs_cv.txt"
        if cshead_path.exists():
            self._cs_headers = parse_cshead(cshead_path)
            self._cs_elements = parse_cs_de(cs_de_path) if cs_de_path.exists() else {}
            self._cs_values = parse_cs_cv(cs_cv_path) if cs_cv_path.exists() else {}
        else:
            self._cs_headers = {}
            self._cs_elements = {}
            self._cs_values = {}

        # Load freeform text
        self._freeform = parse_freeform_file(self._path / "freeform.txt")

        self._loaded = True

    def exists(self, schema_id: str) -> bool:
        """
        Check if a transaction set schema exists.

        Args:
            schema_id: Transaction set ID (e.g., "810", "850")

        Returns:
            True if the transaction set exists in the schema
        """
        self._ensure_loaded()
        return schema_id in self._set_headers

    def list_schemas(self) -> list[str]:
        """
        List all available transaction set IDs.

        Returns:
            Sorted list of transaction set IDs
        """
        self._ensure_loaded()
        return sorted(self._set_headers.keys())

    def load(self, schema_id: str) -> X12Schema:
        """
        Load a complete transaction set schema.

        Args:
            schema_id: Transaction set ID (e.g., "810", "850")

        Returns:
            X12Schema object with full transaction set definition

        Raises:
            ValueError: If the transaction set does not exist
        """
        self._ensure_loaded()

        if schema_id not in self._set_headers:
            raise ValueError(f"Transaction set {schema_id} not found")

        # Return cached schema if available
        if schema_id in self._schemas_cache:
            return self._schemas_cache[schema_id]

        # Build the transaction set
        transaction_set = self._build_transaction_set(schema_id)

        # Collect all segments, elements, composites used
        segments: dict[str, Segment] = {}
        elements: dict[str, DataElement] = {}
        composites: dict[str, Composite] = {}
        code_sources: dict[str, CodeSource] = {}

        # Get segments used in this transaction set
        for ts_seg in transaction_set.structure:
            seg_id = ts_seg.segment_id
            if seg_id not in segments:
                segment = self._get_segment(seg_id)
                if segment:
                    segments[seg_id] = segment

                    # Get elements used in this segment
                    for seg_elem in segment.elements:
                        elem_id = seg_elem.element_id
                        if elem_id.startswith("C"):
                            # Composite
                            if elem_id not in composites:
                                composite = self._get_composite(elem_id)
                                if composite:
                                    composites[elem_id] = composite
                                    # Get elements in composite
                                    for comp_elem in composite.elements:
                                        if comp_elem.element_id not in elements:
                                            element = self._get_element(comp_elem.element_id)
                                            if element:
                                                elements[comp_elem.element_id] = element
                        else:
                            # Simple element
                            if elem_id not in elements:
                                element = self._get_element(elem_id)
                                if element:
                                    elements[elem_id] = element

        # Build schema
        schema = X12Schema(
            transaction_set=transaction_set,
            segments=segments,
            elements=elements,
            composites=composites,
            code_sources=code_sources,
        )

        self._schemas_cache[schema_id] = schema
        return schema

    def _build_transaction_set(self, schema_id: str) -> TransactionSet:
        """Build a TransactionSet object from parsed data."""
        header = self._set_headers[schema_id]
        set_id, name, functional_group = header

        # Get purpose from freeform
        purpose = None
        if self._freeform and schema_id in self._freeform.set_purposes:
            purpose = self._freeform.set_purposes[schema_id]

        # Get notes from freeform
        notes = []
        if self._freeform and schema_id in self._freeform.set_notes:
            notes = self._freeform.set_notes[schema_id]

        # Build structure from details
        structure = []
        if schema_id in self._set_details:
            for detail in self._set_details[schema_id]:
                (
                    area,
                    sequence,
                    segment_id,
                    requirement,
                    max_use,
                    loop_level,
                    loop_repeat,
                    loop_id,
                ) = detail

                # Parse area
                try:
                    ts_area = TransactionSetArea(area)
                except ValueError:
                    ts_area = TransactionSetArea.HEADING

                # Parse requirement
                try:
                    req = RequirementDesignator(requirement)
                except ValueError:
                    req = RequirementDesignator.O

                # Parse max_use (can be integer or ">1")
                max_use_val: int | str
                if max_use == ">1":
                    max_use_val = ">1"
                else:
                    try:
                        max_use_val = int(max_use)
                    except ValueError:
                        max_use_val = 1

                # Parse loop level
                try:
                    level = int(loop_level)
                except ValueError:
                    level = 0

                # Parse loop repeat
                loop_rep: int | str
                if loop_repeat == ">1":
                    loop_rep = ">1"
                else:
                    try:
                        loop_rep = int(loop_repeat)
                    except ValueError:
                        loop_rep = 0

                # Loop ID (empty string becomes None)
                lid = loop_id if loop_id else None

                ts_segment = TransactionSetSegment(
                    area=ts_area,
                    sequence=sequence,
                    segment_id=segment_id,
                    requirement=req,
                    max_use=max_use_val,
                    loop_level=level,
                    loop_repeat=loop_rep,
                    loop_id=lid,
                )
                structure.append(ts_segment)

        return TransactionSet(
            id=set_id,
            name=name,
            functional_group=functional_group,
            purpose=purpose,
            structure=structure,
            notes=notes,
        )

    def _get_element(self, element_id: str) -> DataElement | None:
        """Get or build a DataElement."""
        if element_id in self._elements_cache:
            return self._elements_cache[element_id]

        if element_id not in self._ele_headers:
            return None

        header = self._ele_headers[element_id]
        _, name = header

        # Get details
        detail = self._ele_details.get(element_id)
        if not detail:
            return None

        _, data_type_str, min_len_str, max_len_str = detail

        # Parse data type
        try:
            data_type = DataElementType(data_type_str)
        except ValueError:
            # Handle 'N' type (generic numeric)
            if data_type_str == "N":
                data_type = DataElementType.N
            else:
                data_type = DataElementType.AN

        # Parse lengths
        try:
            min_len = int(min_len_str)
        except ValueError:
            min_len = 1
        try:
            max_len = int(max_len_str)
        except ValueError:
            max_len = 1

        # Get definition from freeform
        definition = None
        if self._freeform and element_id in self._freeform.element_definitions:
            definition = self._freeform.element_definitions[element_id]

        # Get code values from freeform
        code_values = {}
        if self._freeform:
            code_values = self._freeform.get_element_code_values(element_id)

        element = DataElement(
            id=element_id,
            name=name,
            data_type=data_type,
            min_length=min_len,
            max_length=max_len,
            definition=definition,
            code_values=code_values,
        )

        self._elements_cache[element_id] = element
        return element

    def _get_composite(self, composite_id: str) -> Composite | None:
        """Get or build a Composite."""
        if composite_id in self._composites_cache:
            return self._composites_cache[composite_id]

        if composite_id not in self._com_headers:
            return None

        header = self._com_headers[composite_id]
        _, name = header

        # Get purpose from freeform
        purpose = None
        if self._freeform and composite_id in self._freeform.composite_purposes:
            purpose = self._freeform.composite_purposes[composite_id]

        # Build elements list
        elements = []
        if composite_id in self._com_details:
            for detail in self._com_details[composite_id]:
                sequence, element_id, requirement_str = detail

                try:
                    requirement = RequirementDesignator(requirement_str)
                except ValueError:
                    requirement = RequirementDesignator.O

                comp_elem = CompositeElement(
                    sequence=sequence,
                    element_id=element_id,
                    requirement=requirement,
                )
                elements.append(comp_elem)

        composite = Composite(
            id=composite_id,
            name=name,
            purpose=purpose,
            elements=elements,
        )

        self._composites_cache[composite_id] = composite
        return composite

    def _get_segment(self, segment_id: str) -> Segment | None:
        """Get or build a Segment."""
        if segment_id in self._segments_cache:
            return self._segments_cache[segment_id]

        if segment_id not in self._seg_headers:
            return None

        header = self._seg_headers[segment_id]
        _, name = header

        # Get purpose from freeform
        purpose = None
        if self._freeform and segment_id in self._freeform.segment_purposes:
            purpose = self._freeform.segment_purposes[segment_id]

        # Build elements list
        elements = []
        if segment_id in self._seg_details:
            for detail in self._seg_details[segment_id]:
                sequence, element_id, requirement_str, repetition_str = detail

                try:
                    requirement = RequirementDesignator(requirement_str)
                except ValueError:
                    requirement = RequirementDesignator.O

                try:
                    repetition = int(repetition_str)
                except ValueError:
                    repetition = 1

                seg_elem = SegmentElement(
                    sequence=sequence,
                    element_id=element_id,
                    requirement=requirement,
                    repetition_count=repetition,
                )
                elements.append(seg_elem)

        # Get notes from freeform
        notes = []
        if self._freeform:
            for (seg_id, elem_pos, note_type, seq), text in self._freeform.segment_notes.items():
                if seg_id == segment_id:
                    try:
                        nt = NoteType(note_type)
                    except ValueError:
                        nt = NoteType.C
                    note = SegmentNote(
                        segment_id=segment_id,
                        element_position=elem_pos,
                        note_type=nt,
                        sequence=seq,
                        text=text,
                    )
                    notes.append(note)

        segment = Segment(
            id=segment_id,
            name=name,
            purpose=purpose,
            elements=elements,
            notes=notes,
        )

        self._segments_cache[segment_id] = segment
        return segment

    def _get_code_source(self, code_source_id: str) -> CodeSource | None:
        """Get or build a CodeSource."""
        if code_source_id in self._code_sources_cache:
            return self._code_sources_cache[code_source_id]

        if code_source_id not in self._cs_headers:
            return None

        header = self._cs_headers[code_source_id]
        _, name = header

        # Get text from freeform
        source_info = None
        address = None
        internet_address = None
        abstract = None
        notes = None

        if self._freeform:
            source_info = self._freeform.code_source_sources.get(code_source_id)
            address = self._freeform.code_source_from.get(code_source_id)
            internet_address = self._freeform.code_source_inet.get(code_source_id)
            abstract = self._freeform.code_source_abstract.get(code_source_id)
            notes = self._freeform.code_source_notes.get(code_source_id)

        # Get element mappings
        elements = self._cs_elements.get(code_source_id, [])

        # Get code values
        code_values: dict[tuple[str, str], str] = {}
        if code_source_id in self._cs_values:
            for _, elem_id, code in self._cs_values[code_source_id]:
                # Note: cs_cv.txt doesn't include descriptions
                # Descriptions come from ELECOD in freeform
                code_values[(elem_id, code)] = ""

        code_source = CodeSource(
            id=code_source_id,
            name=name,
            source_info=source_info,
            address=address,
            internet_address=internet_address,
            abstract=abstract,
            notes=notes,
            elements=elements,
            code_values=code_values,
        )

        self._code_sources_cache[code_source_id] = code_source
        return code_source

    def get_all_elements(self) -> dict[str, DataElement]:
        """
        Get all data elements in the schema.

        Returns:
            Dictionary mapping element ID to DataElement
        """
        self._ensure_loaded()
        result = {}
        for elem_id in self._ele_headers:
            element = self._get_element(elem_id)
            if element:
                result[elem_id] = element
        return result

    def get_all_segments(self) -> dict[str, Segment]:
        """
        Get all segments in the schema.

        Returns:
            Dictionary mapping segment ID to Segment
        """
        self._ensure_loaded()
        result = {}
        for seg_id in self._seg_headers:
            segment = self._get_segment(seg_id)
            if segment:
                result[seg_id] = segment
        return result

    def get_all_composites(self) -> dict[str, Composite]:
        """
        Get all composites in the schema.

        Returns:
            Dictionary mapping composite ID to Composite
        """
        self._ensure_loaded()
        result = {}
        for com_id in self._com_headers:
            composite = self._get_composite(com_id)
            if composite:
                result[com_id] = composite
        return result

    def get_all_code_sources(self) -> dict[str, CodeSource]:
        """
        Get all code sources in the schema.

        Returns:
            Dictionary mapping code source ID to CodeSource
        """
        self._ensure_loaded()
        result = {}
        for cs_id in self._cs_headers:
            code_source = self._get_code_source(cs_id)
            if code_source:
                result[cs_id] = code_source
        return result
