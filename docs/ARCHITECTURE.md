# Architecture

## Purpose

`financial_researcher` is a CrewAI project whose agents and tasks are configured in YAML and orchestrated from Python.
The runtime is pinned to CrewAI 1.15.18 for reproducible local and deployed execution.

## Components

- `src/financial_researcher/config/agents.yaml`: agent roles, goals, and backstories.
- `src/financial_researcher/config/tasks.yaml`: task descriptions and expected outputs.
- `src/financial_researcher/crew.py`: CrewAI agent, task, and crew construction.
- `src/financial_researcher/model_config.py`: version-controlled, quality-ordered model configuration.
- `src/financial_researcher/model_provider.py`: shared per-call fallback across Gemini, Groq, and OpenRouter.
- `src/financial_researcher/main.py`: command-line entry points and kickoff inputs.
- `app.py`: bilingual Gradio chat that accepts a company and returns the final CrewAI report.
- `styles.py`: shared visual language adapted from the Debate interface.
- `knowledge/`: versioned knowledge supplied to the crew.
- `output/` and `sandbox*/`: generated execution artifacts excluded from Git.
- `scripts/`: shared verification, documentation, hook installation, and safe publishing commands.

## Trust boundaries

- Prompts, model responses, tool results, generated code, and generated reports are untrusted.
- Credentials are loaded from the environment and must not enter Git, prompts, logs, or documentation.
- CrewAI model and tool providers are external services.

## Model resilience

Both agents share one CrewAI-compatible fallback LLM. Each model call tries the best configured free-tier option in order: Gemini 3.8/3.7/3.6 Flash, Groq-hosted GPT-OSS 120B, then OpenRouter-hosted NVIDIA Nemotron 3 Ultra/Super Free. A provider failure retries only that call and preserves completed task output.
Financial model calls allow up to 16,384 output tokens so complete reports are not cut off by provider defaults.

## Web interface

The Gradio interface defaults to English unless the browser language starts with `es`. Each language has an independent chat presentation and three randomly selected company shortcuts immediately above its input, while both execute the same sequential researcher-to-analyst crew. Requests are queued one at a time because the generated report path is shared.

## Related decisions

- [Continuous documentation and safe publishing](decisions/0001-continuous-documentation-and-safe-publishing.md)
