"""Tests de l'inspecteur Protobuf/gRPC et du lanceur de laboratoire."""

import io
import unittest
from contextlib import redirect_stdout

from lab.servers import LabServers
from protos import inventory_pb2
from under_the_hood.protobuf_inspector import GRPCInspectorInterceptor, decode_wire, explain_message


class TestDecodeWire(unittest.TestCase):
    def test_factorial_request_is_two_bytes(self):
        data = inventory_pb2.FactorialRequest(n=5).SerializeToString()
        self.assertEqual(data, b"\x08\x05")
        fields = decode_wire(data)
        self.assertEqual(fields[0]["field_number"], 1)
        self.assertEqual(fields[0]["value"], 5)

    def test_negative_int32_takes_ten_bytes(self):
        data = inventory_pb2.UpdateStockRequest(item_id="A", quantity_delta=-1).SerializeToString()
        f = decode_wire(data)[1]
        self.assertEqual(f["value"], -1)
        self.assertEqual(len(f["bytes"].split()), 11)  # 1 octet de tag + 10 octets varint

    def test_double_and_string(self):
        msg = inventory_pb2.ProductResponse(item_id="X", unit_price=1.5, success=True)
        values = {f["field_number"]: f["value"] for f in decode_wire(msg.SerializeToString())}
        self.assertEqual(values[1], "X")
        self.assertEqual(values[4], 1.5)
        self.assertEqual(values[6], 1)

    def test_explain_message_names_fields(self):
        text = explain_message(inventory_pb2.FactorialRequest(n=7))
        self.assertIn("champ n°1", text)
        self.assertIn("(n ", text)


class TestLabAndInterceptor(unittest.TestCase):
    def test_shared_service_across_protocols(self):
        with LabServers() as lab:
            before = lab.rest_client().get_product_details("PROD-003")["stock"]
            lab.custom_client().update_stock(item_id="PROD-003", quantity_delta=-5)
            lab.grpc_client().update_stock("PROD-003", -5)
            after = lab.rest_client().get_product_details("PROD-003")["stock"]
            self.assertEqual(after, before - 10)

    def test_interceptor_captures_call(self):
        inspector = GRPCInspectorInterceptor()
        with LabServers(protocols=["grpc"]) as lab:
            client = lab.grpc_client(interceptors=[inspector])
            self.assertEqual(client.calculate_factorial(6), 720)
            client.close()
        self.assertEqual(len(inspector.calls), 1)
        rec = inspector.calls[0]
        self.assertEqual(rec["method"], "/inventory.InventoryRPCService/CalculateFactorial")
        self.assertEqual(rec["request_bytes"], b"\x08\x06")
        self.assertEqual(rec["status"], "OK")

    def test_under_the_hood_demo_runs(self):
        from under_the_hood.explorer import run_under_the_hood_demo
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_under_the_hood_demo("calculate_factorial")
        out = buf.getvalue()
        self.assertIn("DISPATCH (table blanche)", out)
        self.assertIn("08 05", out)
        self.assertIn("POST /api/factorial HTTP/1.1", out)


if __name__ == "__main__":
    unittest.main()
