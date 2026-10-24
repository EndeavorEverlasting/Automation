# Upstream reference discovery — reusable Automation mechanism

**Ownership:** Automation owns this offline lookup/validation primitive. TokenCorridor maintains the canonical research-source projections and Prompt Kit policy; each repository maintains a small consumer registry and its own product/design choices. Source spreadsheets remain in Google Drive, not in this generic capability.

```bash
python capabilities/upstream-reference-discovery/lookup.py --registry path/to/harness/upstream-intelligence/consumer.v1.json --query "visual"
python capabilities/upstream-reference-discovery/lookup.py --registry path/to/consumer.v1.json --validate
```

The registry needs `schema_version=upstream-intelligence-consumer/v1`, and each resource: `id`, `kind`, `locator`, `installed_locally=false`, and `source_provenance`. `https://` links are references only; `skills://plugins/` URIs apply to connected ChatGPT Work and **are not** installed Codex/Cursor/OpenCode skills. The CLI never fetches, executes, installs or copies donor content. A consumer can read its registry directly even when Automation is not cloned.

[NYC H+H consumer precedent](https://github.com/EndeavorEverlasting/nyc-hh-fieldops-lab) has `harness/professional-document-design/automation-consumer-profile.v1.json`: upstream Automation owns reusable document-formatting while H+H owns profile tokens, acceptance and provider state. This capability deliberately follows the same ownership partition, not the document renderer itself.

Use a repository-local `.agents/skills/upstream-intelligence/SKILL.md` to make discovery visible in Codex, Cursor and OpenCode. This skill is instruction-only and works even without Automation's Python CLI. For a real skill install, qualify license/trust/version and obtain separate authorization. Do not claim provider access from an inventory snapshot.
