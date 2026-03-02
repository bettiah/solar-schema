## HIPAA ASC X12 Standards for Electronic Data Interchange TR3: 10 or so T Sets

Claims and Encounters:

837P (Professional) — for professional services (physicians, therapists, etc.)
837I (Institutional) — institutional services (hospitals, skilled nursing facilities)
837D (Dental)

Payments:

835 (Health Care Claim Payment/Advice) — electronic remittance advice explaining how claims were adjudicated and paid

Eligibility:

270 — eligibility/benefit inquiry (asking a payer whether a patient is covered)
271 — eligibility/benefit response (status, benefit details, copays, and deductibles)

Claim Status:

276 — claim status inquiry
277 — claim status response, (paid, denied, pending) and adjudication
(there's also a 277CA variant for unsolicited claim acknowledgments)

Referrals and Authorizations:

278 — health care services review (prior authorization requests and responses); CMS replacement FHIR Claim

Enrollment:

834 — benefit enrollment and maintenance (enrolling members in health plans, adding/dropping dependents, etc.)

Premium Payments:

820 — payroll deducted and other group premium payment

## FHIR counterparts

| X12 | Purpose | FHIR Resource(s) | Da Vinci IG |
|-----|---------|-------------------|-------------|
| 837P/I/D | Healthcare Claim Submission | `Claim`, `Patient`, `Practitioner`, `Organization`, `Coverage` | [CARIN Blue Button (C4BB)](http://hl7.org/fhir/us/carin-bb/) |
| 835 | Remittance Advice / EOB | `ExplanationOfBenefit`, `ClaimResponse`, `PaymentReconciliation` | [CARIN Blue Button (C4BB)](http://hl7.org/fhir/us/carin-bb/) |
| 270 | Eligibility Inquiry | `CoverageEligibilityRequest`, `Coverage`, `Patient` | [HRex](http://hl7.org/fhir/us/davinci-hrex/) |
| 271 | Eligibility Response | `CoverageEligibilityResponse`, `Coverage` | [HRex](http://hl7.org/fhir/us/davinci-hrex/) |
| 276 | Claim Status Inquiry | search on `Claim`/`ClaimResponse`, or `Task` | — |
| 277 | Claim Status Response | `ClaimResponse` | — |
| 278 | Prior Auth Request/Response | `Claim` (use=preauthorization), `ClaimResponse`, PAS `Bundle` | [PAS STU 2.0.1](https://build.fhir.org/ig/HL7/davinci-pas/en/) |
| 834 | Benefit Enrollment | `Coverage`, `Patient`, `RelatedPerson`, `Organization` | — |
| 820 | Premium Payment | `PaymentNotice`, `PaymentReconciliation` | — |

## CMS-0057-F: CMS Interoperability and Prior Authorization Final Rule; released January 17, 2024
 
impacted payers: Medicare Advantage orgs, Medicaid/CHIP FFS programs, Medicaid managed care plans, CHIP managed care entities, and QHP issuers on FFEs 

build and maintain five HL7 FHIR-based APIs
1. Patient Access API 
2. Provider Access API
3. Provider Directory API
4. Payer-to-Payer API 
5. Prior Authorization API: 3 IGs - CRD -> DTR -> PAS

CRD: Coverage Requirement Discovery. Does this service even need prior auth?
- clinician orders a service in their EHR - CDS Hooks call fires to the payer in real time
- The payer responds with coverage information — whether PA is required, whether the provider is in-network, whether there are alternative therapies, or whether there are documentation requirements
- at point of treatment - before treatment 
- CRD STU 2.0.1

DTR (Documentation Templates and Rules) : What documentation does the payer need?
- CRD indicates PA is required, DTR launches a SMART on FHIR app within the EHR that presents payer-specific questionnaires. 
- DTR can auto-populate fields by pulling data already in the patient's record (via CQL queries)
- DTR STU 2.0.0

PAS (Prior Authorization Support): Here's my request — what's your decision?
- https://build.fhir.org/ig/HL7/davinci-pas/en/
- PAS STU 2.0.1
- x21 278

Inferno testing framework


## PAS https://build.fhir.org/ig/HL7/davinci-pas/en/usecases.html

PAS Claim submit:
- EHR creates Claim bundle 
- converts it into an X12N 278 and zero or more additional unsolicited 275 transactions 
- executes them against the target payer system
- takes 278 response and converts it into a response FHIR Bundle containing a ClaimResponse
