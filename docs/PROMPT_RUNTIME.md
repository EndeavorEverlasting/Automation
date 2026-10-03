# Repository Prompt Runtime

Automation can resolve operator P-number shorthand from canonical repository-owned prompt registries. This prevents prompt execution from depending on ChatGPT memory, conversation history, or a human re-pasting the prompt body.

## Operator semantics

Examples:

```text
P92
invoke P92
invoke & implement P92
what is P92?
rewrite P92
```

The repository follows the canonical invocation semantics imported from the Prompt Kit control plane:

- bare `P92` or `invoke P92` -> `EXECUTE`
- `invoke & implement P92` -> `EXECUTE_AND_IMPLEMENT`
- explanatory questions -> `REFERENCE`
- explicit rewrite/edit/strengthen verbs -> prompt mutation intent
- unknown IDs fail closed; fuzzy substitution is forbidden

## Resolver

```powershell
python scripts/prompt_runtime.py --text "invoke & implement P92"
```

The JSON packet includes:

- normalized prompt ID;
- invocation intent;
- canonical source repository/ref/path;
- source blob SHA;
- SHA-256 of the exact prompt body;
- exact `copyContent`;
- whether execution and implementation are required.

The resolver uses GitHub's Contents API and supports `GITHUB_TOKEN` or `GH_TOKEN` for authenticated source access.

## Source mobility

The current portable prompt authority is configured in `config/prompt-sources.v1.json`. Repository names are configuration, not code constants.

If the prompt product repository is renamed or transferred, update the config or set:

```text
AUTOMATION_PROMPT_PORTABLE_REPOSITORY
AUTOMATION_PROMPT_PORTABLE_REF
```

Retained prompt authorities have equivalent configuration/override fields.

This means a repository rename does not require rewriting the resolver.

## Agent execution contract

`AGENTS.md` binds repo-capable agents to this rule:

1. resolve the exact P-number from repository-owned source;
2. inspect the invocation packet and exact body;
3. execute it against current repository/provider/runtime truth;
4. if intent is `EXECUTE_AND_IMPLEMENT`, perform reachable authorized mutations and validation;
5. report proof states separately.

Resolution is not execution proof. Printing a prompt body does not satisfy an invocation.

## Failure semantics

If canonical source lookup fails, the resolver returns `PROVIDER_LOOKUP_REQUIRED`.

If an ID is unknown, it returns `UNRESOLVED`.

If the same identity appears in incompatible canonical owners, it returns `SOURCE_CONFLICT`.

None of those states permits a remembered or semantically similar prompt to be substituted.
