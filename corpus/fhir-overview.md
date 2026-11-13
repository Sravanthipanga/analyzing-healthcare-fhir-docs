# FHIR Overview

## What FHIR Is

FHIR (Fast Healthcare Interoperability Resources) is a standard created by HL7 for exchanging healthcare information electronically. It was designed to combine the best features of HL7 Version 2 and HL7 CDA with modern web technology: FHIR data is exchanged over a RESTful API using JSON or XML, which makes it far easier for web and mobile developers to work with than older healthcare standards.

## Resources

The basic building block of FHIR is the **resource**. A resource is a small, self-contained unit of healthcare information with a well-defined structure, such as a `Patient`, an `Observation` (a lab result or vital sign), an `Encounter` (a visit), a `Condition` (a diagnosis or problem), or a `MedicationRequest` (a prescription). FHIR R4 defines more than 140 resource types, but a small core set covers the majority of real-world use cases.

Every resource has:

- A unique `id` assigned by the server that stores it.
- A `meta` section carrying metadata such as `versionId`, `lastUpdated`, and the profiles the resource conforms to.
- A human-readable `text` narrative with a summary of the resource's content.
- Structured data elements, many of which are shared **data types** such as `HumanName`, `Identifier`, `Address`, `CodeableConcept`, and `Reference`.
- An `resourceType` field naming the type, for example `"resourceType": "Patient"`.

Resources link to each other using **references**. A `MedicationRequest`, for example, points to its subject with `"subject": {"reference": "Patient/123"}`. This simple, URL-based linking model mirrors how the web itself works.

## The RESTful API

FHIR servers expose resources through a RESTful API built on standard HTTP operations:

- `GET /Patient/123` reads a single resource by id.
- `POST /Patient` creates a new resource.
- `PUT /Patient/123` updates a resource (or creates it with a known id).
- `PATCH /Patient/123` applies a partial update.
- `DELETE /Patient/123` removes a resource.
- `GET /Patient?name=Example` searches for resources matching criteria.

Search is a first-class part of the specification: every resource type defines standard **search parameters** such as `name`, `birthdate`, and `identifier` for `Patient`. Successful reads return HTTP 200 with the resource as JSON; creates return 201 with a `Location` header. When an operation fails, the server returns an `OperationOutcome` resource describing errors, warnings, and informational messages.

## Formats: JSON and XML

FHIR resources can be represented in both JSON and XML, and the two representations are fully equivalent. JSON is by far the most common in modern integrations. A minimal Patient in JSON looks like:

```json
{
  "resourceType": "Patient",
  "id": "example",
  "name": [{ "family": "Example", "given": ["Jane"] }],
  "gender": "female",
  "birthDate": "1985-04-12"
}
```

Clients negotiate the format with the `Accept` header, using the media types `application/fhir+json` or `application/fhir+xml`.

## Versions: R4 and R5

FHIR has been published in several versions. **R4** (published in 2019) is the first version with normative content — parts of the specification that HL7 guarantees will not change incompatibly — and it is the version most widely implemented in production systems and required by regulations such as the US ONC Cures Act rules. **R5** (published in 2023) adds new resources and refinements but keeps most R4 patterns intact. Because implementations move slowly in healthcare, new projects overwhelmingly target R4 unless they have a specific need for an R5 feature. Resources written against different FHIR versions are not automatically interoperable; servers advertise their version and capabilities in a `CapabilityStatement` resource served from the `/metadata` endpoint.

## Capability Statement

Every FHIR server publishes a `CapabilityStatement` at `GET /metadata`. It declares which resource types the server supports, which search parameters are implemented, which interactions (read, search, create, update, and so on) are available, and the FHIR version in use. Client applications should read this statement rather than assuming full specification support, because real servers implement different subsets of FHIR.
