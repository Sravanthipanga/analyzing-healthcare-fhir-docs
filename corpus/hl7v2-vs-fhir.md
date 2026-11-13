# HL7 Version 2 versus FHIR

## Two Generations of Interoperability

HL7 Version 2 (v2) and FHIR solve the same problem — moving clinical data between systems — with designs separated by three decades of technology. HL7 v2 arrived in the late 1980s and became the most widely deployed healthcare integration standard in the world. FHIR, first drafted in 2011 and normative from R4 (2019), re-imagines the same exchanges using web standards.

## HL7 v2: Messages and Segments

HL7 v2 exchanges **messages**, each composed of **segments** — lines of pipe-delimited fields. The message type and trigger event are named by a three-letter code: an `ADT^A01` is a patient admission, an `ORM^O01` is an order, an `ORU^R01` carries observation results. Segments begin with a three-character id: `MSH` (message header), `PID` (patient identification), `PV1` (patient visit), `OBR` (observation request), `OBX` (observation result), `ORC` (common order), and `NK1` (next of kin).

Fields within a segment are separated by the pipe character `|`, components by `^`, and repetitions by `~`:

```
PID|1||MRN-100234^^^ExampleHospital^MR||Example^Jane||19850412|F|||1200 Example Street^^Springfield^IL^62701^US
```

This PID segment carries the patient's id, name (Example, Jane), birth date, administrative sex, and address positionally — meaning depends on counting delimiters, and the same field can mean different things on different systems. Messages traditionally travel over **MLLP** (Minimal Lower Layer Protocol) — raw TCP sockets with simple framing — and are routed, transformed, and filtered by **interface engines** such as Mirth Connect or Rhapsody. There is no query API: v2 is a push-only, event-driven model in which each system receives copies of the events it subscribes to and maintains its own database.

## FHIR: Resources and REST

FHIR models data as addressable **resources** with JSON (or XML) representations and exposes them through a queryable REST API. Data is pulled as well as pushed: a client can search `GET /Observation?patient=123&code=8867-4` at any time rather than waiting for a feed. Resources carry explicit field names, strong data types, and standard terminologies; servers declare their capabilities in a `CapabilityStatement`; and modern authorization uses OAuth 2.0 via SMART on FHIR — none of which exists natively in v2.

Conceptually, the mappings are recognizable:

- The **PID** segment maps to the `Patient` resource.
- **PV1** (visit) maps to `Encounter`.
- **OBX** observation results map to `Observation`.
- **ORC/ORM** orders map to `ServiceRequest` and `MedicationRequest`.
- An `ADT^A01` admission event roughly corresponds to creating an Encounter with status `in-progress` for a patient.

The shapes differ, though: one v2 message bundles many segments about one event, while FHIR decomposes the same information into individually addressable resources that links connect.

## Comparing Strengths

**HL7 v2 strengths**: battle-tested, extremely widely installed, simple to produce, and well understood by hospital IT. Its flexibility is also its famous weakness — every implementation negotiates local variations ("dialects"), sometimes called the v2 paradox: once you have seen one ADT feed, you have seen exactly one ADT feed. Field optionality and local Z-segments (custom segments) make feeds from two hospitals incompatible in detail even when both claim v2 compliance.

**FHIR strengths**: developer-friendly, self-describing, queryable, and granular — clients request only the resources they need, and the profile/validation ecosystem makes conformance testable. Its weakness is relative immaturity in some domains: certain workflows that v2 handles routinely (real-time ADT event feeds at hospital scale, for example) still commonly run on v2, with FHIR APIs layered on top for app access.

## Migration Considerations

Most organizations do not rip and replace; they coexist:

1. **Façade pattern**: put a FHIR API in front of systems fed by v2. The interface engine continues receiving ADT and ORU messages, transforms them into resources, and stores them in a FHIR server; apps consume FHIR while legacy feeds keep flowing. This is the most common migration path.
2. **Mapping**: v2-to-FHIR mapping is well documented for demographics, encounters, and results, but code systems need attention — v2's local tables must be mapped to terminologies such as LOINC and SNOMED CT.
3. **Eventing gap**: where consumers need push semantics, FHIR's Subscription resource can notify clients of changes, but adoption varies; many designs keep v2 feeds for real-time eventing and use FHIR for query and app access.
4. **Testing**: validate mapped resources against the target implementation guide's profiles, not just base FHIR, before go-live.

The practical summary: HL7 v2 moves events between known systems inside an institution; FHIR opens the same data to applications, patients, and partners through standard web APIs. Modern architectures typically run both.
