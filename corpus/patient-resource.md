# The Patient Resource

## Purpose

The `Patient` resource represents a person who receives healthcare services: demographics and administrative information about an individual. It deliberately contains no clinical data — diagnoses live in `Condition`, measurements in `Observation` — because the Patient resource is the demographic anchor that almost every other resource references through its `subject` or `patient` element.

## Key Elements

- **`id`** — the server-assigned logical id of the resource, unique within the server's Patient collection.
- **`identifier`** — identifiers that belong to the patient in the real world, as opposed to the server id. A Patient typically has several: a medical record number (MRN), a national identifier, or an insurance member id. Each `Identifier` has a `system` (a URI naming the issuing authority, such as a hospital's MRN namespace), a `value`, and often a `type` code. Identifiers are the primary way systems match patients across organizations.
- **`active`** — a boolean indicating whether the patient record is in active use; records created in error are usually marked inactive rather than deleted.
- **`name`** — a list of `HumanName` elements. Each name has a `use` (`official`, `usual`, `maiden`, `nickname`), a `family` name, and one or more `given` names. Patients may have several names over time, so the resource keeps a list rather than a single value.
- **`gender`** — the administrative gender, coded `male`, `female`, `other`, or `unknown`. This is a required binding to a small fixed code set.
- **`birthDate`** — the date of birth as a FHIR `date`. It may be partial: `1985` or `1985-04` are valid when the full date is unknown.
- **`deceased[x]`** — either a boolean (`deceasedBoolean`) or the date and time of death (`deceasedDateTime`).
- **`address`** — a list of `Address` elements with `use` (such as `home` or `work`), `line` (street lines), `city`, `state`, `postalCode`, and `country`.
- **`telecom`** — contact points such as phone numbers and email addresses, each a `ContactPoint` with `system` (`phone`, `email`), `value`, and `use`.
- **`communication`** — the patient's preferred languages. Each entry has a `language` as a `CodeableConcept` (usually coded with BCP-47 language tags, for example `en` or `es`) and an optional `preferred` flag.
- **`maritalStatus`** — a `CodeableConcept` such as married, divorced, or unmarried.
- **`generalPractitioner`** — references to the patient's usual care providers (`Practitioner` or `Organization` resources).
- **`link`** — links to other Patient resources that represent the same person, for example a duplicate record (`type` `replaced-by` or `seealso`).

## Example

```json
{
  "resourceType": "Patient",
  "id": "example",
  "identifier": [
    { "system": "http://example-hospital.org/mrn", "value": "MRN-100234" }
  ],
  "active": true,
  "name": [{ "use": "official", "family": "Example", "given": ["Jane"] }],
  "gender": "female",
  "birthDate": "1985-04-12",
  "address": [{
    "use": "home",
    "line": ["1200 Example Street"],
    "city": "Springfield",
    "state": "IL",
    "postalCode": "62701",
    "country": "US"
  }],
  "communication": [{ "language": { "coding": [{ "system": "urn:ietf:bcp:47", "code": "en" }] }, "preferred": true }]
}
```

Note that this is entirely synthetic demonstration data: "Jane Example" is a fictional person.

## Searching for Patients

The Patient resource defines search parameters including `name`, `family`, `given`, `birthdate`, `gender`, `identifier`, `address`, and `phone`. Identifier search is token-based: `GET /Patient?identifier=http://example-hospital.org/mrn|MRN-100234` finds the patient by system and value. Name search is string-based and typically does prefix and phonetic matching depending on the server.

## Common Pitfalls

Patient matching is the classic integration problem: the same person may have records in many systems with slightly different names and identifiers. Consumers should match on strong identifiers first and treat name-and-birthdate matching as probabilistic. Consumers must also handle merged records — when two Patient resources are merged, one is marked inactive and linked to the survivor with `link.type` of `replaced-by`.
