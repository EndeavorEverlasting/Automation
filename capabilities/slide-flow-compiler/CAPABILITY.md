# Slide Flow Compiler — Portable Semantic Graph → Editable Slide Objects

**Contract:** slide-flow-graph/v1 → slide-flow-ir/v1 → google-slides-batch-update-plan/v1  
**Owner:** Automation; pure compiler + optional provider adapter.  
**Proof ceiling:** structural/geometry compilation. Not rendered, clicked, published or live-accepted.

## Why this exists

A status dashboard cannot masquerade as an execution flowchart. Source-backed stages, evidence gates, independent branches and explicit connections must be specified in a semantic graph. The compiler **never infers** arrows between adjacent cards: only declared directed edges become native connector shapes. Style tokens are inputs, not hardcoded organizational brands.

The compiler is general-purpose, not a H&H source of truth. Private design registries, drafts, operational records, credentials and source URLs remain in their respective consumer workspaces. Example tests use synthetic data only. This does **not** replace any customer's own style registry, favorite document, ticket governance or file lifecycle.

## Minimal public interface

Import \`compileFlow(graph, profile)\` and \`auditIR(ir)\` from \`compile.mjs\`. Graph declares \`schema\`, \`id\`, \`eyebrow\`, \`title\`, \`qualifier\`, and 1–2 \`lanes\`. Each lane has an \`id\`, \`title\`, 1–4 steps, and an optional explicit \`edges\` list. A step has \`id\`, \`kind\` (\`source|action|gate|outcome\`), \`proof_state\` (\`neutral|pending|unverified|verified\`), \`title\`, \`summary\`, and optional \`action:{label,url}\` or \`proof_url\`. Edges connect adjacent declared steps with \`kind:sequence|conditional\`. Empty edges mean independent/parallel stages, **not** implied flow.

The profile must contain \`schema:slide-flow-style/v1\`, \`id\`, \`version\` and explicit colors for \`canvas,panel,ink,muted,action,secondary,gate,verified\`. Operator-approved style names and reference images remain owned by the consuming style registry. No fallback/default profile is silently applied.

\`adapters/google-slides.mjs\` exports \`toGoogleSlidesRequests(ir, existingSlideObjectId)\`, which returns a request **plan**, not an authenticated publish operation. The provider normalizes shape size and affine transforms; correct readback geometry uses **size × transform**, not raw width/height alone.

## Iteration gates

1. **Graph/provenance**: distinct entities and source statuses; source-linked actions; declared directional dependencies; \`verified\` requires an explicit HTTPS proof reference and \`outcome\` requires verified proof. No invented percentages or progress metrics.
2. **Geometry/interaction**: explicit 720×405 pt grid, 1–2 lanes, 1–4 steps/lane, readable copy caps, semantic accent roles, deterministic IDs and no arrow/card collisions. Google adapter emits native editable shapes with link-bearing text, never decorative glyph arrows.
3. **Provider/visual**: an authorized consumer must resolve exactly one original slide and read revision/IDs, preserve unrelated existing elements, publish only after preview, re-read shapes/links, get a fresh 1600×900 thumbnail, **visually inspect it**, and click link targets in the intended viewer. Unobserved visual/UI behavior remains UNPROVEN; never imply that a syntactically valid batchUpdate is visual acceptance.

**Non-goals:** authentication, search, source-of-truth reconciliation, arbitrary graph routing, auto-resizing long paragraphs, direct deletion of slide elements, visual similarity classification, or hidden background-image copying. The consuming adapter owns safe in-place replacement of its known object IDs using revision-controlled writes; this core does not mutate provider state.

## Isolated consumer canary

\`\`\`bash
node --test capabilities/slide-flow-compiler/tests/test_compile.mjs
\`\`\`

The test imports only the advertised compiler and adapter, with synthetic domain-agnostic inputs. A consumer can change the style profile without changing the graph compiler. Do not promote structural test success to Google Slides visual acceptance.


### Second-pass provider readback acceptance

After the **consumer** has explicitly authorized a provider write, fetch the original slide through the authenticated Google Slides API and pass its raw resource plus the exact compiled plan to \`auditGoogleSlidesReadback(snapshot, plan)\` from \`adapters/google-slides-readback.mjs\`.

The structural validator compares requested shape IDs, link targets, actual Google \`PageElement\` geometry using \`size × scale\`, canvas bounds, and the 9pt minimum readability floor. A Google Slides response frequently normalizes requested sizes to 3,000,000 EMU and moves the true physical width/height into the affine transform. Reading only \`size.width\` is incorrect.

It always reports \`provenance: CALLER_SUPPLIED_SNAPSHOT_NOT_PROVIDER_AUTHENTICATED\`, \`visual_state: NOT_VISUALLY_INSPECTED\`, and \`interaction_state: NOT_BROWSER_CLICK_TESTED\`. Only a distinct authenticated provider receipt and actual rendered/interactive observation can advance those ceilings. Test the code with:

\`\`\`bash
node --test capabilities/slide-flow-compiler/tests/test_readback.mjs
\`\`\`

**Readability revision:** the adapter now uses at least 9pt font sizes and the compiler caps action-label length at 20 characters instead of squeezing text smaller to fit.
