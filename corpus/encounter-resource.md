# The Encounter Resource

## Purpose

The `Encounter` resource represents an interaction between a patient and healthcare provider(s) for the purpose of providing healthcare services: a hospital admission, an emergency department visit, an outpatient clinic appointment, a telehealth session, or a home health visit. Other clinical resources — observations, conditions, procedures — are commonly tied to the encounter in which they occurred through their `encounter` element, which gives them clinical context.

## Key Elements

- **`status`** — the lifecycle state of the encounter. Core values are `planned`, `arrived`, `triaged`, `in-progress`, `onleave`, `finished`, `cancelled`, and `entered-in-error`. The `statusHistory` backbone element records previous statuses and the periods during which they applied, since an encounter typically moves from `planned` to `arrived` to `in-progress` to `finished`.
- **`class`** — the setting of the encounter, coded from a value set drawn from HL7 v2 table 0004 concepts. Common codes include `AMB` (ambulatory/outpatient), `EMER` (emergency), `IMP` (inpatient), `HH` (home health), and `VR` (virtual/telehealth). Because settings get more specific over time (a patient arrives as emergency and is then admitted as inpatient), `classHistory` records how the class changed.
- **`type`** — the specific kind of encounter, such as a cardiology consultation or an annual physical, usually coded with SNOMED CT.
- **`subject`** — a reference to the `Patient` (occasionally a `Group`) the encounter is about.
- **`period`** — a `Period` with `start` and `end` date-times bracketing the encounter. The `end` is absent while the encounter is still in progress.
- **`participant`** — the people and organizations involved. Each entry pairs a `type` (for example `ADM` admitter, `ATND` attender, `CON` consultant) with an `individual` reference to a `Practitioner`, `PractitionerRole`, or `RelatedPerson`.
- **`diagnosis`** — conditions and problems relevant to this encounter. Each entry has a `condition` reference to a `Condition` or `Procedure`, a `use` code distinguishing the role of the diagnosis (such as `admission`, `billing`, or `discharge`), and a `rank` indicating priority — rank 1 conventionally means the principal diagnosis for the encounter.
- **`location`** — the physical locations where the patient was during the encounter, each with a `location` reference and a `period`; a hospital encounter might list an emergency bay, then a ward bed, then a discharge lounge.
- **`serviceProvider`** — the organization responsible for the encounter, such as the hospital.
- **`reasonCode`** and **`reasonReference`** — why the encounter took place: the presenting complaint or the condition that prompted the visit.
- **`hospitalization`** — details specific to inpatient encounters, including `admitSource` (for example, emergency department or physician referral), `dischargeDisposition` (for example, discharged to home or expired), and the `origin` and `destination` locations.

## Example

```json
{
  "resourceType": "Encounter",
  "id": "visit-1",
  "status": "finished",
  "class": { "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB" },
  "type": [{ "coding": [{ "system": "http://snomed.info/sct", "code": "185389009", "display": "Follow-up visit" }] }],
  "subject": { "reference": "Patient/example" },
  "period": { "start": "2024-03-04T09:00:00Z", "end": "2024-03-04T09:40:00Z" },
  "participant": [{ "individual": { "reference": "Practitioner/dr-example" } }],
  "diagnosis": [{ "condition": { "reference": "Condition/cold-1" }, "use": { "coding": [{ "code": "billing" }] }, "rank": 1 }]
}
```

## Encounters and Episodes

An `EpisodeOfCare` groups multiple encounters that address the same longer-term care need — for example, all visits related to a pregnancy or a course of chemotherapy. An Encounter links upward with its `episodeOfCare` element. Part-of relationships also exist between encounters themselves: a large hospital stay encounter can have smaller unit encounters as children via the `partOf` element.

## Searching Encounters

Common search parameters include `patient` (or `subject`), `date` (matches encounters overlapping the given range), `status`, `class`, `type`, and `location`. A typical query for a patient's visits in 2024 is `GET /Encounter?patient=example&date=ge2024-01-01&date=lt2025-01-01`.
