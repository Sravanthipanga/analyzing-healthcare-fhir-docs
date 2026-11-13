# The MedicationRequest Resource

## Purpose

The `MedicationRequest` resource represents an order or prescription for a medication: a request that a patient be supplied with and take a medication. It covers inpatient orders, outpatient prescriptions sent to a pharmacy, and over-the-counter recommendations recorded in the chart. Related resources complete the picture: `MedicationDispense` records that a pharmacy supplied the medication, `MedicationAdministration` records doses actually given, and `MedicationStatement` records what a patient reports taking.

## Key Elements

- **`status`** — the state of the order: `active`, `on-hold`, `cancelled`, `completed`, `entered-in-error`, `stopped`, `draft`, or `unknown`. Only active requests should be dispensed against.
- **`statusReason`** — a code explaining a non-active status, for example why a prescription was stopped (adverse reaction, therapy changed).
- **`intent`** — what kind of request this is, and a crucial distinguishing element: `proposal` (a suggestion, not yet an order), `plan` (an intended future action), `order` (an authorized, actionable request), `original-order`, `reflex-order`, `filler-order`, and `instance-order`. Decision-support systems commonly create proposals; a clinician converts them into orders.
- **`medication[x]`** — the medication itself, either `medicationCodeableConcept` coded in **RxNorm** (for example RxNorm 1049625 for a specific packaged product, or an ingredient-level code) or `medicationReference` pointing to a `Medication` resource that describes the drug, its form, and its ingredients in detail.
- **`subject`** — a reference to the `Patient` who should receive the medication.
- **`dosageInstruction`** — how the patient should take it. Each instruction can include `text` (free-text directions such as "Take one tablet by mouth twice daily"), a structured `timing` (frequency and period, for example every 12 hours), a `route` CodeableConcept (for example oral, intravenous), and a `doseAndRate` with a `doseQuantity` such as 500 mg. One request may have several dosage instructions for tapering schedules.
- **`dispenseRequest`** — instructions for the pharmacy: `quantity` to dispense (for example 60 tablets), `expectedSupplyDuration` (for example 30 days), `numberOfRepeatsAllowed` (refills), and a `validityPeriod` for the prescription.
- **`authoredOn`** — when the prescription was written.
- **`requester`** — the Practitioner (or other actor) who ordered it; **`recorder`** records who entered it.
- **`reasonCode`** / **`reasonReference`** — why the medication was ordered, typically the Condition it treats.
- **`priorPrescription`** — a reference to the MedicationRequest this one replaces, forming a chain for renewals and changes.
- **`basedOn`**, **`groupIdentifier`** — links to the care plan or order group the request belongs to.
- **`courseOfTherapyType`** — for example continuous long-term therapy versus a short acute course such as a 7-day antibiotic.
- **`substitution`** — whether substitution (for example generic substitution) is allowed, and why or why not.
- **`encounter`** — the encounter during which the order was placed.

## Example

```json
{
  "resourceType": "MedicationRequest",
  "id": "rx-1",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": { "coding": [{ "system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "197361", "display": "Metformin hydrochloride 500 MG Oral Tablet" }] },
  "subject": { "reference": "Patient/example" },
  "authoredOn": "2024-03-04",
  "requester": { "reference": "Practitioner/dr-example" },
  "reasonReference": [{ "reference": "Condition/diabetes-1" }],
  "dosageInstruction": [{
    "text": "Take one tablet by mouth twice daily with meals",
    "timing": { "repeat": { "frequency": 2, "period": 1, "periodUnit": "d" } },
    "route": { "coding": [{ "system": "http://snomed.info/sct", "code": "26643006", "display": "Oral route" }] },
    "doseAndRate": [{ "doseQuantity": { "value": 1, "unit": "tablet" } }]
  }],
  "dispenseRequest": {
    "quantity": { "value": 60, "unit": "tablet" },
    "expectedSupplyDuration": { "value": 30, "unit": "days", "system": "http://unitsofmeasure.org", "code": "d" },
    "numberOfRepeatsAllowed": 3
  }
}
```

## Searching MedicationRequests

Typical searches use `patient`, `status`, `intent`, `code` (the medication code), and `authoredon` (the date written). A "current medication list" query is usually `GET /MedicationRequest?patient=example&status=active&intent=order`, sometimes combined with the patient's MedicationStatements for completeness, because prescriptions written outside the system only appear as statements.
