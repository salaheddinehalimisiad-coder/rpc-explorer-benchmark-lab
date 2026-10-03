"""
Suite de tests complets pour le Framework RPC Custom (Phase 02)

Teste :
1. Sérialisation / Désérialisation et validation JSON
2. Transport et cadrage TCP (framing par préfixe de 4 octets)
3. Client Stub transparent et invocation dynamique
4. Serveur Skeleton multi-threadé et Dispatcher sécurisé (table blanche)
5. Gestion des erreurs distantes (METHOD_NOT_FOUND, INVALID_ARGS, EXECUTION_ERROR)
6. Gestion des timeouts et de la concurrence
"""

import time
import unittest
import threading
from rpc_core.serializer import RPCSerializer
from rpc_core.client_stub import RPCClient, RPCError
from rpc_core.server_skeleton import RPCServer
from rpc_core.transport import TransportError, ConnectionClosedError


class TestRPCSerializer(unittest.TestCase):
    """Tests unitaires pour RPCSerializer."""

    def test_serialize_deserialize_request(self):
        """Vérifie l'aller-retour de sérialisation d'une requête RPC."""
        req_bytes = RPCSerializer.serialize_request(
            method="calculate_factorial",
            args={"n": 5},
            request_id="req-12345"
        )
        self.assertIsInstance(req_bytes, bytes)

        decoded = RPCSerializer.deserialize_request(req_bytes)
        self.assertEqual(decoded["id"], "req-12345")
        self.assertEqual(decoded["method"], "calculate_factorial")
        self.assertEqual(decoded["jsonrpc"], "2.0")
        self.assertEqual(decoded["params"], {"n": 5})

    def test_auto_generate_request_id(self):
        """Vérifie la génération automatique d'un UUID si request_id n'est pas fourni."""
        req_bytes = RPCSerializer.serialize_request(method="ping", args={})
        decoded = RPCSerializer.deserialize_request(req_bytes)
        self.assertTrue(len(decoded["id"]) > 10)

    def test_serialize_deserialize_response_success(self):
        """Vérifie la sérialisation d'une réponse de succès."""
        resp_bytes = RPCSerializer.serialize_response(
            request_id="req-12345",
            result=120,
            metadata={"status": "OK"}
        )
        decoded = RPCSerializer.deserialize_response(resp_bytes)
        self.assertEqual(decoded["id"], "req-12345")
        self.assertEqual(decoded["result"], 120)
        self.assertNotIn("error", decoded)  # JSON-RPC 2.0 : "result" OU "error"

    def test_serialize_deserialize_response_error(self):
        """Vérifie la sérialisation d'une réponse avec erreur structurée."""
        err_dict = {"code": "METHOD_NOT_FOUND", "message": "Méthode introuvable", "data": {}}
        resp_bytes = RPCSerializer.serialize_response(
            request_id="req-12345",
            result=None,
            error=err_dict
        )
        decoded = RPCSerializer.deserialize_response(resp_bytes)
        self.assertEqual(decoded["id"], "req-12345")
        self.assertNotIn("result", decoded)
        self.assertEqual(decoded["error"]["code"], -32601)  # code JSON-RPC 2.0
        self.assertEqual(decoded["error"]["data"]["name"], "METHOD_NOT_FOUND")

    def test_invalid_request_rejection(self):
        """Vérifie le rejet des requêtes malformées."""
        with self.assertRaises(ValueError):
            RPCSerializer.serialize_request(method="", args={})

        with self.assertRaises(ValueError):
            RPCSerializer.serialize_request(method="test", args="not_a_dict")  # type: ignore

        with self.assertRaises(ValueError):
            RPCSerializer.deserialize_request(b"invalid json")

        with self.assertRaises(ValueError):
            RPCSerializer.deserialize_request(b'{"id": "1"}')  # Manque jsonrpc et method

        with self.assertRaises(ValueError):  # version absente
            RPCSerializer.deserialize_request(b'{"method": "ping", "id": "1"}')


class TestRPCIntegration(unittest.TestCase):
    """Tests d'intégration de bout en bout du mini-framework RPC."""

    @classmethod
    def setUpClass(cls):
        """Démarre un serveur RPC sur un port dynamique (port=0)."""
        cls.server = RPCServer(host="127.0.0.1", port=0)

        # Enregistrement des fonctions dans la table blanche
        def add(a: int, b: int) -> int:
            return a + b

        def echo(message: str) -> str:
            return f"Echo: {message}"

        def slow_method(duration: float) -> str:
            time.sleep(duration)
            return "done"

        def failing_method():
            raise ZeroDivisionError("Division par zéro simulée")

        cls.server.register_method("add", add)
        cls.server.register_method("echo", echo)
        cls.server.register_method("slow_method", slow_method)
        cls.server.register_method("failing_method", failing_method)

        cls.server.start(threaded=True)
        # Port alloué dynamiquement par le système
        cls.port = cls.server.port
        cls.client = RPCClient(host="127.0.0.1", port=cls.port, timeout=3.0)

    @classmethod
    def tearDownClass(cls):
        """Arrête proprement le serveur."""
        cls.server.stop()

    def test_direct_call_success(self):
        """Vérifie l'exécution d'un appel RPC via client.call()."""
        result = self.client.call("add", a=15, b=27)
        self.assertEqual(result, 42)

    def test_dynamic_stub_call(self):
        """Vérifie la transparence totale via le stub dynamique client.method()."""
        result = self.client.echo(message="Hello SOA Distributed Systems")
        self.assertEqual(result, "Echo: Hello SOA Distributed Systems")

    def test_method_not_found_error(self):
        """Vérifie qu'appeler une méthode non enregistrée lève RPCError avec code METHOD_NOT_FOUND."""
        with self.assertRaises(RPCError) as ctx:
            self.client.call("unregistered_method", x=1)
        self.assertEqual(ctx.exception.code, "METHOD_NOT_FOUND")

    def test_invalid_arguments_error(self):
        """Vérifie qu'un argument invalide (ex: manque d'argument requis) lève INVALID_ARGS."""
        with self.assertRaises(RPCError) as ctx:
            self.client.call("add", a=10)  # Manque b
        self.assertEqual(ctx.exception.code, "INVALID_ARGS")

    def test_remote_execution_error(self):
        """Vérifie qu'une exception levée par la fonction distante est encapsulée proprement."""
        with self.assertRaises(RPCError) as ctx:
            self.client.call("failing_method")
        self.assertEqual(ctx.exception.code, "EXECUTION_ERROR")
        self.assertIn("Division par zéro", ctx.exception.message)

    def test_timeout_handling(self):
        """Vérifie qu'un appel qui dépasse le timeout lève TimeoutError côté client."""
        fast_client = RPCClient(host="127.0.0.1", port=self.port, timeout=0.2)
        with self.assertRaises(TimeoutError):
            fast_client.call("slow_method", duration=0.8)

    def test_connection_refused(self):
        """Vérifie que cibler un port fermé lève ConnectionError ou TimeoutError selon l'OS."""
        dead_client = RPCClient(host="127.0.0.1", port=59999, timeout=0.5)
        with self.assertRaises((ConnectionError, TimeoutError)):
            dead_client.call("add", a=1, b=2)

    def test_concurrent_clients(self):
        """Vérifie que le serveur multi-threadé gère correctement plusieurs requêtes concurrentes."""
        results = []
        errors = []

        def worker(idx):
            try:
                cli = RPCClient(host="127.0.0.1", port=self.port, timeout=3.0)
                res = cli.add(a=idx, b=100)
                results.append(res)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Erreurs rencontrées : {errors}")
        self.assertEqual(len(results), 10)
        self.assertEqual(sorted(results), [100 + i for i in range(10)])


if __name__ == "__main__":
    unittest.main()
