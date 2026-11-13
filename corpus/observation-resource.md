# The Observation Resource

## Purpose

The `Observation` resource is the workhorse of clinical data in FHIR: it represents a measurement, a test result, a vital sign, a survey answer, or any other discrete observation made about a patient. Lab results, blood pressure readings, body weights, pain scores, and imaging findings all travel as Observations. Because so much clinical data flows through this one shape, understanding Observation is essential to working with FHIR.

## Key Elements

- **`status`** — the state of the result: `registered`, `preliminary`, `final`, `amended`, `corrected`, `cancelled`, or `entered-in-error`. Consumers should generally only trust `final` (and later `amended`/`corrected`) results for clinical decisions, and a corrected result supersedes the original.
- **`category`** — a high-level classification such as `vital-signs`, `laboratory`, `imaging`, `survey`, or `exam`. An Observation may carry several categories.
- **`code`** — a `CodeableConcept` saying what was measured. Laboratory tests are usually coded in **LOINC** (for example LOINC 2339-0 is glucose in blood), and vital signs have mandated LOINC codes in the FHIR vital signs profile (for example 8867-4 heart rate, 85354-9 blood pressure panel).
- **`subject`** — a reference to the `Patient` (or other subject) the observation is about.
- **`effective[x]`** — when the observation is clinically relevant: usually `effectiveDateTime`, sometimes `effectivePeriod` for measurements spanning an interval.
- **`value[x]`** — the result itself, in one of many types depending on the test:
  - `valueQuantity` — a number with a unit, for example `{ "value": 72, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min" }`. Units conventionally use UCUM codes.
  - `valueCodeableConcept` — a coded result, such as positive/negative.
  - `valueString`, `valueBoolean`, `valueInteger`, `valueRatio`, `valueRange`, `valueSampledData`, `valueTime`, `valueDateTime`, `valuePeriod`.
- **`component`** — for panel results measured together. A blood pressure Observation has two components: systolic (LOINC 8480-6) and diastolic (LOINC 8462-4), each with its own `code` and `value[x]`. Components keep the panel together as one Observation rather than scattering it across several.
- **`referenceRange`** — the normal interval for the result, with `low` and `high` quantities, optionally qualified by age or other criteria.
- **`interpretation`** — a coded flag such as `H` (high), `L` (low), or `N` (normal) relative to the reference range.
- **`dataAbsentReason`** — explains why there is no value, for example the test was not performed or the patient refused.
- **`method`**, **`bodySite`**, **`device`** — how, where, and with what the measurement was taken.
- **`derivedFrom`** — references to source resources the observation was calculated from.
- **`hasMember`** — groups related observations, for example the individual analytes of a lab panel, each of which is also its own Observation.

## Example: A Heart Rate Vital Sign

```json
{
  "resourceType": "Observation",
  "id": "hr-1",
  "status": "final",
  "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs" }] }],
  "code": { "coding": [{ "system": "http://loinc.org", "code": "8867-4", "display": "Heart rate" }] },
  "subject": { "reference": "Patient/example" },
  "effectiveDateTime": "2024-03-04T09:15:00Z",
  "valueQuantity": { "value": 72, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min" }
}
```

## Vital Signs Profile

The FHIR specification defines a vital signs profile that constrains Observation for common measurements: body temperature, heart rate, respiratory rate, blood pressure, oxygen saturation, body weight, height, and BMI. The profile fixes the `category` to `vital-signs` and requires specific LOINC codes, so a client can reliably find a patient's blood pressures with `GET /Observation?patient=example&code=85354-9`.

## Searching Observations

Key search parameters are `patient`, `code`, `category`, `date`, and `status`. Code search is token-based, so `GET /Observation?patient=example&code=http://loinc.org|8867-4` returns heart rate readings. Combining token and date parameters is the standard way to pull a trend for charting.
