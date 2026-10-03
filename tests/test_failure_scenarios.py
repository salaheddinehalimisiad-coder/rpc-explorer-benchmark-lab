"""
Tests d'integration des scenarios de pannes reseau (Phase 07).

Valide experimentalement les 4 transports face aux defaillances :
1. Custom RPC : Latence, Timeout, Connection Refused, Crash serveur, Message corrompu, Methode inconnue
2. gRPC : Latence, Deadline exceeded (timeout), Crash serveur (UNAVAILABLE), Protobuf invalide
3. REST : Latence, Request timeout, Crash serveur (503 / SERVER_UNAVAILABLE)
4. Isolation stricte des scenarios : retour a la baseline apres reset
"""

import time
import socket
import unittest

from failure_simulator.simulator import FailureSimulator
from failure_simulator.message_corruptor import MessageCorruptor
from rpc_core.server_skeleton import RPCServer
from rpc_core.client_stub import RPCClient, RPCError
from rpc_core.transport import send_message, receive_message, ConnectionClosedError
from business.inventory_service import InventoryService
from grpc_impl.grpc_server import InventoryGRPCServer
from grpc_impl.grpc_client import InventoryGRPCClient
import grpc
from rest.rest_server import RestServer
from rest.rest_client import RestClient, RestClientError
import requests.exceptions


class TestFailureScenariosIntegration(unittest.TestCase):
    """Tests d'integration des pannes sur Custom RPC, gRPC et REST."""

    # -------------------------------------------------------------
    # 1. Scenarios Custom RPC
    # -------------------------------------------------------------

    def test_custom_rpc_latency_injection(self):
        """Verifie que l'injection de latence augmente le temps de reponse Custom RPC."""
        sim = FailureSimulator()
        sim.enable_latency_spike(delay_ms=50.0)

        svc = InventoryService()
        server = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim)
        server.register_method("calculate_factorial", svc.calculate_factorial)
        server.start(threaded=True)

        try:
            client = RPCClient(host="127.0.0.1", port=server.port, timeout=2.0)
            t0 = time.perf_counter()
            res = client.call("calculate_factorial", n=5)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(res, 120)
            # Doit inclure les ~50ms de latence injectee (tolerance +-20ms)
            self.assertGreaterEqual(elapsed_ms, 35.0)
        finally:
            server.stop()

    def test_custom_rpc_timeout(self):
        """Verifie qu'un retard serveur superieur au timeout client leve TimeoutError."""
        sim = FailureSimulator()
        sim.simulate_timeout(failure_delay_seconds=1.0)

        svc = InventoryService()
        server = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim)
        server.register_method("calculate_factorial", svc.calculate_factorial)
        server.start(threaded=True)

        try:
            # Timeout client a 0.2s alors que le serveur attend 1.0s
            client = RPCClient(host="127.0.0.1", port=server.port, timeout=0.2)
            with self.assertRaises((TimeoutError, socket.timeout, ConnectionError)):
                client.call("calculate_factorial", n=5)
        finally:
            server.stop()

    def test_custom_rpc_connection_refused_server_down(self):
        """Verifie que la tentative de connexion a un port inactif echoue."""
        # Port dynamique sans serveur
        dead_client = RPCClient(host="127.0.0.1", port=59981, timeout=0.5)
        with self.assertRaises((ConnectionError, TimeoutError, OSError)):
            dead_client.call("calculate_factorial", n=5)

    def test_custom_rpc_server_crash(self):
        """Verifie que le crash serveur coupe brutalement la connexion pendant l'appel."""
        sim = FailureSimulator()
        sim.simulate_server_crash()

        svc = InventoryService()
        server = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim)
        server.register_method("calculate_factorial", svc.calculate_factorial)
        server.start(threaded=True)

        try:
            client = RPCClient(host="127.0.0.1", port=server.port, timeout=2.0)
            with self.assertRaises((ConnectionError, RPCError, ConnectionClosedError)):
                client.call("calculate_factorial", n=5)
        finally:
            server.stop()

    def test_custom_rpc_invalid_message_deserialization(self):
        """Verifie qu'un message JSON malforme declenche une erreur structuree du serveur."""
        server = RPCServer(host="127.0.0.1", port=0)
        server.start(threaded=True)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", server.port))
            # Envoyer directement un JSON syntaxiquement invalide cadree
            bad_payload = MessageCorruptor.create_invalid_json()
            send_message(sock, bad_payload)

            resp_bytes = receive_message(sock)
            import json
            resp = json.loads(resp_bytes.decode("utf-8"))
            self.assertIn("error", resp)
            # JSON-RPC 2.0 : JSON illisible -> "Parse error" (-32700), id null
            self.assertEqual(resp["error"]["code"], -32700)
            self.assertEqual(resp["error"]["data"]["name"], "PARSE_ERROR")
            self.assertIsNone(resp["id"])
            sock.close()
        finally:
            server.stop()

    def test_custom_rpc_unknown_method_error(self):
        """Verifie qu'un appel a une methode inexistante renvoie METHOD_NOT_FOUND."""
        svc = InventoryService()
        server = RPCServer(host="127.0.0.1", port=0)
        server.register_method("calculate_factorial", svc.calculate_factorial)
        server.start(threaded=True)

        try:
            client = RPCClient(host="127.0.0.1", port=server.port, timeout=1.0)
            with self.assertRaises(RPCError) as ctx:
                client.call("__non_existent_method__")
            self.assertIn("METHOD_NOT_FOUND", str(ctx.exception))
        finally:
            server.stop()

    # -------------------------------------------------------------
    # 2. Scenarios gRPC
    # -------------------------------------------------------------

    def test_grpc_latency_injection(self):
        """Verifie que l'injection de latence augmente le temps d'appel gRPC."""
        sim = FailureSimulator()
        sim.enable_latency_spike(delay_ms=40.0)

        server = InventoryGRPCServer(port=0, failure_simulator=sim)
        actual_port = server.start()

        try:
            client = InventoryGRPCClient(port=actual_port, timeout=2.0)
            t0 = time.perf_counter()
            resp = client.calculate_factorial(5)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(resp, 120)
            self.assertGreaterEqual(elapsed_ms, 25.0)
            client.close()
        finally:
            server.stop(grace=0.1)

    def test_grpc_timeout_deadline_exceeded(self):
        """Verifie qu'un delai serveur superieur au timeout gRPC leve DEADLINE_EXCEEDED."""
        sim = FailureSimulator()
        sim.simulate_timeout(failure_delay_seconds=1.0)

        server = InventoryGRPCServer(port=0, failure_simulator=sim)
        actual_port = server.start()

        try:
            client = InventoryGRPCClient(port=actual_port, timeout=0.2)
            with self.assertRaises(grpc.RpcError) as ctx:
                client.calculate_factorial(5)
            self.assertEqual(ctx.exception.code(), grpc.StatusCode.DEADLINE_EXCEEDED)
            client.close()
        finally:
            server.stop(grace=0.1)

    def test_grpc_server_crash(self):
        """Verifie que le crash serveur gRPC retourne StatusCode.UNAVAILABLE."""
        sim = FailureSimulator()
        sim.simulate_server_crash()

        server = InventoryGRPCServer(port=0, failure_simulator=sim)
        actual_port = server.start()

        try:
            client = InventoryGRPCClient(port=actual_port, timeout=2.0)
            with self.assertRaises(grpc.RpcError) as ctx:
                client.calculate_factorial(5)
            self.assertEqual(ctx.exception.code(), grpc.StatusCode.UNAVAILABLE)
            client.close()
        finally:
            server.stop(grace=0.1)

    # -------------------------------------------------------------
    # 3. Scenarios REST
    # -------------------------------------------------------------

    def test_rest_latency_injection(self):
        """Verifie que l'injection de latence augmente le temps d'appel REST."""
        sim = FailureSimulator()
        sim.enable_latency_spike(delay_ms=40.0)

        server = RestServer(port=0, failure_simulator=sim)
        actual_port = server.start(threaded=True)

        try:
            client = RestClient(base_url=f"http://127.0.0.1:{actual_port}", timeout=2.0)
            t0 = time.perf_counter()
            data = client.calculate_factorial(5)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(data, 120)
            self.assertGreaterEqual(elapsed_ms, 25.0)
            client.close()
        finally:
            server.stop()

    def test_rest_timeout(self):
        """Verifie qu'un delai serveur superieur au timeout REST leve une exception timeout."""
        sim = FailureSimulator()
        sim.simulate_timeout(failure_delay_seconds=1.0)

        server = RestServer(port=0, failure_simulator=sim)
        actual_port = server.start(threaded=True)

        try:
            client = RestClient(base_url=f"http://127.0.0.1:{actual_port}", timeout=0.2)
            with self.assertRaises((RestClientError, requests.exceptions.Timeout)):
                client.calculate_factorial(5)
            client.close()
        finally:
            server.stop()

    def test_rest_server_crash(self):
        """Verifie que le crash serveur REST renvoie 503 Service Unavailable."""
        sim = FailureSimulator()
        sim.simulate_server_crash()

        server = RestServer(port=0, failure_simulator=sim)
        actual_port = server.start(threaded=True)

        try:
            client = RestClient(base_url=f"http://127.0.0.1:{actual_port}", timeout=2.0)
            with self.assertRaises(RestClientError) as ctx:
                client.calculate_factorial(5)
            self.assertEqual(ctx.exception.status_code, 503)
            client.close()
        finally:
            server.stop()

    # -------------------------------------------------------------
    # 4. Isolation des Scenarios
    # -------------------------------------------------------------

    def test_scenario_isolation_and_reset(self):
        """Verifie qu'apres reinitialisation du simulateur, les performances reviennent au nominal."""
        sim = FailureSimulator()
        server = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim)
        svc = InventoryService()
        server.register_method("calculate_factorial", svc.calculate_factorial)
        server.start(threaded=True)

        try:
            client = RPCClient(host="127.0.0.1", port=server.port, timeout=2.0)

            # 1. Baseline nominale
            t0 = time.perf_counter()
            res1 = client.call("calculate_factorial", n=5)
            baseline_ms = (time.perf_counter() - t0) * 1000.0
            self.assertEqual(res1, 120)

            # 2. Injection latence 50ms
            sim.enable_latency_spike(50.0)
            t0 = time.perf_counter()
            res2 = client.call("calculate_factorial", n=5)
            with_fault_ms = (time.perf_counter() - t0) * 1000.0
            self.assertEqual(res2, 120)
            self.assertGreater(with_fault_ms, baseline_ms)

            # 3. Reset et retour a la baseline
            sim.reset()
            self.assertFalse(sim.is_active)
            t0 = time.perf_counter()
            res3 = client.call("calculate_factorial", n=5)
            restored_ms = (time.perf_counter() - t0) * 1000.0
            self.assertEqual(res3, 120)
            self.assertLess(restored_ms, 30.0)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
