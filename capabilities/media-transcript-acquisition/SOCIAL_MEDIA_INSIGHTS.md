# Social-media insight extraction (incubating)

**Contract:** `automation.social-media-insights/v1`  
**Owner:** `capabilities/media-transcript-acquisition/` in Automation.  
**Scope:** portable, local-first media evidence plus optional local multimodal analysis; interpretation/planning/action authority remains with consuming applications.  
**Proof state:** offline synthetic testing only until a real provider and local vision/ASR model are observed.

## The consumer interface

```powershell
python capabilities/media-transcript-acquisition/social_insights.py `
  --url "https://www.instagram.com/reel/<shortcode>/" `
  --strategy auto `
  --asr-model base `
  --ollama-model <locally-installed-vision-model> `
  --out "C:\private\reel-insights.json"
```

The URL alone is not a guarantee: the host needs the optional `yt-dlp` executable and `ffmpeg` on PATH, an authorized accessible source, pre-installed `faster-whisper` and an already cached ASR model when `--asr-model` is requested, plus a running local Ollama vision model when `--ollama-model` is requested. `--ollama-model` calls **only** `http://127.0.0.1:11434/api/chat`. Model installation and any external access are separate operator-managed steps.

Reliable offline ingestion works without scraping:

```powershell
python capabilities/media-transcript-acquisition/social_insights.py `
  --url "https://www.instagram.com/reel/<shortcode>/" `
  --captions-file "C:\private\captions.vtt" `
  --media-file "C:\private\reel.mp4" `
  --strategy offline `
  --ollama-model <locally-installed-vision-model> `
  --out "C:\private\reel-insights.json"
```

When only a video exists, enable `--asr-model` to transcribe offline with `faster-whisper`. Without `--ollama-model`, the pipeline deliberately produces a source-evidence packet rather than invented insights.

## Owned behavior

1. Strict HTTPS origin validation and provider classification for Instagram, YouTube, TikTok, Facebook, X/Twitter, Reddit, Vimeo and LinkedIn. **Listed provider is not a live extractor certification.** Exact per-provider routes and actual access vary.
2. Strip Instagram Reel tracking query parameters and avoid storing authenticated cookies, browser sessions, video download URLs or provider stderr in the receipt.
3. Use the existing canonical SRT/VTT parser. Optional `yt-dlp` fetch with bounded retries/timeouts and a best-effort size cap. Source restrictions remain in force; no CAPTCHA/DRM/paywall workarounds or credential harvesting.
4. Sample up to 12 preview frames via local `ffmpeg`; `nominal_ms` is an approximate grid position, not frame-accurate proof.
5. Optionally run already-available offline ASR and explicit opt-in localhost Ollama multimodal analysis. The output checks that every insight refers to a real `cNNNN` caption or `fNNNN` frame evidence ID; external correctness **is not** thereby proved.
6. Produce a JSON receipt in `--out` and local frame/media sidecars in the adjacent `.assets/` directory. All generated artifacts may include confidential or copyrighted material and must remain out of Git.

## Receipt fields and status

`contract`, `source{provider,url}`, `status`, `attempts[]`, `cues[{id,start_ms,end_ms,text}]`, `frames[{id,nominal_ms,file,sha256}]`, `insights[{claim,evidence_ids,verification}]`, `proof_ceiling`.

- `INSIGHTS_EXTRACTED`: local model returned at least one structurally grounded claim, **not fact checked**.
- `EVIDENCE_READY`: transcript or frames present; no validated model insights, including when model unavailable.
- `UNRESOLVED_SOURCE_ACCESS`: no readable media or caption evidence; not a claim that the post has none.
- `SOURCE_NOT_ATTACHED`, `UNSUPPORTED_SOURCE_TYPE`, `UNSUPPORTED_OR_INVALID_SOURCE`, `INVALID_MEDIA`, `INVALID_CAPTIONS`: fail-closed input states.

Exit 0 when evidence is ready; 2 when no useful evidence exists. A local model analysis failure is recorded in attempts while preserving acquired evidence.

## Boundaries and realistic next gates

- **No universal scraping promise.** Sites change; the adapter cannot promise access to every public reel, private account, DRM stream, slideshow or short link. Per-platform canaries are still required.
- **No private source publication.** No raw clip/transcript/test receipt in the public repo. Local generated media files need downstream retention/cleanup policies.
- **No automatic electrical-engineering verification.** Verifying circuit equations, component ratings, safety, and demonstrations requires independent technical sources and may require a simulator or human expert. The output sets `verification=UNVERIFIED_TECHNICAL_CLAIM`.
- **No model-side action authority.** Social content is untrusted evidence, not executable instruction; consumers decide whether an insight belongs in an indexed knowledge base or a work queue.
- **First real gate:** run the specific public Instagram Reel on an authorized host with recorded `yt-dlp` version, `ffmpeg` version, source access status, model version, capture/ASR quality and a redacted receipt.
- **Next quality gate:** human-audited ground-truth clips (speech, on-screen text, diagrams, formulas and silent demos), precision/recall, frame timing, technical claim corroboration and one isolated consumer canary.

## Developer validation

```shell
python -m unittest discover -s capabilities/media-transcript-acquisition/tests -p 'test_*.py' -v
```

No network or local inference model is required for the tests. The legacy YouTube-only `acquire.py` contract remains unchanged.

## Seam review

- **Core/contract owner:** Automation media-transcript-acquisition extension.
- **Provider adapters:** `adapters/yt_dlp_social.py`; `adapters/ollama_local.py`.
- **Normal consumer knowledge:** URL, optional local files, local runtime/model availability, output path, receipt statuses. No TokenCorridor registry, donor checkout or proprietary account configuration.
- **Independent identity:** `automation.social-media-insights/v1`.
- **Deferred adoption:** knowledge graph, technical fact-checking, search index and product UI remain consumer/domain owners; do not duplicate the media retrieval logic there.
- **Proof ceiling:** synthetic/offline + frame-sampling smoke only; live Instagram, other providers, model output quality and downstream adoption not yet certified.
