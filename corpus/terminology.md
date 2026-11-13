# Clinical Terminology in FHIR

## Why Terminology Matters

FHIR moves structure; **terminology** gives the values meaning. A blood pressure reading is only computable if everyone agrees which code means "systolic blood pressure". FHIR references several large external code systems, each with its own scope and canonical system URI, and provides data types and resources to bind them to elements.

## The Major Code Systems

- **LOINC** (system `http://loinc.org`) — Logical Observation Identifiers Names and Codes: names for laboratory tests, vital signs, and clinical measurements. Observation codes are usually LOINC: glucose is 2339-0, heart rate is 8867-4, systolic blood pressure is 8480-6.
- **SNOMED CT** (system `http://snomed.info/sct`) — the most comprehensive clinical terminology: diagnoses, procedures, findings, body sites. Condition and Procedure codes are usually SNOMED CT, for example hypertensive disorder is 38341003.
- **ICD-10** (system `http://hl7.org/fhir/sid/icd-10`) — the classification used for billing and epidemiology, for example I10 for essential (primary) hypertension. ICD-10 codes are coarser than SNOMED CT concepts; conditions often carry a SNOMED code for clinical use and an ICD-10 code for billing in the same element.
- **RxNorm** (system `http://www.nlm.nih.gov/research/umls/rxnorm`) — normalized names for medications in the US: ingredients, strengths, and dose forms. MedicationRequest's medication is usually coded in RxNorm.
- **UCUM** (system `http://unitsofmeasure.org`) — codes for units of measure used in Quantity values, for example `mg`, `mm[Hg]`, `/min`.
- **CPT** — procedure billing codes, widely used in US claims (licensed code system).

## Coding and CodeableConcept

A **`Coding`** is one code from one system: a `system` URI, a `code`, and a human-readable `display`. A **`CodeableConcept`** is the type used by most coded elements: a list of Codings (allowing the same concept expressed in several systems at once) plus a `text` field with the original human wording. For example, a condition might carry:

```json
{
  "coding": [
    { "system": "http://snomed.info/sct", "code": "38341003", "display": "Hypertensive disorder" },
    { "system": "http://hl7.org/fhir/sid/icd-10", "code": "I10", "display": "Essential hypertension" }
  ],
  "text": "Hypertension"
}
```

Consumers must be careful: multiple codings in one concept assert the *same* meaning in different systems — they are translations, not a list of different problems. Never treat each coding as a separate diagnosis.

## Value Sets and Binding Strengths

A **ValueSet** resource defines an intensional set of codes — for example, "all SNOMED codes that are descendants of hypertensive disorder" — by composing inclusions and filters over code systems, with expansions computed by a terminology server. Profiles bind elements to value sets with a **binding strength**:

- **`required`** — the value must come from the value set; anything else is invalid. Example: Patient.gender is required-bound to the small administrative gender code set.
- **`extensible`** — use a code from the value set if it covers the concept; a local code is allowed only when the value set has no suitable concept.
- **`preferred`** — the value set is recommended for interoperability, but other codes are not invalid.
- **`example`** — the value set is purely illustrative, a starting point for implementers.

Servers validate bindings according to the profiles they claim.

## Terminology Operations

FHIR defines standard terminology operations on `ValueSet` and `CodeSystem` resources: `$validate-code` checks whether a code belongs to a value set; `$expand` computes a value set's full code list; `$lookup` returns a code's properties and display; `$subsumes` asks whether one code subsumes another (is it an ancestor in the hierarchy); and `$translate` maps a code between systems using a `ConceptMap`. Dedicated terminology servers (for example, implementations backed by the full SNOMED and LOINC releases) usually provide these operations, because the code systems are far too large to embed in application code.

## Versioning

Code systems evolve: SNOMED CT releases twice a year, LOINC twice a year, and ICD-10 annually. A Coding may carry a `version` to pin the edition it came from. Analytics and decision support must be explicit about versions; a value set expansion from 2023 is not the same dataset as the 2025 expansion.
