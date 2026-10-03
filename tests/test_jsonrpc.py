"""
Conformité JSON-RPC 2.0 du Custom RPC (https://www.jsonrpc.org/specification).

Les cas reprennent les exemples de la section 7 de la spécification, envoyés
octet par octet sur la socket, sans passer par le stub client.
"""

import json
import socket
import unittest

from rpc_core import RPCClient, RPCError, RPCServer
from rpc_core import protocol
from rpc_core.transport import receive_message, send_message


def subtract(minuend, subtrahend):
    return minuend - subtrahend


class TestJsonRpcSpecExamples(unittest.TestCase):
    def setUp(self):
        self.server = RPCServer(port=0)
        self.server.register_method("subtract", subtract)
        self.server.register_method("sum", lambda *xs: sum(xs))
        self.server.register_method("update", lambda *xs: None)
        self.server.register_method("get_data", lambda: ["hello", 5])
        self.notified = []
        self.server.register_method("notify_hello", lambda *xs: self.notified.append(xs))
        self.server.start()
        self.sock = socket.create_connection(("127.0.0.1", self.server.port), timeout=2)

    def tearDown(self):
        self.sock.close()
        self.server.stop()

    def rpc(self, raw):
        send_message(self.sock, raw.encode() if isinstance(raw, str) else raw)
        return json.loads(receive_message(self.sock))

    def test_positional_params(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}')
        self.assertEqual(r, {"jsonrpc": "2.0", "result": 19, "id": 1})

    def test_named_params(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}')
        self.assertEqual(r, {"jsonrpc": "2.0", "result": 19, "id": 3})

    def test_notification_gets_no_response(self):
        send_message(self.sock, b'{"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}')
        # Le serveur ne doit RIEN renvoyer : la requête suivante reçoit sa propre réponse.
        r = self.rpc('{"jsonrpc": "2.0", "method": "get_data", "id": "9"}')
        self.assertEqual(r["id"], "9")

    def test_method_not_found(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": "foobar", "id": "1"}')
        self.assertEqual(r["error"]["code"], -32601)
        self.assertEqual(r["id"], "1")

    def test_invalid_json(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]')
        self.assertEqual(r["error"]["code"], -32700)
        self.assertIsNone(r["id"])

    def test_invalid_request_object(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": 1, "params": "bar"}')
        self.assertEqual(r["error"]["code"], -32600)
        self.assertIsNone(r["id"])

    def test_invalid_params(self):
        r = self.rpc('{"jsonrpc": "2.0", "method": "subtract", "params": [1], "id": 7}')
        self.assertEqual(r["error"]["code"], -32602)

    def test_batch_invalid_json(self):
        r = self.rpc('[{"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"}, {"jsonrpc": "2.0", "method"]')
        self.assertEqual(r["error"]["code"], -32700)

    def test_empty_batch(self):
        r = self.rpc("[]")
        self.assertEqual(r["error"]["code"], -32600)

    def test_invalid_batch(self):
        r = self.rpc("[1, 2, 3]")
        self.assertEqual([x["error"]["code"] for x in r], [-32600] * 3)

    def test_mixed_batch(self):
        r = self.rpc("""[
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
            {"foo": "boo"},
            {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
            {"jsonrpc": "2.0", "method": "get_data", "id": "9"}
        ]""")
        by_id = {x["id"]: x for x in r}
        self.assertEqual(len(r), 5)  # la notification n'a pas de réponse
        self.assertEqual(by_id["1"]["result"], 7)
        self.assertEqual(by_id["2"]["result"], 19)
        self.assertEqual(by_id[None]["error"]["code"], -32600)
        self.assertEqual(by_id["5"]["error"]["code"], -32601)
        self.assertEqual(by_id["9"]["result"], ["hello", 5])
        self.assertEqual(self.notified, [(7,)])

    def test_every_response_is_valid_jsonrpc(self):
        for raw in ('{"jsonrpc":"2.0","method":"get_data","id":1}', '{"jsonrpc":"2.0","method":"x","id":2}'):
            protocol.validate_response(self.rpc(raw))


class TestJsonRpcClient(unittest.TestCase):
    def setUp(self):
        self.server = RPCServer(port=0)
        self.server.register_method("subtract", subtract)
        self.seen = []
        self.server.register_method("log", lambda message: self.seen.append(message))
        self.server.start()
        self.client = RPCClient(port=self.server.port, timeout=2)

    def tearDown(self):
        self.server.stop()

    def test_named_and_positional_calls(self):
        self.assertEqual(self.client.subtract(minuend=10, subtrahend=4), 6)
        self.assertEqual(self.client.subtract(10, 4), 6)
        with self.assertRaises(ValueError):
            self.client.call("subtract", 10, subtrahend=4)

    def test_error_carries_name_and_numeric_code(self):
        with self.assertRaises(RPCError) as ctx:
            self.client.missing()
        self.assertEqual(ctx.exception.code, "METHOD_NOT_FOUND")
        self.assertEqual(ctx.exception.jsonrpc_code, -32601)

    def test_batch(self):
        res = self.client.batch([("subtract", [5, 3]), ("missing", None), ("subtract", {"minuend": 1, "subtrahend": 1})])
        self.assertEqual(res[0], 2)
        self.assertIsInstance(res[1], RPCError)
        self.assertEqual(res[2], 0)

    def test_notification(self):
        self.client.notify("log", message="hello")
        import time
        for _ in range(50):
            if self.seen:
                break
            time.sleep(0.02)
        self.assertEqual(self.seen, ["hello"])

    def test_request_on_the_wire(self):
        from rpc_core.serializer import RPCSerializer
        msg = json.loads(RPCSerializer.serialize_request("subtract", {"minuend": 1, "subtrahend": 2}, request_id="a"))
        self.assertEqual(msg, {"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 1, "subtrahend": 2}, "id": "a"})


if __name__ == "__main__":
    unittest.main()
