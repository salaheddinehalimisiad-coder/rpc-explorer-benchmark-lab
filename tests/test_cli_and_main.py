"""Tests du CLI interactif (entrées simulées) et du point d'entrée main.py."""

import io
import os
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout

import main
from cli.cli_runner import CLIRunner, invoke, parse_kv_args, parse_value
from lab.servers import LabServers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scripted(answers):
    it = iter(answers)

    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return _input


class TestHelpers(unittest.TestCase):
    def test_parse_value(self):
        self.assertEqual(parse_value("5"), 5)
        self.assertEqual(parse_value("-1"), -1)
        self.assertEqual(parse_value("true"), True)
        self.assertEqual(parse_value("PROD-001"), "PROD-001")

    def test_parse_kv_args(self):
        self.assertEqual(parse_kv_args(["n=5", "item_id=PROD-1"]), {"n": 5, "item_id": "PROD-1"})
        with self.assertRaises(ValueError):
            parse_kv_args(["oops"])

    def test_invoke_same_result_on_all_protocols(self):
        with LabServers() as lab:
            for proto in ("custom", "grpc", "rest"):
                self.assertEqual(invoke(lab, proto, "calculate_factorial", {"n": 6}), 720)
            events = invoke(lab, "grpc", "stream_analytics", {"metric_name": "cpu_usage", "num_events": 3})
            self.assertEqual(len(events), 3)


class TestInteractiveMenu(unittest.TestCase):
    def run_menu(self, answers):
        buf = io.StringIO()
        cli = CLIRunner(input_fn=scripted(answers))
        with redirect_stdout(buf):
            cli.run_interactive_menu()
        return cli, buf.getvalue()

    def test_call_custom_with_under_the_hood(self):
        # 2 = activer Sous le capot ; 1 = appel ; protocole 1 (custom) ; méthode 1 ; n=7 ; 0 = quitter
        cli, out = self.run_menu(["2", "1", "1", "1", "7", "0"])
        self.assertIn("Statut    : OK", out)
        self.assertIn("5040", out)
        self.assertIn("DISPATCH (table blanche)", out)
        self.assertEqual(cli.history[0]["status"], "OK")

    def test_injected_crash_is_visible(self):
        # 3 = pannes ; 3 = crash ; 1 = appel ; protocole 2 (grpc) ; méthode 1 ; n=5 ; 0
        cli, out = self.run_menu(["3", "3", "1", "2", "1", "5", "0"])
        self.assertIn("UNAVAILABLE", cli.history[0]["status"])

    def test_invalid_choice_and_eof(self):
        _, out = self.run_menu(["42"])
        self.assertIn("Choix invalide", out)
        self.assertIn("Serveurs arrêtés", out)


class TestMain(unittest.TestCase):
    def test_version(self):
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                main.parse_arguments(["--version"])

    def test_benchmark_mode_small(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main.main(["--benchmark", "--iterations", "20", "--warmup", "2", "--no-save"])
        self.assertEqual(rc, 0)
        self.assertIn("Custom RPC (cnx persistante)", buf.getvalue())

    def test_serve_and_call_in_separate_processes(self):
        """Vrai client/serveur dans deux processus distincts (comme sur deux machines)."""
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen([sys.executable, "main.py", "--serve", "custom", "--port", str(port)],
                                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            out = ""
            for _ in range(50):
                r = subprocess.run([sys.executable, "main.py", "--call", "custom", "calculate_factorial",
                                    "n=5", "--port", str(port)], cwd=ROOT, capture_output=True, text=True)
                out = r.stdout
                if r.returncode == 0:
                    break
                time.sleep(0.2)
            self.assertEqual(out.strip(), "120")
        finally:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
