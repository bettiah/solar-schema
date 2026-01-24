# EDIFACT quick ref

EDIFACT (Electronic Data Interchange For Administration, Commerce and Transport) uses a hierarchical envelope structure similar to X12, but with different segment names and field structures. The key difference is that EDIFACT uses **composite data elements** (groups of related fields) rather than simple positional elements.

## Envelope Structure

```
UNA (optional)  ← Service String Advice (defines separators)
UNB             ← Interchange Header
  UNG (optional) ← Functional Group Header
    UNH          ← Message Header
    ...          ← Message content
    UNT          ← Message Trailer
  UNE (optional) ← Functional Group Trailer
UNZ             ← Interchange Trailer
```

## 1. UNA - Service String Advice (Optional)

The UNA segment defines the separator characters used in the interchange. It's **not** a normal segment - it's exactly 9 bytes with fixed positions:

```
UNA:+.? '
   ││││└─ Segment terminator (usually ')
   │││└── Reserved (usually space)
   ││└─── Release/escape character (usually ?)
   │└──── Decimal notation (usually .)
   └───── Component data element separator (usually +)
         Data element separator (usually :)
```

**When to include UNA:**
- When charset is not UNOA (default)
- When using non-standard separators
- When `forceUNA` is set

## 2. UNB - Interchange Header

The UNB segment contains interchange-level information:
`UNB+UNOA:2+PARTNER1:14+PARTNER2:14+050824:1727+1UNBREF++++++1'`

| Field | Name | Description | Example |
|-------|------|-------------|---------|
| **S001** | Syntax identifier | Composite containing charset and version | |
| S001.0001 | Syntax identifier | UNOA, UNOB, UNOC, etc. | `UNOC` |
| S001.0002 | Syntax version number | 1, 2, 3, 4 | `3` |
| S001.0080 | Service code list directory version | Optional | |
| S001.0133 | Character encoding | Optional | `UTF8` |
| **S002** | Interchange sender | Composite containing sender details | |
| S002.0004 | Sender identification | Partner ID | `SENDER123` |
| S002.0007 | Identification code qualifier | Partner ID type | `14` (EAN) |
| S002.0008 | Address for reverse routing | Optional | |
| S002.0042 | Sender identification reverse routing | Optional | |
| **S003** | Interchange recipient | Composite containing receiver details | |
| S003.0010 | Recipient identification | Partner ID | `RECEIVER456` |
| S003.0007 | Identification code qualifier | Partner ID type | `14` (EAN) |
| S003.0014 | Routing address | Optional | |
| S003.0046 | Recipient identification reverse routing | Optional | |
| **S004** | Date/time of preparation | Composite with date and time | |
| S004.0017 | Date | YYMMDD or CCYYMMDD | `20231031` |
| S004.0019 | Time | HHMM or HHMMSS | `1430` |
| **S005** | Recipients reference/password | Optional composite | |
| S005.0022 | Recipients reference/password | Optional | |
| S005.0025 | Recipients reference/password qualifier | Optional | |
| 0020 | Interchange control reference | Unique reference number | `12345` |
| 0026 | Application reference | Optional message type | `ORDERS` |
| 0029 | Processing priority code | A=High, blank=Normal | |
| 0031 | Acknowledgement request | 1=Requested | `1` |
| 0032 | Interchange agreement identifier | Optional | |
| 0035 | Test indicator | 1=Test, blank=Production | `1` |

## 3. UNG/UNE - Functional Group (Optional)

Many EDIFACT implementations **skip** UNG/UNE and go directly from UNB to UNH. When used:

**UNG Fields:**
- 0038: Message type (ORDERS, INVOIC, etc.)
- S006: Application sender
- S007: Application recipient
- S004: Date/time
- 0048: Group reference number
- 0051: Controlling agency (UN, etc.)
- S008: Message version/release

**UNE Fields:**
- 0060: Number of messages in group
- 0048: Group reference number (matches UNG)

## 4. UNH/UNT - Message Header/Trailer

These are part of the message itself, not the envelope:

**UNH Fields:**
- 0062: Message reference number
- S009: Message identifier (type, version, release, etc.)

**UNT Fields:**
- 0074: Number of segments in message
- 0062: Message reference number (matches UNH)

## 5. UNZ - Interchange Trailer

The UNZ segment closes the interchange:

| Field | Name | Description |
|-------|------|-------------|
| 0036 | Interchange control count | Number of messages/groups in UNB |
| 0020 | Interchange control reference | Must match UNB.0020 |

## Version-Dependent Behavior

Similar to X12, EDIFACT date formatting depends on the syntax version:

| Version | Date Format (S004.0017) | Example |
|---------|------------------------|---------|
| < 4 | YYMMDD (6 digits) | `231031` |
| >= 4 | CCYYMMDD (8 digits) | `20231031` |

## Interactive messages
┌─────────────┬─────────────────────┬─────────────────────┐                                                                                                                                                                                                                                                                            
│   Aspect    │        Batch        │     Interactive     │                                                                                                                                                                                                                                                                            
├─────────────┼─────────────────────┼─────────────────────┤                                                                                                                                                                                                                                                                            
│ Envelope    │ UNB/UNZ, UNH/UNT    │ UIB/UIZ, UIH/UIT    │                                                                                                                                                                                                                                                                            
├─────────────┼─────────────────────┼─────────────────────┤                                                                                                                                                                                                                                                                            
│ Use case    │ Store-and-forward   │ Real-time dialogues │                                                                                                                                                                                                                                                                            
├─────────────┼─────────────────────┼─────────────────────┤                                                                                                                                                                                                                                                                            
│ Directories │ edmd/, edsd/, edcd/ │ idmd/, idsd/, idcd/ │                                                                                                                                                                                                                                                                            
├─────────────┼─────────────────────┼─────────────────────┤                                                                                                                                                                                                                                                                            
│ Examples    │ INVOIC, ORDERS      │ AVLREQ, IHCEBI      │                                                                                                                                                                                                                                                                            
└─────────────┴─────────────────────┴─────────────────────┘       

## Acknowledgments: CONTRL & APERAK

EDIFACT has two acknowledgment mechanisms at different levels:

| Message | Level | Purpose | X12 Equivalent |
|---------|-------|---------|----------------|
| **CONTRL** | Syntax | Confirms receipt, reports syntax/structure errors | 997/999 |
| **APERAK** | Application | Reports business-level errors/status | 824 |

### CONTRL - Syntax Acknowledgment

Reports whether the interchange was syntactically valid. Sent automatically by EDI systems.

```
UNH+1+CONTRL:D:3:UN'
UCI+12345+SENDER+RECEIVER+7'       ← Interchange response
UCM+1+INVOIC:D:23A:UN+7'           ← Message response
UCS+5+16'                          ← Segment error (optional)
UCD+1+3039+12'                     ← Element error (optional)
UNT+5+1'
```

**Key Segments:**

| Segment | Purpose |
|---------|---------|
| UCI | Interchange response (references UNB) |
| UCM | Message response (references UNH) |
| UCF | Functional group response (references UNG) |
| UCS | Segment error pointer |
| UCD | Data element error |

**Action Codes (UCI/UCM element 3):**

| Code | Meaning |
|------|---------|
| 4 | Rejected |
| 7 | Acknowledged |
| 8 | Received but not processable |

**Common Error Codes (UCS/UCD):**

| Code | Meaning |
|------|---------|
| 12 | Invalid value |
| 13 | Missing required data |
| 14 | Value not supported |
| 16 | Too many constituents |
| 35 | Too many repetitions |
| 37 | Invalid character |

### APERAK - Application Error/Acknowledgment

Reports business-level processing results. Sent by the application after processing.

```
UNH+1+APERAK:D:96A:UN'
BGM+313+ACK001+9'                  ← Acknowledgment doc
DTM+137:20240115:102'              ← Date
RFF+ACW:INVOIC-001'                ← Reference to original
ERC+12:131'                        ← Error code
FTX+AAO+++Invoice total mismatch'  ← Free text explanation
UNT+6+1'
```

**Use Cases:**
- Invoice rejected due to PO mismatch
- Order cannot be fulfilled (out of stock)
- Document requires correction
- Positive business acknowledgment

**Key Segments:**

| Segment | Purpose |
|---------|---------|
| BGM | Beginning of message (doc type 313=ACK) |
| RFF | Reference to original document |
| ERC | Application error code |
| FTX | Free text error description |

**When to Use Which:**

| Scenario | Response |
|----------|----------|
| Malformed EDI, bad syntax | CONTRL with error |
| Valid EDI, business error | APERAK |
| Valid EDI, processed OK | CONTRL (7) or APERAK (optional) |

## Key Differences from X12

| Aspect | X12 | EDIFACT |
|--------|-----|---------|
| **Field notation** | Simple position (ISA06) | Composite/component (S002.0004) |
| **Separators** | Fixed in ISA16 | Defined in UNA |
| **Functional group** | Always present (GS/GE) | Optional (UNG/UNE) |
| **Partner fields** | Fixed 15 chars | Variable length |
| **Test indicator** | P/T in ISA15 | 1/blank in UNB.0035 |
| **Reference format** | 9 digits zero-filled | Variable length |
| **Syntax ACK** | 997/999 | CONTRL |
| **Application ACK** | 824 | APERAK |

