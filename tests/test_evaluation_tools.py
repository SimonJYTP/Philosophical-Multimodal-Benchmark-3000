from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_script("run_models.py")


class PromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.query = json.loads((ROOT / "data" / "query.json").read_text(encoding="utf-8"))
        cls.prompt_payload, cls.catalog = RUNNER.prompt_catalog()

    def record(self, family: str):
        return next(item for item in self.query if item["task"]["family"] == family)

    def test_hss_prompt_contains_separate_options(self):
        record = self.record("visual_multiple_choice_qa")
        prompt = RUNNER.render_prompt(
            record,
            self.catalog["P0-choice-direct-en-v1"]["template"],
            "en",
            "",
            "",
        )
        self.assertIn("A. Money is the root", prompt)
        self.assertIn("D. It is necessary", prompt)

    def test_vulca_requires_codebook(self):
        record = self.record(RUNNER.VULCA_FAMILY)
        with self.assertRaises(RUNNER.EvaluationError):
            RUNNER.render_prompt(
                record,
                self.catalog["P0-vulca-direct-en-v1"]["template"],
                "en",
                "",
                "",
            )

    def test_choice_parsing_strict_and_lenient(self):
        self.assertEqual(
            RUNNER.parse_response("moral_judge", "P0", "A"),
            ("A", "strict_ok", None),
        )
        prediction, status, _ = RUNNER.parse_response("moral_judge", "P0", "Answer: (B)")
        self.assertEqual((prediction, status), ("B", "lenient_only"))

    def test_evidence_json_parsing(self):
        raw = '{"visible_evidence":["a person"],"uncertainty":"low","answer":"C"}'
        prediction, status, error = RUNNER.parse_response("visual_multiple_choice_qa", "P1", raw)
        self.assertEqual((prediction, status, error), ("C", "strict_ok", None))

        prediction, status, _ = RUNNER.parse_response("visual_multiple_choice_qa", "P1", '{"answer":"C"}')
        self.assertEqual((prediction, status), ("C", "lenient_only"))

    def test_sampling_parameters_can_be_omitted(self):
        self.assertIsNone(RUNNER.optional_float("none"))
        self.assertEqual(RUNNER.optional_float("0.25"), 0.25)


class EndToEndTests(unittest.TestCase):
    def test_mock_runner_and_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "mock-run"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_models.py"),
                    "--provider",
                    "mock",
                    "--model",
                    "mock-v1",
                    "--split",
                    "dev",
                    "--families",
                    "visual_multiple_choice_qa",
                    "--limit",
                    "2",
                    "--output-dir",
                    str(run_dir),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            predictions = [
                json.loads(line)
                for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(predictions), 2)
            self.assertTrue(all(item["parse_status"] == "strict_ok" for item in predictions))
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "analyze_results.py"),
                    str(run_dir / "predictions.jsonl"),
                    "--split",
                    "dev",
                    "--families",
                    "visual_multiple_choice_qa",
                    "--allow-partial",
                    "--bootstrap-samples",
                    "20",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((run_dir / "analysis" / "summary.json").is_file())
            self.assertTrue((run_dir / "analysis" / "metrics_long.csv").is_file())
            self.assertTrue((run_dir / "analysis" / "report.md").is_file())

            comparison_dir = Path(temporary) / "comparison"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "compare_runs.py"),
                    str(run_dir / "predictions.jsonl"),
                    str(run_dir / "predictions.jsonl"),
                    "--split",
                    "dev",
                    "--families",
                    "visual_multiple_choice_qa",
                    "--allow-partial",
                    "--bootstrap-samples",
                    "20",
                    "--output-dir",
                    str(comparison_dir),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            comparison = json.loads((comparison_dir / "comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(comparison["results"][0]["delta"], 0.0)
            self.assertTrue((comparison_dir / "metrics_delta.csv").is_file())
            self.assertTrue((comparison_dir / "comparison.md").is_file())


if __name__ == "__main__":
    unittest.main()
