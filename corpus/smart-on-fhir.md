# SMART on FHIR

## What SMART on FHIR Is

SMART on FHIR is the standard way third-party applications connect to EHR systems and FHIR servers with user authorization. It layers an authorization and app-launch framework on top of FHIR's REST API, using **OAuth 2.0** for authorization and **OpenID Connect (OIDC)** for identity. If you have seen a patient portal offer "connect an app", or a clinician launch a decision-support tool from inside the chart, that is almost certainly SMART on FHIR.

## The Two Launch Patterns

- **EHR launch**: the app is started from inside the EHR. The EHR redirects the user's browser to the app with two parameters: `iss` (the FHIR server base URL, which is also the authorization server's issuer) and `launch` (an opaque launch token identifying the session's context — which patient, encounter, and user are in play). The app exchanges the launch token during authorization and receives that context back in the token response.
- **Standalone launch**: the app starts outside the EHR (a patient opens it directly). The app itself begins the OAuth flow against a known FHIR endpoint, and the user picks a patient if the workflow requires one.

## OAuth 2.0 Flow

The authorization flow is the standard OAuth 2.0 authorization code grant:

1. The app redirects the browser to the authorization endpoint with its `client_id`, a `redirect_uri`, the requested `scope`, a `state` value, and an `aud` parameter naming the FHIR server.
2. The user authenticates (to the EHR's identity system) and approves the requested access.
3. The authorization server redirects back to the app with a short-lived `code`.
4. The app exchanges the code at the token endpoint — confidential clients authenticate with a client secret or a private-key JWT — and receives an `access_token`, a `refresh_token` where granted, and the launch context: `patient`, `encounter`, and (with OIDC) an `id_token` identifying the user.
5. The app calls the FHIR API with the access token as a Bearer token. Access tokens are short-lived (often minutes to an hour); refresh tokens allow long-lived patient-facing apps to renew silently.

Public clients (mobile and pure browser apps that cannot keep a secret) must use **PKCE** to protect the code exchange. Backend services that act without an interactive user use the separate **SMART Backend Services** profile: the client signs a JWT with its registered private key and receives a token scoped to system-level access.

## Scopes

Scopes follow the pattern `context/resource.permission` in SMART v1, tightened in v2:

- **Context**: `patient/` (access limited to one patient's compartment), `user/` (whatever the signed-in user may access), or `system/` (no user; backend services).
- **Permissions**: `read` and `write` in v1; v2 splits them into granular letters — `r`ead (including search), `c`reate, `u`pdate, `d`elete, `s`earch — for example `patient/Observation.rs`.
- Examples: `patient/Patient.read` lets a patient-facing app read the launched patient's demographics; `patient/Observation.read` reads their observations; `user/Patient.read` lets a clinician app read patients the clinician can access; `system/Observation.read` is for bulk/server-to-server jobs.
- Special scopes: `launch` requests a launch context in an EHR launch, `launch/patient` asks the server to let the user select a patient in a standalone launch, `openid` and `fhirUser` request the OIDC identity token, and `offline_access` requests a refresh token.

In SMART v2, scopes can also carry query constraints, for example `patient/Observation.rs?category=http://terminology.hl7.org/CodeSystem/observation-category|vital-signs`, restricting an app to just vital signs.

## OpenID Connect and fhirUser

With `openid` and `fhirUser` scopes, the token response includes an `id_token`. Its `fhirUser` claim is a URL reference to the logged-in user's FHIR identity — for example `Practitioner/234` or `Patient/123` — so the app knows *who* is using it in FHIR terms, not just as an opaque login id.

## Discovery

A SMART-enabled server publishes its OAuth endpoints and capabilities in a discovery document at `{fhir-base}/.well-known/smart-configuration`, listing the authorization and token endpoints, supported scopes, and features such as PKCE and context support. Apps should discover endpoints from this document rather than hard-coding them.
