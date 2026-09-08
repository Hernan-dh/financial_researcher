"""Bilingual Gradio interface for the CrewAI financial researcher."""

from __future__ import annotations

import os
import random
import queue
import re
import threading
from datetime import date
from pathlib import Path

import gradio as gr
from report_export import download_controls, prepare_with_downloads, finish_with_downloads, finish_with_progress_downloads
from dotenv import load_dotenv

from financial_researcher.crew import FinancialResearcher
from financial_researcher.model_provider import fallback_llm
from styles import CSS, JS

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)

UI_TEXT = {
    "English": {
        "subtitle": "MULTI-AGENT MARKET INTELLIGENCE",
        "greeting": "Enter a company name and I’ll prepare a current financial research report.",
        "placeholder": "Enter a company name…",
        "submit": "Research",
        "instruction": "Write the complete research and final report in English.",
        "error": "I couldn't complete this financial research. Please try again.",
        "examples": "Example companies",
        "status": "**Financial Researcher** is using **Serper web search** to collect current company evidence.",
    },
    "Español": {
        "subtitle": "INTELIGENCIA DE MERCADO MULTIAGENTE",
        "greeting": "Ingresá el nombre de una empresa y prepararé un informe financiero actualizado.",
        "placeholder": "Ingresá el nombre de una empresa…",
        "submit": "Investigar",
        "instruction": "Escribí la investigación y el informe final completos en español.",
        "error": "No pude completar esta investigación financiera. Intentá nuevamente.",
        "examples": "Empresas de ejemplo",
        "status": "**Financial Researcher** está usando la **búsqueda web de Serper** para reunir evidencia actual de la empresa.",
    },
}

COMPANIES = (
    "Microsoft", "NVIDIA", "Tesla", "Mercado Libre", "Apple",
    "Amazon", "Alphabet", "Netflix", "Toyota", "Samsung Electronics",
)
SUGGESTED_COMPANIES = random.sample(COMPANIES, k=3)


def normalize_report(markdown: object) -> str:
    """Return displayable Markdown and fail closed on empty/decorative output."""
    if not isinstance(markdown, str):
        raise ValueError("The financial report is not text")
    report = markdown.strip()
    fenced = re.fullmatch(r"```(?:markdown|md)?\s*\n(?P<body>[\s\S]*?)\n```", report, re.IGNORECASE)
    if fenced:
        report = fenced.group("body").strip()
    if len(re.sub(r"[^\w]+", "", report, flags=re.UNICODE)) < 100:
        raise ValueError("The financial report has no readable content")
    return report


def header_html(language: str) -> str:
    text = UI_TEXT.get(language, UI_TEXT["English"])
    return f"""
    <div class="financial-brand">
      <div class="financial-mark" aria-hidden="true">
        <span class="financial-bar financial-bar-1"></span>
        <span class="financial-bar financial-bar-2"></span>
        <span class="financial-bar financial-bar-3"></span>
      </div>
      <div class="financial-headings">
        <h1>FINANCIAL<span class="financial-sep">/</span>RESEARCH</h1>
        <p>{text['subtitle']}</p>
      </div>
    </div>
    """


def localized_ui(language: str):
    return (
        header_html(language),
        gr.Group(visible=language == "English"),
        gr.Group(visible=language == "Español"),
    )


def initialize_language(browser_language: str):
    language = "Español" if (browser_language or "").lower().startswith("es") else "English"
    header, english_group, spanish_group = localized_ui(language)
    return language, header, english_group, spanish_group


def research_company(message: str, _history, language: str, task_callback=None) -> str:
    language = language if language in UI_TEXT else "English"
    text = UI_TEXT[language]
    company = (message or "").strip()
    if not company:
        return text["greeting"]
    try:
        result = FinancialResearcher(llm=fallback_llm(), task_callback=task_callback).crew().kickoff(inputs={
            "company": company,
            "current_date": date.today().isoformat(),
            "language_instruction": text["instruction"],
        })
    except Exception as error:
        print(f"[web] financial research failed ({type(error).__name__})", flush=True)
        return text["error"]
    try:
        return normalize_report(result.raw)
    except ValueError as error:
        print(f"[web] invalid financial report ({error})", flush=True)
        return text["error"]


def submit_company(message: str, history: list[dict], language: str):
    """Render the user turn before the queued research starts."""
    message = (message or "").strip()
    if not message:
        raise gr.Error("Ingresá una empresa." if language == "Español" else "Enter a company.")
    status = UI_TEXT[language if language in UI_TEXT else "English"]["status"]
    return gr.Textbox(value="", interactive=False), [
        *(history or []),
        {"role": "user", "content": message},
        {"role": "assistant", "content": status},
    ], gr.Button(interactive=False)


def finish_submission(history: list[dict], language: str):
    if len(history) < 2 or history[-2]["role"] != "user":
        return gr.Textbox(interactive=True), history, gr.Button(interactive=True)
    content = history[-2]["content"]
    # Gradio 6 normalizes Chatbot input into typed content blocks.
    message = content if isinstance(content, str) else "\n".join(
        block["text"] for block in content if block.get("type") == "text"
    )
    response = research_company(message, history[:-2], language)
    return gr.Textbox(interactive=True), [
        *history[:-1],
        {"role": "assistant", "content": response},
    ], gr.Button(interactive=True)


def finish_submission_progress(history: list[dict], language: str):
    """Stream task-completion updates into the pending Gradio chat response."""
    if len(history) < 2 or history[-2]["role"] != "user":
        yield gr.Textbox(interactive=True), history, gr.Button(interactive=True), True
        return
    content = history[-2]["content"]
    company = content if isinstance(content, str) else "\n".join(block["text"] for block in content if block.get("type") == "text")
    text = UI_TEXT[language]
    updates = queue.Queue()
    stage = (
        "**Financial Analyst** is evaluating the collected evidence and writing the company report."
        if language == "English" else
        "**Financial Analyst** está evaluando la evidencia reunida y redactando el informe de la empresa."
    )
    callback_count = 0
    def on_task_complete(_output):
        nonlocal callback_count
        callback_count += 1
        if callback_count == 1:
            updates.put((stage, False))
    def work():
        try:
            updates.put((research_company(company, history[:-2], language, task_callback=on_task_complete), True))
        except Exception as error:
            print(f"[web] financial research failed ({type(error).__name__})", flush=True)
            updates.put((text["error"], True))
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    while thread.is_alive() or not updates.empty():
        try:
            update, completed = updates.get(timeout=0.1)
        except queue.Empty:
            continue
        yield gr.Textbox(interactive=completed), [*history[:-1], {"role": "assistant", "content": update}], gr.Button(interactive=completed), completed


def submit_english(message: str, history: list[dict]):
    return submit_company(message, history, "English")


def submit_spanish(message: str, history: list[dict]):
    return submit_company(message, history, "Español")


def finish_english(history: list[dict]):
    return finish_submission(history, "English")


def finish_english_progress(history: list[dict]):
    yield from finish_submission_progress(history, "English")


def finish_spanish(history: list[dict]):
    return finish_submission(history, "Español")


def finish_spanish_progress(history: list[dict]):
    yield from finish_submission_progress(history, "Español")


initial = UI_TEXT["English"]
with gr.Blocks(delete_cache=(3600, 86400)) as demo:
    with gr.Row(elem_id="title-row"):
        with gr.Column(scale=1, min_width=0, elem_id="header-copy"):
            header = gr.HTML(header_html("English"), elem_id="financial-header")
        with gr.Column(scale=0, min_width=180, elem_id="language-control"):
            gr.Markdown("Idioma / Language:", elem_id="language-label")
            language = gr.Dropdown(
                choices=["Español", "English"], value="English", show_label=False,
                container=False, interactive=True, elem_id="language-selector",
            )

    with gr.Group(visible=True) as english_chat:
        english_chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": initial["greeting"]}],
            show_label=False, height=520, elem_id="financial-chat-en",
        )
        english_report, english_download = download_controls("English")
        gr.Markdown(initial["examples"], elem_classes="company-examples-label")
        with gr.Row(elem_id="company-examples-en", elem_classes="company-examples"):
            english_buttons = [gr.Button(company) for company in SUGGESTED_COMPANIES]
        with gr.Row(elem_id="company-input-row-en", elem_classes="company-input-row"):
            english_textbox = gr.Textbox(
                placeholder=initial["placeholder"], show_label=False, container=False,
                scale=1, elem_id="company-input-en",
            )
            english_submit = gr.Button(initial["submit"], variant="primary", scale=0)
        for button, company in zip(english_buttons, SUGGESTED_COMPANIES):
            button.click(lambda value=company: value, outputs=english_textbox)
        english_submit.click(
            prepare_with_downloads(submit_english), [english_textbox, english_chatbot],
            [english_textbox, english_chatbot, english_submit, english_report, english_download], queue=False,
        ).success(
            finish_with_progress_downloads(finish_english_progress, UI_TEXT["English"]["error"]), english_chatbot,
            [english_textbox, english_chatbot, english_submit, english_report, english_download], show_progress="hidden",
        )
        english_textbox.submit(
            prepare_with_downloads(submit_english), [english_textbox, english_chatbot],
            [english_textbox, english_chatbot, english_submit, english_report, english_download], queue=False,
        ).success(
            finish_with_progress_downloads(finish_english_progress, UI_TEXT["English"]["error"]), english_chatbot,
            [english_textbox, english_chatbot, english_submit, english_report, english_download], show_progress="hidden",
        )

    with gr.Group(visible=False) as spanish_chat:
        spanish = UI_TEXT["Español"]
        spanish_chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": spanish["greeting"]}],
            show_label=False, height=520, elem_id="financial-chat-es",
        )
        spanish_report, spanish_download = download_controls("Español")
        gr.Markdown(spanish["examples"], elem_classes="company-examples-label")
        with gr.Row(elem_id="company-examples-es", elem_classes="company-examples"):
            spanish_buttons = [gr.Button(company) for company in SUGGESTED_COMPANIES]
        with gr.Row(elem_id="company-input-row-es", elem_classes="company-input-row"):
            spanish_textbox = gr.Textbox(
                placeholder=spanish["placeholder"], show_label=False, container=False,
                scale=1, elem_id="company-input-es",
            )
            spanish_submit = gr.Button(spanish["submit"], variant="primary", scale=0)
        for button, company in zip(spanish_buttons, SUGGESTED_COMPANIES):
            button.click(lambda value=company: value, outputs=spanish_textbox)
        spanish_submit.click(
            prepare_with_downloads(submit_spanish), [spanish_textbox, spanish_chatbot],
            [spanish_textbox, spanish_chatbot, spanish_submit, spanish_report, spanish_download], queue=False,
        ).success(
            finish_with_progress_downloads(finish_spanish_progress, UI_TEXT["Español"]["error"]), spanish_chatbot,
            [spanish_textbox, spanish_chatbot, spanish_submit, spanish_report, spanish_download], show_progress="hidden",
        )
        spanish_textbox.submit(
            prepare_with_downloads(submit_spanish), [spanish_textbox, spanish_chatbot],
            [spanish_textbox, spanish_chatbot, spanish_submit, spanish_report, spanish_download], queue=False,
        ).success(
            finish_with_progress_downloads(finish_spanish_progress, UI_TEXT["Español"]["error"]), spanish_chatbot,
            [spanish_textbox, spanish_chatbot, spanish_submit, spanish_report, spanish_download], show_progress="hidden",
        )

    language.change(
        localized_ui, inputs=language, outputs=[header, english_chat, spanish_chat],
        js="(language) => { document.title = language === 'Español' ? 'Investigación financiera' : 'Financial Research'; return language; }",
    )
    browser_language = gr.Textbox(visible=False)
    demo.load(
        initialize_language, inputs=browser_language, outputs=[language, header, english_chat, spanish_chat],
        js="() => navigator.language || ''",
    )

demo.queue(default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        css=CSS,
        js=JS,
        theme=gr.themes.Base(),
    )
