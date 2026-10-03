"""
Tests du câblage CLI (main.py + cli.CLIRunner).

Vérifie :
1. Le parsing et la validation des arguments de main.py
2. Le routage de chaque mode vers la bonne méthode du CLIRunner
3. Le benchmark réel de bout en bout sur les 4 protocoles (Local, Custom RPC, gRPC, REST)
4. La démonstration de pannes réelle (latence, timeout, crash, isolation)
5. Le menu interactif piloté par des saisies scriptées
"""

import io
import json
import logging
import os
import tempfile
import unittest

import main
from cli.cli_runner import CLIRunner, LabServers, OPERATIONS, PROTOCOLS, parse_protocols


def scripted_input(answers):
    """Retourne une fonction input() qui renvoie les réponses dans l'ordre."""
    iterator = iter(answers)

    def _input(prompt=""):
        try:
            return next(iterator)
        except StopIteration:
            raise EOFError

    return _input


class RecordingRunner:
    """Faux CLIRunner qui enregistre les appels reçus depuis main()."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {}

        return _record


class TestArgumentParsing(unittest.TestCase):

    def test_parse_protocols_default_is_all(self):
        self.assertEqual(parse_protocols(None), list(PROTOCOLS))

    def test_parse_protocols_list(self):
        self.assertEqual(parse_protocols("custom, GRPC,rest"), ["custom", "grpc", "rest"])

    def test_parse_protocols_unknown(self):
        with self.assertRaises(ValueError):
            parse_protocols("custom,soap")

    def test_invalid_protocol_exits(self):
        with self.assertRaises(SystemExit):
            main.parse_arguments(["--benchmark", "--protocols", "soap"])

    def test_invalid_iterations_exits(self):
        with self.assertRaises(SystemExit):
            main.parse_arguments(["--benchmark", "--iterations", "0"])

    def test_negative_latency_exits(self):
        with self.assertRaises(SystemExit):
            main.parse_arguments(["--simulate-latency", "-5"])

    def test_modes_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            main.parse_arguments(["--benchmark", "--simulate-failures"])


class TestMainDispatch(unittest.TestCase):

    def test_benchmark_mode(self):
        runner = RecordingRunner()
        code = main.main(
            ["--benchmark", "--iterations", "10", "--warmup", "2", "--protocols", "custom,grpc",
             "--operation", "get_product_details", "--output", "out.json"],
            runner=runner,
        )
        self.assertEqual(code, 0)
        self.assertEqual(runner.calls, [(
            "run_benchmark_mode", (),
            {"iterations": 10, "warmup_iterations": 2, "protocols": ["custom", "grpc"],
             "operation": "get_product_details", "output_path": "out.json"},
        )])

    def test_benchmark_default_iterations(self):
        runner = RecordingRunner()
        main.main(["--benchmark"], runner=runner)
        self.assertEqual(runner.calls[0][2]["iterations"], 1000)
        self.assertEqual(runner.calls[0][2]["protocols"], list(PROTOCOLS))

    def test_simulate_failures_mode(self):
        runner = RecordingRunner()
        main.main(["--simulate-failures", "--iterations", "5"], runner=runner)
        self.assertEqual(runner.calls, [("run_failure_demo", (), {"iterations": 5, "output_path": None})])

    def test_simulate_latency_mode(self):
        runner = RecordingRunner()
        main.main(["--simulate-latency", "200"], runner=runner)
        self.assertEqual(runner.calls, [("run_latency_demo", (200.0,), {"iterations": 30})])

    def test_simulate_timeout_mode(self):
        runner = RecordingRunner()
        main.main(["--simulate-timeout", "5", "--client-timeout", "0.5"], runner=runner)
        self.assertEqual(runner.calls, [("run_timeout_demo", (5.0,), {"client_timeout": 0.5})])

    def test_interactive_mode(self):
        runner = RecordingRunner()
        main.main(["--interactive"], runner=runner)
        self.assertEqual(runner.calls, [("run_interactive_menu", (), {})])

    def test_no_argument_prints_help_hint(self):
        runner = RecordingRunner()
        self.assertEqual(main.main([], runner=runner), 0)
        self.assertEqual(runner.calls, [])


class TestLabServers(unittest.TestCase):

    def test_all_protocols_answer_every_operation(self):
        with LabServers() as lab:
            self.assertEqual(sorted(lab.adapters), sorted(PROTOCOLS))
            for proto, adapter in lab.adapters.items():
                with self.subTest(protocol=proto):
                    self.assertEqual(CLIRunner.call_operation(adapter, "calculate_factorial", {"n": 6}), 720)
                    prod = CLIRunner.call_operation(adapter, "get_product_details")
                    self.assertEqual(prod["item_id"], "PROD-001")
                    events = CLIRunner.call_operation(adapter, "stream_analytics", {"count": 3})
                    self.assertIsInstance(events, list)
                    self.assertEqual(len(events), 3)

    def test_subset_and_cleanup(self):
        werkzeug = logging.getLogger("werkzeug")
        level_before = werkzeug.level
        lab = LabServers(protocols=["custom", "rest"]).start()
        self.assertEqual(sorted(lab.adapters), ["custom", "rest"])
        lab.stop()
        self.assertEqual(lab.adapters, {})
        self.assertEqual(werkzeug.level, level_before)

    def test_unknown_operation(self):
        with LabServers(protocols=["local"]) as lab:
            with self.assertRaises(ValueError):
                CLIRunner.call_operation(lab.adapters["local"], "drop_database")


class TestBenchmarkMode(unittest.TestCase):

    def test_full_benchmark_report(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bench.json")
            report = CLIRunner(out=out).run_benchmark_mode(
                iterations=5, warmup_iterations=1, output_path=path
            )
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["conditions"]["iterations"], 5)

        latency = report["latency_comparison"]
        self.assertEqual(sorted(latency), ["Custom RPC", "Local", "REST", "gRPC"])
        for name, res in latency.items():
            with self.subTest(protocol=name):
                self.assertEqual(res["iterations"], 5)
                self.assertEqual(res["error_count"], 0)
                self.assertEqual(res["warmup_iterations"], 1)
        self.assertIn("payload_sizes", report)
        self.assertIn("serialization_microbenchmark", report)
        self.assertIn("python", report["conditions"]["environment"])
        text = out.getvalue()
        self.assertIn("Custom RPC", text)
        self.assertIn("p95", text)

    def test_benchmark_other_operation(self):
        report = CLIRunner(out=io.StringIO()).run_benchmark_mode(
            iterations=3, warmup_iterations=0, protocols=["grpc"], operation="get_product_details"
        )
        self.assertEqual(list(report["latency_comparison"]), ["gRPC"])
        self.assertEqual(report["latency_comparison"]["gRPC"]["operation"], "get_product_details")
        self.assertEqual(report["latency_comparison"]["gRPC"]["error_count"], 0)

    def test_benchmark_rejects_bad_input(self):
        runner = CLIRunner(out=io.StringIO())
        with self.assertRaises(ValueError):
            runner.run_benchmark_mode(iterations=0)
        with self.assertRaises(ValueError):
            runner.run_benchmark_mode(iterations=1, operation="unknown")


class TestFailureModes(unittest.TestCase):

    def test_failure_demo_runs_all_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "failures.json")
            results = CLIRunner(out=io.StringIO()).run_failure_demo(
                iterations=2, delays=(0.0,), timeout_delay_seconds=0.3,
                client_timeout=0.05, output_path=path,
            )
            self.assertTrue(os.path.exists(path))

        self.assertIn("delay_0ms", results["latency_experiments"])
        for proto in ("Custom RPC", "gRPC", "REST"):
            with self.subTest(protocol=proto):
                self.assertEqual(results["latency_experiments"]["delay_0ms"][proto]["count"], 2)
                self.assertNotEqual(results["timeout_experiments"][proto]["status"], "UNEXPECTED_SUCCESS")
                self.assertNotEqual(results["crash_experiments"][proto], "UNEXPECTED_SUCCESS")
        self.assertIn("restored_nominal_ms", results["isolation_experiment"])

    def test_latency_demo_adds_delay(self):
        results = CLIRunner(out=io.StringIO()).run_latency_demo(30.0, iterations=3)
        self.assertEqual(sorted(results), ["delay_0ms", "delay_30ms"])
        for proto in ("Custom RPC", "gRPC", "REST"):
            with self.subTest(protocol=proto):
                self.assertGreaterEqual(results["delay_30ms"][proto]["min_ms"], 30.0)

    def test_timeout_demo_reports_timeouts(self):
        results = CLIRunner(out=io.StringIO()).run_timeout_demo(0.3, client_timeout=0.05)
        self.assertIn("TIMEOUT", results["Custom RPC"]["status"])
        self.assertIn("DEADLINE_EXCEEDED", results["gRPC"]["status"])
        self.assertIn("REST_TIMEOUT", results["REST"]["status"])

    def test_invalid_values(self):
        runner = CLIRunner(out=io.StringIO())
        with self.assertRaises(ValueError):
            runner.run_latency_demo(-1)
        with self.assertRaises(ValueError):
            runner.run_timeout_demo(0)


class TestInteractiveMenu(unittest.TestCase):

    def run_menu(self, answers):
        out = io.StringIO()
        CLIRunner(out=out, input_func=scripted_input(answers)).run_interactive_menu()
        return out.getvalue()

    def test_quit(self):
        self.assertIn("Au revoir.", self.run_menu(["0"]))

    def test_end_of_input_quits(self):
        self.assertIn("Au revoir.", self.run_menu([]))

    def test_remote_call_success(self):
        text = self.run_menu(["1", "rest", "calculate_factorial", '{"n": 5}', "0"])
        self.assertIn("[REST] calculate_factorial -> OK", text)
        self.assertIn("120", text)

    def test_remote_call_error_is_displayed(self):
        text = self.run_menu(["1", "custom", "calculate_factorial", '{"n": -1}', "0"])
        self.assertIn("ÉCHEC", text)
        self.assertIn("RPCError", text)

    def test_invalid_entries(self):
        text = self.run_menu([
            "9",
            "1", "soap",
            "1", "custom", "drop_database",
            "1", "custom", "calculate_factorial", "not json",
            "0",
        ])
        self.assertIn("Choix invalide : 9", text)
        self.assertIn("Protocole inconnu : soap", text)
        self.assertIn("Opération inconnue : drop_database", text)
        self.assertIn("Arguments invalides", text)

    def test_benchmark_from_menu(self):
        text = self.run_menu(["2", "3", "0", "0"])
        self.assertIn("BENCHMARK COMPARATIF", text)
        self.assertIn("Itérations    : 3 (warm-up : 0)", text)


if __name__ == "__main__":
    unittest.main()
