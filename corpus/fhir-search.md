# FHIR Search

## The Basics

Search is the primary way clients find resources in FHIR: `GET /Patient?name=Example&birthdate=1985-04-12` reads as a query string of **search parameters**, and the server returns a `searchset` Bundle containing matching resources. Each resource type defines its own parameters (plus universal ones like `_id` and `_lastUpdated`), and each parameter has a type that determines how matching and prefixes work.

## Parameter Types

- **String** parameters such as `name`, `family`, and `address-city` match flexibly: servers generally do case-insensitive prefix matching, and some support phonetic matching.
- **Token** parameters match coded values and identifiers as `system|value`. `identifier=http://example-hospital.org/mrn|MRN-100234` matches on both parts; omitting the system (`identifier=MRN-100234`) matches the value in any system, and `|MRN-100234`... the form `system|` alone matches any value in that system. Code parameters such as Observation `code` are tokens against the coding's system and code.
- **Date** parameters support prefix operators because healthcare queries are usually ranges: `eq`, `ne`, `gt`, `lt`, `ge`, `le`, `sa` (starts after), `eb` (ends before), and `ap` (approximately). `Observation?date=ge2024-01-01&date=lt2025-01-01` finds 2024 observations — repeating the same parameter ANDs the conditions.
- **Number** and **quantity** parameters use the same comparison prefixes: `value-quantity=gt100` or with units `value-quantity=gt100|http://unitsofmeasure.org|mg`.
- **Reference** parameters match links: `Observation?subject=Patient/123`, and most servers also accept just `patient=123` for patient-centric parameters.
- **Composite** parameters match two values together, for example `code-value-quantity` on Observation, which finds a specific test with a value in a range in a single parameter.

Multiple different parameters are combined with AND. Comma-separated values in one parameter are OR: `status=final,amended` matches either. There is no general NOT or arbitrary boolean logic; clients use multiple queries and client-side filtering.

## Modifiers

Modifiers refine a parameter, written after a colon:

- `:exact` on strings requires exact match: `name:exact=Example`.
- `:contains` on strings matches substrings.
- `:missing` on any parameter finds resources where the element is present or absent: `birthdate:missing=false`.
- `:not`, `:in`, `:not-in`, `:below`, `:above` apply to token parameters against value sets and hierarchies — for example `code:in=http://example.org/ValueSet/cardiac-tests` or finding conditions in a SNOMED sub-tree with `:below`.
- `:identifier` and type modifiers on references restrict which target is matched, for example `subject:Patient=123`.

## Chaining and Reverse Chaining

**Chaining** searches across references using dot notation: `Observation?subject.name=Example` finds observations whose subject (a Patient) has the given name; longer chains like `Encounter?patient.organization.name=General` are possible. **Reverse chaining** with `_has` searches from the other direction: `Patient?_has:Observation:patient:code=8867-4` finds patients who have a heart-rate observation. Chained and `_has` queries are expressive but expensive; not all servers support them fully.

## Including Related Resources

`_include` asks the server to also return resources referenced by the results: `Observation?_include=Observation:patient` returns each observation's patient in the same bundle (marked `search.mode = include`). `_include:iterate` follows includes recursively. The reverse, `_revinclude`, returns resources that point at the results — `Patient?_revinclude=Observation:patient` returns the patient and all their observations in one call. These parameters prevent N+1 query patterns.

## Sorting and Paging

`_sort` orders results: `_sort=-date,code` sorts by date descending then code ascending; the minus prefix means descending, and only some parameters are sortable. `_count` sets page size, and the returned Bundle's `link` relations (`next`, `previous`, `first`, `last`) walk through pages; `Bundle.total` holds the full match count. `_summary=true` (or `count`, `data`, `text`) returns a lightweight form of resources, and `_elements` picks specific elements to return.

## Total and Accuracy

By default `total` may be an estimate (`Bundle.total` present with `meta` accuracy hints) or omitted for speed. Clients needing exact counts on large servers can pass `_total=accurate`, accepting the extra cost.
