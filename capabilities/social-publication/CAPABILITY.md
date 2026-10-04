# Social Publication

Status: **PROGRAM_DESIGN_PROTOTYPE_PROVEN**

`social-publication` is the provider-neutral owner for turning an already-authored social post into an approval-bound publication attempt and a durable provider-neutral receipt.

This capability intentionally does **not** own content strategy or generation. A consumer supplies the post body. The capability owns the publication lifecycle.

## Smallest v1 operation

v1 is deliberately text-only:

```text
publication intent
  -> validate
  -> preview + canonical content SHA-256
  -> explicit approval bound to that SHA-256
  -> provider adapter request
  -> provider transport
  -> provider adapter response translation
  -> provider-neutral publication/failure receipt
```

If the content changes after approval, the attempt fails closed before provider request construction or network mutation.

## Core versus adapter

Core:

- validates the provider-neutral intent;
- computes the canonical publishable-content hash;
- binds approval to exact publishable semantics;
- owns provider-neutral lifecycle states and receipts;
- distinguishes provider-request state as `NOT_EMITTED`, `EMITTED`, or `UNKNOWN`;
- refuses missing or stale approval.

LinkedIn adapter:

- owns Person URN input;
- owns LinkedIn Posts API request shape;
- owns required LinkedIn/Rest.li version headers;
- owns raw LinkedIn response translation into provider-neutral outcomes;
- will own OAuth token injection at send time in the build sprint.

The P95 prototype never persists OAuth credentials or an Authorization header.

## P95 prototype

Run success:

```powershell
python capabilities/social-publication/prototype.py --intent capabilities/social-publication/fixtures/text-intent.synthetic.v1.json --mode success
```

Run stale-approval failure:

```powershell
python capabilities/social-publication/prototype.py --intent capabilities/social-publication/fixtures/text-intent.synthetic.v1.json --mode stale-approval
```

Run provider-authorization failure:

```powershell
python capabilities/social-publication/prototype.py --intent capabilities/social-publication/fixtures/text-intent.synthetic.v1.json --mode provider-auth-failure
```

## LinkedIn launch boundary

The current official LinkedIn path for member publication is:

1. register/configure a LinkedIn application;
2. enable **Share on LinkedIn**;
3. obtain member authorization for `w_member_social`;
4. resolve the authenticated member's Person URN;
5. prepare the exact text intent and preview hash;
6. bind operator approval to that exact hash;
7. inject the OAuth token only at transport time;
8. `POST https://api.linkedin.com/rest/posts`;
9. treat HTTP 201 + `x-restli-id` as provider publication proof;
10. persist only the privacy-safe publication receipt.

Live OAuth, identity lookup, HTTP transport, and production publication are successor build work. They are not claimed by this P95 prototype.

## Proof ceiling

Synthetic executable prototypes prove:

- approval binding;
- stale-content fail-closed behavior;
- current LinkedIn text-post request construction;
- successful provider response translation;
- provider authorization failure translation;
- request-build failure receipts without provider mutation;
- transport failure with `UNKNOWN` emission state;
- strict secret-free receipts.

They do not prove live LinkedIn authorization, network publication, actual member identity, platform acceptance, scheduling, or production use.
