# X12 997 Functional Acknowledgement Mapping

## Overview

Maps X12 997 Functional Acknowledgement to UBL ApplicationResponse semantic model.

**Status:** Planning
**X12 Transaction:** 997 - Functional Acknowledgement
**UBL Document:** ApplicationResponse

---

## Overview

The 997 is a technical acknowledgement that confirms receipt of an EDI transmission. It's **not** a business-level response (like 855 PO Acknowledgement) but rather confirms the EDI envelope was received and parseable.

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **AK1** | 01 | Functional ID Code | `document_response.document_reference.document_type_code` | PO, IN, SH |
| AK1 | 02 | Group Control Number | `document_response.document_reference.id` | From GS06 |
| AK1 | 03 | Version/Release | `document_response.document_reference.version_id` | (optional) |

---

## Transaction Set Response (AK2/AK5 Loop)

Each transaction set in the functional group gets an AK2/AK5 pair:

### AK2 - Transaction Set Response Header

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AK2*01 | Transaction Set ID | `document_response.document_reference.document_type` | 850, 856, etc. |
| AK2*02 | Control Number | `document_response.document_reference.uuid` | From ST02 |
| AK2*03 | Implementation Version | `document_response.document_reference.version_id` | (optional) |

### AK5 - Transaction Set Response Trailer

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AK5*01 | Acknowledgment Code | `document_response.response.response_code` | A, E, R |
| AK5*02 | Error Code 1 | `document_response.response.description` | If errors |
| AK5*03 | Error Code 2 | `document_response.response.description` | (appended) |
| AK5*04 | Error Code 3 | `document_response.response.description` | (appended) |
| AK5*05 | Error Code 4 | `document_response.response.description` | (appended) |
| AK5*06 | Error Code 5 | `document_response.response.description` | (appended) |

---

## Acknowledgment Code Mapping (AK5*01)

| X12 Code | Meaning | Semantic `response_code` |
|----------|---------|-------------------------|
| A | Accepted | `ACCEPTED` |
| E | Accepted with Errors | `ACCEPTED_WITH_ERRORS` |
| M | Rejected, Message Authentication Code (MAC) Failed | `REJECTED` |
| P | Partially Accepted | `PARTIALLY_ACCEPTED` |
| R | Rejected | `REJECTED` |
| W | Rejected, Invalid Security Info | `REJECTED` |
| X | Rejected, Content Not Supported | `REJECTED` |

---

## Error Codes (AK5*02-06)

Common error codes reported in AK5:

| Code | Meaning |
|------|---------|
| 1 | Transaction Set Not Supported |
| 2 | Transaction Set Trailer Missing |
| 3 | Transaction Set Control Number Mismatch |
| 4 | Number of Included Segments Mismatch |
| 5 | One or More Segments in Error |
| 6 | Missing or Invalid Transaction Set Identifier |
| 7 | Missing or Invalid Transaction Set Control Number |
| 8-23 | Various segment/element errors |

---

## Segment Error Detail (AK3/AK4 Loop)

For detailed error reporting:

### AK3 - Data Segment Note

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AK3*01 | Segment ID | `line_response.document_reference.document_type` | N1, PO1, etc. |
| AK3*02 | Position in Transaction | `line_response.document_reference.line_id` | Segment position |
| AK3*03 | Loop ID | `line_response.document_reference.uuid` | (optional) |
| AK3*04 | Segment Error Code | `line_response.response.response_code` | |

### AK4 - Data Element Note

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AK4*01 | Element Position | `line_response.line_reference.line_id` | |
| AK4*02 | Element Reference | (for composite) | |
| AK4*03 | Data Element Error Code | `line_response.response.description` | |
| AK4*04 | Copy of Bad Data | `line_response.response.description` | (appended) |

---

## Segment Error Codes (AK3*04)

| Code | Meaning |
|------|---------|
| 1 | Unrecognized Segment ID |
| 2 | Unexpected Segment |
| 3 | Mandatory Segment Missing |
| 4 | Loop Occurs Over Maximum Times |
| 5 | Segment Exceeds Maximum Use |
| 6 | Segment Not in Defined Transaction Set |
| 7 | Segment Not in Proper Sequence |
| 8 | Segment Has Data Element Errors |

---

## Data Element Error Codes (AK4*03)

| Code | Meaning |
|------|---------|
| 1 | Mandatory Data Element Missing |
| 2 | Conditional Required Data Element Missing |
| 3 | Too Many Data Elements |
| 4 | Data Element Too Short |
| 5 | Data Element Too Long |
| 6 | Invalid Character in Data Element |
| 7 | Invalid Code Value |
| 8 | Invalid Date |
| 9 | Invalid Time |
| 10 | Exclusion Condition Violated |

---

## Functional Group Response (AK9 Segment)

Summary for the entire functional group:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AK9*01 | Acknowledgment Code | `response.response_code` | Group-level |
| AK9*02 | Transactions Included | `total_document_count` | Count from GE |
| AK9*03 | Transactions Received | `received_document_count` | |
| AK9*04 | Transactions Accepted | `accepted_document_count` | |
| AK9*05 | Error Code 1 | `response.description` | (optional) |
| AK9*06-09 | Error Codes 2-5 | `response.description` | (appended) |

---

## Implementation Notes

### 997 vs 999
- **997** is the legacy functional acknowledgement
- **999** is the HIPAA-compliant implementation acknowledgement (more detailed)
- For non-HIPAA, 997 is standard

### Automatic Generation
Most EDI translators auto-generate 997s. The semantic model is primarily for:
1. Parsing received 997s to check transmission status
2. Reporting errors back to originator
3. Tracking acknowledgement status

---

## Implementation Tasks

- [ ] Create ApplicationResponse semantic model
- [ ] Create 997 mapping definition
- [ ] Add AK1 header mapping
- [ ] Add AK2/AK5 transaction set loop handler
- [ ] Add AK3/AK4 error detail handler (optional)
- [ ] Add AK9 summary mapping
- [ ] Add error code lookup/description mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/application_response.py` | Create ApplicationResponse semantic model |
| `mapping/x12/functional_ack_997.py` | Create mapping definition |
| `mapping/engine.py` | Add 997-specific handlers |
| `tests/semantic/test_x12_functional_ack_mapper.py` | Add tests |
