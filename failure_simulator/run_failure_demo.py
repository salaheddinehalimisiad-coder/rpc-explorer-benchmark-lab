"""
Script d'execution et de mesure reelle des scenarios de pannes (Phase 07).

Mesure et compare experimentalement :
1. Baseline nominale vs Injection de latence (50ms, 100ms, 200ms) sur Custom RPC, gRPC et REST
2. Comportement reels face aux timeouts
3. Comportements reels face aux crashs serveur
4. Comportements face aux messages corrompus et requetes invalides
5. Verification du retour a la baseline apres reset (isolation)
"""

import time
import socket
import json
import statistics
from typing import Dict, Any, List, Optional, Sequence

from failure_simulator import (
    FailureSimulator,
    MessageCorruptor,
)
from business.inventory_service import InventoryService
from rpc_core.server_skeleton import RPCServer
from rpc_core.client_stub import RPCClient, RPCError
from rpc_core.transport import send_message, receive_message
from grpc.grpc_server import InventoryGRPCServer
from grpc.grpc_client import InventoryGRPCClient
import grpc
from rest.rest_server import RestServer
from rest.rest_client import RestClient, RestClientError
import requests.exceptions


def measure_custom_rpc(sim: FailureSimulator, iterations: int = 50) -> Dict[str, Any]:
    svc = InventoryService()
    server = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim)
    server.register_method("calculate_factorial", svc.calculate_factorial)
    server.start(threaded=True)

    latencies: List[float] = []
    errors = 0
    try:
        client = RPCClient(host="127.0.0.1", port=server.port, timeout=2.0)
        # warm-up
        for _ in range(5):
            client.call("calculate_factorial", n=5)

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                res = client.call("calculate_factorial", n=5)
                elapsed = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed)
            except Exception:
                errors += 1
    finally:
        server.stop()

    return {
        "count": len(latencies),
        "mean_ms": statistics.mean(latencies) if latencies else 0.0,
        "median_ms": statistics.median(latencies) if latencies else 0.0,
        "min_ms": min(latencies) if latencies else 0.0,
        "max_ms": max(latencies) if latencies else 0.0,
        "errors": errors,
    }


def measure_grpc(sim: FailureSimulator, iterations: int = 50) -> Dict[str, Any]:
    server = InventoryGRPCServer(port=0, failure_simulator=sim)
    port = server.start()

    latencies: List[float] = []
    errors = 0
    try:
        client = InventoryGRPCClient(port=port, timeout=2.0)
        # warm-up
        for _ in range(5):
            client.calculate_factorial(5)

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                res = client.calculate_factorial(5)
                elapsed = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed)
            except Exception:
                errors += 1
        client.close()
    finally:
        server.stop(grace=0.1)

    return {
        "count": len(latencies),
        "mean_ms": statistics.mean(latencies) if latencies else 0.0,
        "median_ms": statistics.median(latencies) if latencies else 0.0,
        "min_ms": min(latencies) if latencies else 0.0,
        "max_ms": max(latencies) if latencies else 0.0,
        "errors": errors,
    }


def measure_rest(sim: FailureSimulator, iterations: int = 50) -> Dict[str, Any]:
    server = RestServer(port=0, failure_simulator=sim)
    port = server.start(threaded=True)

    latencies: List[float] = []
    errors = 0
    try:
        client = RestClient(base_url=f"http://127.0.0.1:{port}", timeout=2.0)
        # warm-up
        for _ in range(5):
            client.calculate_factorial(5)

        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                res = client.calculate_factorial(5)
                elapsed = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed)
            except Exception:
                errors += 1
        client.close()
    finally:
        server.stop()

    return {
        "count": len(latencies),
        "mean_ms": statistics.mean(latencies) if latencies else 0.0,
        "median_ms": statistics.median(latencies) if latencies else 0.0,
        "min_ms": min(latencies) if latencies else 0.0,
        "max_ms": max(latencies) if latencies else 0.0,
        "errors": errors,
    }


DEFAULT_RESULTS_PATH = "failure_simulator/experiment_results.json"


def run_latency_experiment(
    delays: Sequence[float] = (0.0, 50.0, 100.0), iterations: int = 30
) -> Dict[str, Any]:
    """Mesure Custom RPC / gRPC / REST pour chaque latence artificielle (ms)."""
    print("=== 1. Mesure de l'impact de la latence artificielle ===")
    latency_results: Dict[str, Any] = {}

    for delay in delays:
        sim = FailureSimulator()
        if delay > 0:
            sim.enable_latency_spike(delay)

        rpc_res = measure_custom_rpc(sim, iterations=iterations)
        grpc_res = measure_grpc(sim, iterations=iterations)
        rest_res = measure_rest(sim, iterations=iterations)

        latency_results[f"delay_{int(delay)}ms"] = {
            "Custom RPC": rpc_res,
            "gRPC": grpc_res,
            "REST": rest_res,
        }
        print(f"Delay {int(delay)}ms:")
        print(f"  Custom RPC: mean={rpc_res['mean_ms']:.2f}ms, median={rpc_res['median_ms']:.2f}ms")
        print(f"  gRPC:       mean={grpc_res['mean_ms']:.2f}ms, median={grpc_res['median_ms']:.2f}ms")
        print(f"  REST:       mean={rest_res['mean_ms']:.2f}ms, median={rest_res['median_ms']:.2f}ms")

    return latency_results


def run_timeout_experiment(
    failure_delay_seconds: float = 1.0, client_timeout: float = 0.2
) -> Dict[str, Any]:
    """Le serveur retient sa réponse ``failure_delay_seconds`` ; le client abandonne après ``client_timeout``."""
    print("\n=== 2. Simulation de Timeout ===")

    # Custom RPC Timeout
    sim_t = FailureSimulator()
    sim_t.simulate_timeout(failure_delay_seconds=failure_delay_seconds)
    server_rpc = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim_t)
    server_rpc.register_method("calculate_factorial", InventoryService().calculate_factorial)
    server_rpc.start(threaded=True)
    try:
        client = RPCClient(host="127.0.0.1", port=server_rpc.port, timeout=client_timeout)
        t0 = time.perf_counter()
        try:
            client.call("calculate_factorial", n=5)
            rpc_t_status = "UNEXPECTED_SUCCESS"
        except (TimeoutError, socket.timeout, ConnectionError) as err:
            rpc_t_status = f"TIMEOUT_CAUGHT: {type(err).__name__}"
        rpc_t_elapsed = (time.perf_counter() - t0) * 1000.0
    finally:
        server_rpc.stop()

    # gRPC Timeout
    server_grpc = InventoryGRPCServer(port=0, failure_simulator=sim_t)
    gport = server_grpc.start()
    try:
        gclient = InventoryGRPCClient(port=gport, timeout=client_timeout)
        t0 = time.perf_counter()
        try:
            gclient.calculate_factorial(5)
            grpc_t_status = "UNEXPECTED_SUCCESS"
        except grpc.RpcError as err:
            grpc_t_status = f"GRPC_ERROR: {err.code()}"
        grpc_t_elapsed = (time.perf_counter() - t0) * 1000.0
        gclient.close()
    finally:
        server_grpc.stop(grace=0.1)

    # REST Timeout
    server_rest = RestServer(port=0, failure_simulator=sim_t)
    rport = server_rest.start(threaded=True)
    try:
        rclient = RestClient(base_url=f"http://127.0.0.1:{rport}", timeout=client_timeout)
        t0 = time.perf_counter()
        try:
            rclient.calculate_factorial(5)
            rest_t_status = "UNEXPECTED_SUCCESS"
        except (RestClientError, requests.exceptions.Timeout) as err:
            rest_t_status = f"REST_TIMEOUT: {type(err).__name__}"
        rest_t_elapsed = (time.perf_counter() - t0) * 1000.0
        rclient.close()
    finally:
        server_rest.stop()

    timeout_results = {
        "Custom RPC": {"status": rpc_t_status, "elapsed_ms": rpc_t_elapsed},
        "gRPC": {"status": grpc_t_status, "elapsed_ms": grpc_t_elapsed},
        "REST": {"status": rest_t_status, "elapsed_ms": rest_t_elapsed},
    }
    print(f"Custom RPC Timeout: {rpc_t_status} in {rpc_t_elapsed:.1f}ms")
    print(f"gRPC Timeout:       {grpc_t_status} in {grpc_t_elapsed:.1f}ms")
    print(f"REST Timeout:       {rest_t_status} in {rest_t_elapsed:.1f}ms")

    return timeout_results


def run_crash_experiment() -> Dict[str, Any]:
    """Simule un crash serveur brutal et relève l'erreur observée par chaque client."""
    print("\n=== 3. Simulation de Crash Serveur Brutal ===")

    sim_c = FailureSimulator()
    sim_c.simulate_server_crash()

    # Custom RPC Crash
    server_rpc_c = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim_c)
    server_rpc_c.register_method("calculate_factorial", InventoryService().calculate_factorial)
    server_rpc_c.start(threaded=True)
    try:
        client = RPCClient(host="127.0.0.1", port=server_rpc_c.port, timeout=1.0)
        try:
            client.call("calculate_factorial", n=5)
            rpc_c_status = "UNEXPECTED_SUCCESS"
        except Exception as err:
            rpc_c_status = f"CRASH_CAUGHT: {type(err).__name__}"
    finally:
        server_rpc_c.stop()

    # gRPC Crash
    server_grpc_c = InventoryGRPCServer(port=0, failure_simulator=sim_c)
    gport_c = server_grpc_c.start()
    try:
        gclient = InventoryGRPCClient(port=gport_c, timeout=1.0)
        try:
            gclient.calculate_factorial(5)
            grpc_c_status = "UNEXPECTED_SUCCESS"
        except grpc.RpcError as err:
            grpc_c_status = f"GRPC_CRASH: {err.code()}"
        gclient.close()
    finally:
        server_grpc_c.stop(grace=0.1)

    # REST Crash
    server_rest_c = RestServer(port=0, failure_simulator=sim_c)
    rport_c = server_rest_c.start(threaded=True)
    try:
        rclient = RestClient(base_url=f"http://127.0.0.1:{rport_c}", timeout=1.0)
        try:
            rclient.calculate_factorial(5)
            rest_c_status = "UNEXPECTED_SUCCESS"
        except RestClientError as err:
            rest_c_status = f"REST_CRASH: HTTP {err.status_code} ({err.error_code})"
        rclient.close()
    finally:
        server_rest_c.stop()

    crash_results = {
        "Custom RPC": rpc_c_status,
        "gRPC": grpc_c_status,
        "REST": rest_c_status,
    }
    print(f"Custom RPC Crash: {rpc_c_status}")
    print(f"gRPC Crash:       {grpc_c_status}")
    print(f"REST Crash:       {rest_c_status}")

    return crash_results


def run_isolation_experiment(latency_ms: float = 50.0) -> Dict[str, Any]:
    """Vérifie le retour à la baseline après reset() du simulateur."""
    print("\n=== 4. Test d'Isolation et Reset ===")
    sim_iso = FailureSimulator()
    server_iso = RPCServer(host="127.0.0.1", port=0, failure_simulator=sim_iso)
    server_iso.register_method("calculate_factorial", InventoryService().calculate_factorial)
    server_iso.start(threaded=True)
    try:
        client = RPCClient(host="127.0.0.1", port=server_iso.port, timeout=2.0)
        t0 = time.perf_counter()
        client.call("calculate_factorial", n=5)
        iso_base = (time.perf_counter() - t0) * 1000.0

        sim_iso.enable_latency_spike(latency_ms)
        t0 = time.perf_counter()
        client.call("calculate_factorial", n=5)
        iso_spiked = (time.perf_counter() - t0) * 1000.0

        sim_iso.reset()
        t0 = time.perf_counter()
        client.call("calculate_factorial", n=5)
        iso_restored = (time.perf_counter() - t0) * 1000.0
    finally:
        server_iso.stop()

    isolation_results = {
        "baseline_ms": iso_base,
        f"with_latency_{int(latency_ms)}ms": iso_spiked,
        "restored_nominal_ms": iso_restored,
    }
    print(f"Isolation: Baseline={iso_base:.2f}ms -> Latency={iso_spiked:.2f}ms -> Restored={iso_restored:.2f}ms")

    return isolation_results


def run_all_experiments(
    iterations: int = 30,
    delays: Sequence[float] = (0.0, 50.0, 100.0),
    timeout_delay_seconds: float = 1.0,
    client_timeout: float = 0.2,
    output_path: Optional[str] = DEFAULT_RESULTS_PATH,
) -> Dict[str, Any]:
    """
    Enchaîne les 4 expériences (latence, timeout, crash, isolation).

    Les valeurs par défaut reproduisent la campagne Phase 07 d'origine.
    ``output_path=None`` désactive l'écriture du fichier JSON.
    """
    results: Dict[str, Any] = {
        "latency_experiments": run_latency_experiment(delays=delays, iterations=iterations),
        "timeout_experiments": run_timeout_experiment(
            failure_delay_seconds=timeout_delay_seconds, client_timeout=client_timeout
        ),
        "crash_experiments": run_crash_experiment(),
        "isolation_experiment": run_isolation_experiment(),
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    run_all_experiments()
