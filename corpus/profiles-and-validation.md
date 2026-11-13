# Profiles, StructureDefinitions, and Validation

## Why Profiles Exist

Base FHIR is deliberately permissive: most elements are optional, and coded elements often accept any code. Real interoperability requires agreement that is narrower — a US hospital and an app vendor must agree that a Patient always carries an identifier, a name, a birth date, and a gender from a specific set. FHIR expresses that agreement as **profiles**: constraint sets layered on top of base resource definitions.

## StructureDefinition

A profile is itself a FHIR resource: a `StructureDefinition`. It has a canonical `url` by which other artifacts reference it (for example `http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient`), a `baseDefinition` pointing at the resource or profile it constrains, and two views of its rules:

- The **differential** lists only what the profile changes relative to its base: tightened cardinalities, added constraints, terminology bindings, and new extension elements. Differentials are short and human-authored.
- The **snapshot** is the complete, flattened element list produced by merging the differential with its whole inheritance chain. Tools generate it; validation and code generation work from the snapshot.

Within these views, each `ElementDefinition` can specify:

- **Cardinality**: for example, Patient.name goes from `0..*` in base FHIR to `1..*` — at least one name is *required*.
- **Must-support flags**: elements marked must-support must be populated by producers when the data exists, and consumers must be able to process them meaningfully (not merely ignore them). Must-support is about behaviour obligations, not cardinality — a must-support element can still be absent when no data exists.
- **Bindings**: an element can be bound to a specific `ValueSet` with a strength (required, extensible, preferred, example).
- **Fixed and pattern values**: an element may be fixed to a constant (for example, a category code that must always be `vital-signs`).
- **Constraints**: invariants in FHIRPath, such as "a deceased patient must not have a future appointment".
- **Slicing**: rules for dividing a repeating element into named, individually constrained groups — for example, slicing Patient.identifier into distinct MRN and national-id slices, each with its own system and cardinality.
- **Extensions**: elements added beyond the base resource. An extension is defined by its own StructureDefinition with a URL; simple extensions carry one value, complex ones nest children. Data that is nationally or locally needed but not in the 80/20 base spec — race and ethnicity in US Core, for instance — travels as extensions.

## Implementation Guides

An **Implementation Guide (IG)** is the published package that ties it together: a set of profiles, value sets, examples, and narrative documentation for a specific use case and jurisdiction. Well-known IGs include **US Core** (the baseline profile set for US interoperability, referenced by ONC certification rules), **Da Vinci** guides for payer-provider exchange (prior authorization, payer data exchange), **CARIN** for consumer-directed exchange, and national programs in many other countries. When a server claims support for an IG, it is claiming its resources validate against those profiles.

## Validation

Servers declare the profiles a resource conforms to in `meta.profile`. Validation checks a resource against a profile's snapshot: cardinality, data types, bindings, fixed values, and FHIRPath invariants. It can be triggered explicitly with the **`$validate` operation** — `POST /Patient/$validate` with a candidate resource returns an `OperationOutcome` listing every error and warning without storing anything — or enforced on create/update by stricter servers. Clients and integration pipelines also validate offline using the official FHIR validator, published as a Java CLI by HL7, which loads IG packages from the FHIR package registry and validates resources with the same rules servers use.

## Authoring and Tooling

Profiles are commonly authored in **FSH (FHIR Shorthand)** and compiled with the SUSHI tool into StructureDefinition JSON, which eliminates the error-prone hand-writing of snapshots. IGs are built and published with the HL7 IG Publisher. Published packages are distributed through the FHIR package registry (packages.simplifier.net and packages.fhir.org), versioned like software libraries — because for implementers, that is exactly what they are.

## Practical Advice

Design integrations against profiles, not base FHIR: find the governing IG, read its must-support obligations, validate early with `$validate` or the validator CLI, and treat validation warnings about terminology bindings as real defects — they are what breaks the next consumer downstream.
