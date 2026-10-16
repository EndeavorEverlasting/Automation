# VSC-1 isolated browser capture

This is the optional, read-only Playwright adapter to Automation's visual-state-compare capability. Contract: automation.browser-visual-capture/v1. It is NOT a click agent, semantic evaluator, login/session bridge, or automatic data uploader.

Requirements: Python 3.11+, playwright==1.55.0; install browser via python -m playwright install chromium. Core compare.py remains usable without Playwright.

Local synthetic example (create the output directory first):

    python capabilities/visual-state-compare/adapters/playwright-browser/capture.py \
      --source-html /path/to/synthetic.html --privacy SYNTHETIC_PUBLIC \
      --host-alias local-synthetic --screenshot /tmp/visual/frame.png \
      --receipt /tmp/visual/receipt.json

For explicitly authorized web pages, replace --source-html with --url URL, add --allow-origin SCHEME://HOST[:PORT], and set --privacy PRIVATE_LOCAL_ONLY. HTTP is limited to loopback; HTTPS non-loopback must match the explicitly named origin. The browser creates a fresh, unauthenticated context. JavaScript is disabled, external origins blocked, redirects must stay within the approved origin, downloads disabled; browser-runtime policy remains a separate boundary.

The --ax-out flag optionally writes a local accessibility snapshot containing user-visible text. By default no text tree is captured. Screenshot and AX outputs can disclose confidential data: use private untracked output files, never GitHub/public CI for real sessions. The receipt excludes raw URLs, absolute paths, screenshots and visible text. Its hashes can still correlate sensitive materials.

Run the dedicated synthetic acceptance with a Playwright Chromium installation:
    VSC_REQUIRE_BROWSER=1 python -m unittest discover -s capabilities/visual-state-compare/adapters/playwright-browser/tests -v

The public CI fixture is synthetic. Compare two captured screenshots separately with compare.py; changed pixels do not imply task success. Live host, local model, element localization and action authority require independent gates.
