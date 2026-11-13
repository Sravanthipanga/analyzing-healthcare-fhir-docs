# Bundles and Transactions

## What a Bundle Is

The `Bundle` resource is a container: a single FHIR resource whose `entry` list holds other resources. Bundles do not have clinical meaning of their own; they are how FHIR packages collections for transport — the result of a search, a document, a message, or a group of changes that must be applied together. Every entry has a `fullUrl` (a URI identifying the resource within the bundle) and a `resource`.

## Bundle Types

The `type` element declares how the bundle should be interpreted:

- **`searchset`** — the result of a search or read-history operation. Each entry holds one matching resource, and entries may also include resources pulled in by `_include` (marked with `search.mode` of `include`) and an `OperationOutcome` entry (`search.mode` of `outcome`) carrying warnings. The bundle's `total` element gives the full count of matches, which can exceed the number of entries on one page; `link` elements with relations `self`, `next`, `previous`, `first`, and `last` support paging.
- **`transaction`** — a set of creates, updates, and deletes that the server must process as a single atomic unit: either everything succeeds or everything is rolled back. Each entry carries a `request` element with the HTTP `method` (`POST`, `PUT`, `PATCH`, `DELETE`), the `url` (for example `Patient` or `Patient/123`), and optional `ifNoneExist` or `ifMatch` conditional headers. The server responds with a `transaction-response` bundle whose entries carry status codes per request.
- **`batch`** — like a transaction, but each entry is processed independently: some may succeed and others fail, and the response is a `batch-response` bundle with per-entry results. Use batch when atomicity is not required and partial success is acceptable.
- **`document`** — an attested, immutable collection (a clinical document) whose first entry is a `Composition` resource that organizes the rest.
- **`message`** — a bundle sent as a message, whose first entry is a `MessageHeader` defining the event and sender.
- **`history`** — a list of versions of resources, as returned by a history operation.
- **`collection`** — a bundle assembled for a purpose other than the above, with no processing rules attached.

## Transaction Details

Transactions are how clients create interdependent resources in one round trip — for example, a Patient together with three Observations that reference it. Because the server has not yet assigned ids at the time the bundle is authored, entries reference each other using **temporary UUIDs** in `fullUrl`:

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "fullUrl": "urn:uuid:9c2d1b6e-0000-4000-8000-000000000001",
      "resource": { "resourceType": "Patient", "name": [{ "family": "Example", "given": ["Jane"] }] },
      "request": { "method": "POST", "url": "Patient" }
    },
    {
      "fullUrl": "urn:uuid:9c2d1b6e-0000-4000-8000-000000000002",
      "resource": {
        "resourceType": "Observation",
        "status": "final",
        "code": { "coding": [{ "system": "http://loinc.org", "code": "8867-4" }] },
        "subject": { "reference": "urn:uuid:9c2d1b6e-0000-4000-8000-000000000001" },
        "valueQuantity": { "value": 72, "unit": "beats/minute" }
      },
      "request": { "method": "POST", "url": "Observation" }
    }
  ]
}
```

The server replaces the placeholder UUIDs with the real assigned ids and rewrites the references. Conditional creates use `ifNoneExist` with a search string — `POST Patient` with `ifNoneExist: identifier=http://example-hospital.org/mrn|MRN-100234` creates the patient only if no patient with that identifier exists, preventing duplicates when a transaction is retried.

## Rules and Limits

Within a transaction, entries are processed in order and the bundle either fully succeeds or fully fails with an `OperationOutcome`. Servers may impose size limits on bundles, and references between entries must resolve either to another entry's `fullUrl` or to a resource that already exists on the server. Transactions are posted to the server's base URL (`POST /`), not to a `/Bundle` endpoint.
