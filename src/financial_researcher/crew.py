import re

from crewai import Agent, Crew, Process, Task
from crewai.tasks.task_output import TaskOutput
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

def validate_financial_report(output: TaskOutput) -> tuple[bool, str]:
    """Reject empty or structurally broken reports before they reach the UI."""
    report = (output.raw or "").strip()
    readable = re.sub(r"[^\w]+", "", report, flags=re.UNICODE)
    headings = re.findall(r"(?m)^#{1,6}\s+\S", report)
    sources = re.findall(r"https?://[^\s)>]+", report)

    problems = []
    if len(readable) < 800:
        problems.append("the report has too little readable content")
    if len(headings) < 3:
        problems.append("it needs at least three Markdown section headings")
    if len(sources) < 2:
        problems.append("it needs at least two explicit source URLs")
    if problems:
        return False, "The draft is incomplete: " + "; ".join(problems) + ". Rewrite the complete report."
    return True, report


@CrewBase
class FinancialResearcher():
    """FinancialResearcher crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    def __init__(self, llm, task_callback=None):
        self.llm = llm
        self.task_callback = task_callback

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'],
            llm=self.llm,
            verbose=True,
            tools=[SerperDevTool()]
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst'],
            llm=self.llm,
            verbose=True
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task']
        )

    @task
    def analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['analysis_task'],
            output_file='output/report.md',
            markdown=True,
            guardrail=validate_financial_report,
            guardrail_max_retries=2,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the FinancialResearcher crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            tracing=False,
            task_callback=self.task_callback,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
