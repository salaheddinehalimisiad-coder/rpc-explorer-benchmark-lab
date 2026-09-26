"""
Moteur de Benchmark Comparatif pour RPC Explorer & Benchmark Lab.

Mesure et compare :
1. Latence (min, mean, median, max, p50, p90, p95, p99, std_dev)
2. Débit / Throughput (requêtes par seconde)
3. Taille des payloads réseau (octets bruts sérialisés JSON vs Protobuf vs REST)
4. Coût CPU de sérialisation / désérialisation
5. Concurrence et tenue sous charge (1, 5, 10, 20 workers)
"""

import time
import json
from concurrent import futures
from typing import Dict, List, Any, Optional

from rpc_core.serializer import RPCSerializer
from protos import inventory_pb2
from .adapters.base_adapter import BaseBenchmarkAdapter
from .metrics import BenchmarkResult


class BenchmarkRunner:
    """
    Orchestrateur des campagnes de benchmark comparatives.
    """

    def __init__(
        self,
        adapters: Optional[List[BaseBenchmarkAdapter]] = None,
        failure_simulator: Optional[Any] = None,
    ):
        self.adapters = adapters or []
        self.failure_simulator = failure_simulator

    def run_latency_benchmark(
        self,
        adapter: BaseBenchmarkAdapter,
        operation: str = "calculate_factorial",
        iterations: int = 1000,
        warmup_iterations: int = 50,
        failure_simulator: Optional[Any] = None,
        **kwargs,
    ) -> BenchmarkResult:
        """
        Mesure la latence d'appels répétés pour un adaptateur donné après warm-up.
        """
        active_sim = failure_simulator if failure_simulator is not None else self.failure_simulator
        # 1. Phase de chauffe (Warm-up)
        for _ in range(warmup_iterations):
            try:
                self._dispatch_call(adapter, operation, **kwargs)
            except Exception:
                pass

        # 2. Phase d'échantillonnage
        latencies_ms: List[float] = []
        errors = 0
        start_campaign = time.perf_counter()

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                self._dispatch_call(adapter, operation, **kwargs)
                t1 = time.perf_counter()
                latencies_ms.append((t1 - t0) * 1000.0)
            except Exception:
                errors += 1

        total_time_seconds = time.perf_counter() - start_campaign

        return BenchmarkResult(
            name=adapter.name,
            operation=operation,
            latencies_ms=latencies_ms,
            total_time_seconds=total_time_seconds,
            warmup_iterations=warmup_iterations,
            error_count=errors,
            concurrency=1,
        )

    def _dispatch_call(self, adapter: BaseBenchmarkAdapter, operation: str, **kwargs) -> Any:
        """Achemine l'appel vers la méthode d'adaptateur adéquate."""
        if operation == "calculate_factorial":
            n = kwargs.get("n", 5)
            return adapter.call_calculate_factorial(n)
        elif operation == "get_product_details":
            item_id = kwargs.get("item_id", "PROD-001")
            return adapter.call_get_product_details(item_id)
        elif operation == "update_stock":
            item_id = kwargs.get("item_id", "PROD-002")
            delta = kwargs.get("quantity_delta", 1)
            return adapter.call_update_stock(item_id, delta)
        elif operation == "stream_analytics":
            metric_name = kwargs.get("metric_name", "cpu_usage")
            count = kwargs.get("count", 5)
            return adapter.call_stream_analytics(metric_name, count)
        else:
            raise ValueError(f"Opération '{operation}' non reconnue par le benchmark.")

    def run_payload_size_comparison(self) -> Dict[str, Any]:
        """
        Mesure et compare la taille binaire réelle des requêtes et réponses
        sérialisées : Protobuf (binaire gRPC) vs JSON (Custom RPC) vs JSON (REST).
        """
        # 1. calculate_factorial (n=5)
        # Custom RPC
        custom_req = RPCSerializer.serialize_request("calculate_factorial", args={"n": 5})
        custom_resp = RPCSerializer.serialize_response("benchmark_req_001", result=120)
        # gRPC Protobuf
        grpc_req = inventory_pb2.FactorialRequest(n=5).SerializeToString()
        grpc_resp = inventory_pb2.FactorialResponse(result=120, execution_time_ms=0.05).SerializeToString()
        # REST HTTP Body
        rest_req = json.dumps({"n": 5}).encode("utf-8")
        rest_resp = json.dumps({"n": 5, "result": 120, "execution_time_ms": 0.05}).encode("utf-8")

        factorial_sizes = {
            "Custom RPC": {"request_bytes": len(custom_req), "response_bytes": len(custom_resp), "total_bytes": len(custom_req) + len(custom_resp)},
            "gRPC": {"request_bytes": len(grpc_req), "response_bytes": len(grpc_resp), "total_bytes": len(grpc_req) + len(grpc_resp)},
            "REST": {"request_bytes": len(rest_req), "response_bytes": len(rest_resp), "total_bytes": len(rest_req) + len(rest_resp)},
        }

        # 2. get_product_details ("PROD-001")
        # Custom RPC
        prod_data = {
            "item_id": "PROD-001", "name": "Laptop ProBook 450", "category": "Electronics",
            "price": 1299.99, "stock": 42, "unit": "unit", "last_updated": "2026-09-26T12:00:00Z"
        }
        custom_prod_req = RPCSerializer.serialize_request("get_product_details", args={"item_id": "PROD-001"})
        custom_prod_resp = RPCSerializer.serialize_response("benchmark_req_002", result=prod_data)
        # gRPC Protobuf
        grpc_prod_req = inventory_pb2.ProductRequest(item_id="PROD-001").SerializeToString()
        grpc_prod_resp = inventory_pb2.ProductResponse(
            item_id="PROD-001", name="Laptop ProBook 450", quantity=42, unit_price=1299.99,
            category="Electronics", success=True, message="Produit trouvé."
        ).SerializeToString()
        # REST HTTP Body
        rest_prod_req = b""  # GET n'a pas de body
        rest_prod_resp = json.dumps(prod_data).encode("utf-8")

        product_sizes = {
            "Custom RPC": {"request_bytes": len(custom_prod_req), "response_bytes": len(custom_prod_resp), "total_bytes": len(custom_prod_req) + len(custom_prod_resp)},
            "gRPC": {"request_bytes": len(grpc_prod_req), "response_bytes": len(grpc_prod_resp), "total_bytes": len(grpc_prod_req) + len(grpc_prod_resp)},
            "REST": {"request_bytes": len(rest_prod_req), "response_bytes": len(rest_prod_resp), "total_bytes": len(rest_prod_req) + len(rest_prod_resp)},
        }

        # Calcul des gains de compacité
        factorial_reduction_vs_json = round((1.0 - (factorial_sizes["gRPC"]["total_bytes"] / factorial_sizes["Custom RPC"]["total_bytes"])) * 100.0, 1)
        product_reduction_vs_json = round((1.0 - (product_sizes["gRPC"]["total_bytes"] / product_sizes["Custom RPC"]["total_bytes"])) * 100.0, 1)

        return {
            "calculate_factorial": factorial_sizes,
            "get_product_details": product_sizes,
            "compactness_gain_percent": {
                "factorial_grpc_vs_custom_rpc": factorial_reduction_vs_json,
                "product_grpc_vs_custom_rpc": product_reduction_vs_json,
            },
        }

    def run_serialization_benchmark(self, iterations: int = 1000) -> Dict[str, Any]:
        """
        Micro-benchmark mesurant le coût CPU d'encodage et décodage pur :
        JSON (dumps/loads) vs Protobuf (SerializeToString/ParseFromString).
        """
        prod_dict = {
            "item_id": "PROD-001", "name": "Laptop ProBook 450", "category": "Electronics",
            "price": 1299.99, "stock": 42, "unit": "unit", "last_updated": "2026-09-26T12:00:00Z"
        }
        json_str = json.dumps(prod_dict)

        proto_obj = inventory_pb2.ProductResponse(
            item_id="PROD-001", name="Laptop ProBook 450", quantity=42, unit_price=1299.99,
            category="Electronics", success=True, message="Produit trouvé."
        )
        proto_bytes = proto_obj.SerializeToString()

        # Mesure JSON serialize
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = json.dumps(prod_dict)
        json_encode_us = ((time.perf_counter() - t0) / iterations) * 1_000_000.0

        # Mesure JSON deserialize
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = json.loads(json_str)
        json_decode_us = ((time.perf_counter() - t0) / iterations) * 1_000_000.0

        # Mesure Protobuf serialize
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = proto_obj.SerializeToString()
        proto_encode_us = ((time.perf_counter() - t0) / iterations) * 1_000_000.0

        # Mesure Protobuf deserialize
        t0 = time.perf_counter()
        target = inventory_pb2.ProductResponse()
        for _ in range(iterations):
            target.ParseFromString(proto_bytes)
        proto_decode_us = ((time.perf_counter() - t0) / iterations) * 1_000_000.0

        return {
            "iterations": iterations,
            "json": {
                "encode_us": round(json_encode_us, 3),
                "decode_us": round(json_decode_us, 3),
                "total_us": round(json_encode_us + json_decode_us, 3),
            },
            "protobuf": {
                "encode_us": round(proto_encode_us, 3),
                "decode_us": round(proto_decode_us, 3),
                "total_us": round(proto_encode_us + proto_decode_us, 3),
            },
        }

    def run_concurrency_benchmark(
        self,
        adapter: BaseBenchmarkAdapter,
        operation: str = "calculate_factorial",
        concurrency_levels: Optional[List[int]] = None,
        iterations_per_worker: int = 50,
        **kwargs,
    ) -> Dict[int, BenchmarkResult]:
        """
        Mesure le débit et la latence sous différents niveaux de concurrence multi-threadée (1, 5, 10, 20).
        """
        levels = concurrency_levels or [1, 5, 10, 20]
        results_by_concurrency: Dict[int, BenchmarkResult] = {}

        for workers in levels:
            all_latencies: List[float] = []
            errors = 0

            def worker_task():
                local_latencies = []
                local_errors = 0
                for _ in range(iterations_per_worker):
                    t0 = time.perf_counter()
                    try:
                        self._dispatch_call(adapter, operation, **kwargs)
                        t1 = time.perf_counter()
                        local_latencies.append((t1 - t0) * 1000.0)
                    except Exception:
                        local_errors += 1
                return local_latencies, local_errors

            t_start = time.perf_counter()
            with futures.ThreadPoolExecutor(max_workers=workers) as executor:
                tasks = [executor.submit(worker_task) for _ in range(workers)]
                for fut in tasks:
                    lats, errs = fut.result()
                    all_latencies.extend(lats)
                    errors += errs
            t_total = time.perf_counter() - t_start

            results_by_concurrency[workers] = BenchmarkResult(
                name=f"{adapter.name}-c{workers}",
                operation=operation,
                latencies_ms=all_latencies,
                total_time_seconds=t_total,
                warmup_iterations=0,
                error_count=errors,
                concurrency=workers,
            )

        return results_by_concurrency

    def run_full_suite(
        self, iterations: int = 500, warmup_iterations: int = 50
    ) -> Dict[str, Any]:
        """
        Exécute la campagne complète de benchmark comparatif sur tous les adaptateurs enregistrés.
        """
        latency_results: Dict[str, Dict[str, Any]] = {}

        for adapter in self.adapters:
            res = self.run_latency_benchmark(
                adapter=adapter,
                operation="calculate_factorial",
                iterations=iterations,
                warmup_iterations=warmup_iterations,
                n=5,
            )
            latency_results[adapter.name] = res.to_dict()

        payload_results = self.run_payload_size_comparison()
        serialization_results = self.run_serialization_benchmark(iterations=iterations)

        return {
            "latency_comparison": latency_results,
            "payload_sizes": payload_results,
            "serialization_microbenchmark": serialization_results,
        }

    @staticmethod
    def format_comparison_table(results: List[BenchmarkResult]) -> str:
        """
        Formate une liste de résultats sous forme de tableau texte aligné.
        """
        lines = [
            f"{'Protocole':<15} | {'Opération':<22} | {'Moyenne':<10} | {'Médiane':<10} | {'p95':<10} | {'p99':<10} | {'Débit (RPS)':<12}",
            "-" * 105,
        ]
        for r in results:
            lines.append(
                f"{r.name:<15} | {r.operation:<22} | {r.mean_ms:>8.3f}ms | {r.median_ms:>8.3f}ms | "
                f"{r.p95_ms:>8.3f}ms | {r.p99_ms:>8.3f}ms | {r.throughput_rps:>10.1f} req/s"
            )
        return "\n".join(lines)
