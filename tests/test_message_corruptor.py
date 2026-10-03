"""
Tests unitaires pour MessageCorruptor (Phase 07).

Verifie :
1. Generation d'octets JSON invalides ou tronques
2. Echec de deserialisation JSON
3. Echec de decodage Protobuf avec des octets corrompus
4. Generation de requetes avec methode inconnue ou schema invalide
5. Mutation d'octets binaires
"""

import json
import unittest
from failure_simulator.message_corruptor import MessageCorruptor
import protos.inventory_pb2 as inventory_pb2
import google.protobuf.message


class TestMessageCorruptor(unittest.TestCase):
    """Suite de tests pour MessageCorruptor."""

    def test_create_invalid_json(self):
        """Verifie que le JSON produit est syntaxiquement invalide."""
        raw = MessageCorruptor.create_invalid_json()
        self.assertIsInstance(raw, bytes)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw.decode("utf-8", errors="replace"))

    def test_create_truncated_json(self):
        """Verifie qu'un JSON tronque leve JSONDecodeError."""
        raw = MessageCorruptor.create_truncated_json()
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw.decode("utf-8"))

    def test_create_invalid_protobuf(self):
        """Verifie que les octets invalides echouent a etre deserialises par Protobuf."""
        bad_bytes = MessageCorruptor.create_invalid_protobuf()
        self.assertIsInstance(bad_bytes, bytes)

        req = inventory_pb2.FactorialRequest()
        with self.assertRaises(google.protobuf.message.DecodeError):
            req.ParseFromString(bad_bytes)

    def test_create_unknown_method_request(self):
        """Verifie la structure de la requete avec methode inconnue."""
        req = MessageCorruptor.create_unknown_method_request(
            req_id="custom_id",
            method_name="test_unknown"
        )
        self.assertEqual(req["id"], "custom_id")
        self.assertEqual(req["method"], "test_unknown")
        self.assertEqual(req["params"], {})
        self.assertEqual(req["jsonrpc"], "2.0")
        self.assertNotIn("args", req)  # format JSON-RPC 2.0 : "params", pas "args"

    def test_create_invalid_schema_request(self):
        """Verifie la structure de la requete au schema invalide."""
        req = MessageCorruptor.create_invalid_schema_request()
        self.assertNotIn("method", req)
        self.assertIn("bad_key", req)

    def test_corrupt_bytes(self):
        """Verifie l'inversion d'octets par corrupt_bytes."""
        original = b"HELLO_RPC"
        corrupted = MessageCorruptor.corrupt_bytes(original, offset=1)
        self.assertNotEqual(original, corrupted)
        self.assertEqual(len(original), len(corrupted))
        self.assertEqual(corrupted[0], original[0])
        self.assertNotEqual(corrupted[1], original[1])

        # Test sur donnees vides
        empty_corrupted = MessageCorruptor.corrupt_bytes(b"")
        self.assertEqual(empty_corrupted, b"\xff")


if __name__ == "__main__":
    unittest.main()
