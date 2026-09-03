"""Gradio web interface for the CrewAI financial researcher."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import gradio as gr
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
    },
    "Español": {
        "subtitle": "INTELIGENCIA DE MERCADO MULTIAGENTE",
        "greeting": "Ingresá el nombre de una empresa y prepararé un informe financiero actualizado.",
        "placeholder": "Ingresá el nombre de una empresa…",
        "submit": "Investigar",
        "instruction": "Escribí la investigación y el informe final completos en español.",
        "error": "No pude completar esta investigación financiera. Intentá nuevamente.",
    },
}


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


def research_company(message: str, _history, language: str) -> str:
    language = language if language in UI_TEXT else "English"
    text = UI_TEXT[language]
    company = (message or "").strip()
    if not company:
        return text["greeting"]

    try:
        result = FinancialResearcher(llm=fallback_llm()).crew().kickoff(
            inputs={
                "company": company,
                "current_date": date.today().isoformat(),
                "language_instruction": text["instruction"],
            }
        )
    except Exception as error:
        print(f"[web] financial research failed ({type(error).__name__})", flush=True)
        return text["error"]

    return result.raw


def research_english(message: str, history) -> str:
    return research_company(message, history, "English")


def research_spanish(message: str, history) -> str:
    return research_company(message, history, "Español")


initial = UI_TEXT["English"]
with gr.Blocks() as demo:
    with gr.Row(elem_id="title-row"):
        with gr.Column(scale=1, min_width=0, elem_id="header-copy"):
            header = gr.HTML(header_html("English"), elem_id="financial-header")
        with gr.Column(scale=0, min_width=180, elem_id="language-control"):
            gr.Markdown("Idioma / Language:", elem_id="language-label")
            language = gr.Dropdown(
                choices=["Español", "English"],
                value="English",
                show_label=False,
                container=False,
                interactive=True,
                elem_id="language-selector",
            )

    with gr.Group(visible=True) as english_chat:
        english_textbox = gr.Textbox(
            placeholder=initial["placeholder"],
            submit_btn=initial["submit"],
            show_label=False,
            render=False,
        )
        gr.ChatInterface(
            research_english,
            chatbot=gr.Chatbot(
                value=[{"role": "assistant", "content": initial["greeting"]}],
                show_label=False,
                height=520,
                elem_id="financial-chat-en",
            ),
            textbox=english_textbox,
            flagging_mode="never",
        )

    with gr.Group(visible=False) as spanish_chat:
        spanish = UI_TEXT["Español"]
        spanish_textbox = gr.Textbox(
            placeholder=spanish["placeholder"],
            submit_btn=spanish["submit"],
            show_label=False,
            render=False,
        )
        gr.ChatInterface(
            research_spanish,
            chatbot=gr.Chatbot(
                value=[{"role": "assistant", "content": spanish["greeting"]}],
                show_label=False,
                height=520,
                elem_id="financial-chat-es",
            ),
            textbox=spanish_textbox,
            flagging_mode="never",
        )

    language.change(
        localized_ui,
        inputs=language,
        outputs=[header, english_chat, spanish_chat],
        js="(language) => { document.title = language === 'Español' ? 'Investigación financiera' : 'Financial Research'; return language; }",
    )
    browser_language = gr.Textbox(visible=False)
    demo.load(
        initialize_language,
        inputs=browser_language,
        outputs=[language, header, english_chat, spanish_chat],
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
