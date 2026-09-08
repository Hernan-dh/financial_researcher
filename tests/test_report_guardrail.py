import unittest

from crewai.tasks.task_output import TaskOutput

from financial_researcher.crew import validate_financial_report


class ReportGuardrailTests(unittest.TestCase):
    def output(self, raw):
        return TaskOutput(description="report", expected_output="markdown", raw=raw, agent="analyst")

    def test_rejects_broken_markdown_table(self):
        valid, message = validate_financial_report(self.output("| |\n| --- |\n| |"))
        self.assertFalse(valid)
        self.assertIn("too little readable content", message)

    def test_accepts_substantial_sourced_report(self):
        report = (
            "# Executive summary\n\n" + "Evidence and analysis. " * 45
            + "\n\n## Performance\n\nhttps://example.com/filing\n"
            + "\n## Outlook\n\nhttps://example.com/release\n"
        )
        valid, value = validate_financial_report(self.output(report))
        self.assertTrue(valid)
        self.assertEqual(value, report.strip())


if __name__ == "__main__":
    unittest.main()
