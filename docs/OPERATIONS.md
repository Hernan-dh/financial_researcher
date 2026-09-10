# Operations

## Local setup

1. Install Python 3.10–3.13 and `uv`.
2. Run `uv sync`.
3. Copy `.env.example` to `.env` and configure at least one of `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY`. Configure `SERPER_API_KEY` for live web research.
4. Run `uv run crewai run`.

For the web interface, run `uv run python app.py` and open `http://127.0.0.1:7860`. Override the port with `PORT`; production services must expose that same environment-provided port.

## Follow-up conversation

After a completed report, ordinary chat messages are answered only from that report and do not fetch current market data. Use `/new-report <company>` to begin a new research run.

Generated files in `output/` and `sandbox*/` are local artifacts and are excluded from publication.

Runtime model names and their order are committed in `src/financial_researcher/model_config.py`; credentials remain only in the environment. Logs show each provider attempt without exposing keys. If a provider fails, the current LLM call moves to the next configured model without restarting completed tasks.

## Verification

Run `./scripts/verify.sh`, or on Windows run `uv run python scripts/verify.py`.

Enable the repository-managed pre-commit hook once per clone with `uv run python scripts/install_hooks.py`. GitHub Actions runs the same verifier.

## Documentation

- Rebuild the changelog: `uv run python scripts/document.py changelog`.
- Create an ADR draft: `uv run python scripts/document.py decision "Decision title"`.

## Publishing

Preview a proposal with `uv run python scripts/publish.py --preview`. Interactive publication verifies the repository, proposes an English Conventional Commit title through Gemini with Groq fallback, and requires typing `PUBLISH` before staging, committing, and pushing.

Provide `--title` and `--description` to avoid external metadata generation. Commits and pushes always require explicit user authorization.

## Recovery

- If verification fails, fix every reported item and rerun it.
- If metadata generation fails, inspect the provider attempt names, verify local keys and quotas, or provide commit metadata manually.
- Never recover with a force-push.

Gradio 6 represents Chatbot input content as typed blocks. The submission handler extracts text before calling the research backend. When checking chat changes, round-trip history through Chatbot.postprocess and Chatbot.preprocess; testing only plain string dictionaries misses this conversion.

Final reports are validated twice: the CrewAI analysis task retries drafts that lack readable content, Markdown sections, or source URLs, and the web boundary rejects non-text or decorative-only output. A rejected result is shown as the localized generic error and is not made downloadable.

## Public-source verification

See [README](../README.md) for the reproducible setup. CI installs dependencies before invoking the verifier. Tests disable dotenv loading and provider telemetry and use synthetic inputs or mocked external calls; passing unit tests does not certify live services or production security.

The verifier invokes tests through uv in this repository so imports resolve even when verification is started from global Python. uv must be on PATH; use uv sync --locked for the committed dependency resolution.


## Publication review

Before publishing, run the verifier and review git diff and git status --short,
especially new files. Keep real credentials in local environment files or hosting
secrets, and preserve upstream license notices. Automated secret checks cover
recognizable patterns in current source files; they do not certify the absence of
secrets or scan every historical commit, remote ref, hosting log or fork. Removing
a file from the working tree does not remove it from Git history.

## Downloadable reports

Install the updated dependencies before starting the app. No LibreOffice,
browser renderer or external document-conversion service is required. PDF fonts
are bundled with ReportLab. Generated files are built in a temporary directory,
copied to the download component's Gradio cache, and the staging directory is
removed immediately. Blocks checks the cache hourly and removes files older
than 24 hours. Restarts or ephemeral hosting storage may remove downloads sooner.
No generated report is placed in the repository or added to allowed_paths.

Verification includes tests for Unicode text, long PDFs, DOCX tables, source
URLs, invalid formats, empty reports and clearing stale download state. Test
live downloads after deployment in both interface languages; MD should match
the completed response and PDF/DOCX should open with legible headings and tables.
