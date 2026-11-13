# The Condition Resource

## Purpose

The `Condition` resource represents a clinical condition, problem, diagnosis, or other health concern that applies to a patient over time: diabetes, hypertension, a fractured wrist, or a suspected infection under investigation. Where `Observation` captures a point-in-time measurement, Condition captures a state that persists. Conditions are the backbone of problem lists, encounter diagnoses, and billing workflows.

## Key Elements

- **`clinicalStatus`** — where the condition is in its lifecycle: `active`, `recurrence`, `relapse`, `inactive`, `remission`, or `resolved`. A condition with no `clinicalStatus` should be treated cautiously: the element may be omitted only when the status genuinely is not known, and the FHIR specification warns consumers not to assume such conditions are active. An allergy that is no longer relevant, for instance, would move from `active` to `resolved`.
- **`verificationStatus`** — how confident clinicians are that the condition is real: `unconfirmed`, `provisional`, `differential`, `confirmed`, `refuted`, or `entered-in-error`. A working diagnosis during a visit is often `provisional`; it becomes `confirmed` when test results arrive. A condition ruled out is marked `refuted`, not deleted, preserving the clinical audit trail.
- **`category`** — classifies the condition's role: `problem-list-item` (it belongs on the patient's problem list), `encounter-diagnosis` (it was addressed at a specific encounter), or `health-concern`.
- **`code`** — a `CodeableConcept` identifying the condition. Diagnoses are most often coded in **SNOMED CT** for clinical detail (for example 38341003 for hypertensive disorder) and mapped to **ICD-10** for billing (for example I10 for essential hypertension). A single CodeableConcept can carry both codings at once.
- **`subject`** — a reference to the `Patient` who has the condition.
- **`onset[x]`** — when the condition began: `onsetDateTime`, `onsetAge`, `onsetPeriod`, `onsetRange`, or a descriptive `onsetString` such as "about two weeks ago".
- **`abatement[x]`** — when the condition stopped or resolved, in parallel forms (`abatementDateTime`, `abatementAge`, and so on). Setting an abatement is usually paired with moving `clinicalStatus` to `resolved` or `inactive`.
- **`recordedDate`** — when the condition was first recorded in the system, which may be later than the onset.
- **`severity`** — a coded severity such as mild, moderate, or severe, typically from SNOMED CT.
- **`stage`** — summaries of staging assessments, for example a cancer stage, each pointing at the Observation or other resource that supports it.
- **`evidence`** — references to Observations, reports, or other resources that support the diagnosis.
- **`encounter`** — the encounter during which the condition was first asserted.
- **`asserter`** and **`recorder`** — who asserted the diagnosis and who entered it into the record.

## Example

```json
{
  "resourceType": "Condition",
  "id": "htn-1",
  "clinicalStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active" }] },
  "verificationStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed" }] },
  "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-category", "code": "problem-list-item" }] }],
  "code": { "coding": [
    { "system": "http://snomed.info/sct", "code": "38341003", "display": "Hypertensive disorder" },
    { "system": "http://hl7.org/fhir/sid/icd-10", "code": "I10", "display": "Essential hypertension" }
  ] },
  "subject": { "reference": "Patient/example" },
  "onsetDateTime": "2019-06-15",
  "recordedDate": "2019-06-20"
}
```

## Problem Lists vs Encounter Diagnoses

The same resource serves both purposes, distinguished by `category`. Problem list conditions are the curated, longitudinal set of ongoing issues; systems typically filter with `GET /Condition?patient=example&category=problem-list-item&clinical-status=active`. Encounter diagnoses additionally carry the billing role and rank recorded in `Encounter.diagnosis`. Note the search parameter spellings: `clinical-status` (with a hyphen) is the parameter name for `clinicalStatus`.

## Common Pitfalls

Do not treat the absence of a Condition as proof a patient does not have a problem: records are fragmented across systems. Do not resurrect `entered-in-error` or `refuted` conditions into problem lists. And when comparing conditions across systems, compare codes carefully — SNOMED CT has many near-synonyms, and granularity differs between sources.
