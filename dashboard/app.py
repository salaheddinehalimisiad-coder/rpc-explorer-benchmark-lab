"""
Tableau de bord web du RPC Explorer (local, sans dépendance Internet).

    python main.py --dashboard            → ouvre http://127.0.0.1:8080

Le tableau de bord démarre les trois serveurs (Custom RPC, gRPC, REST) autour
d'un même service métier, puis expose une petite API JSON utilisée par la page :

    GET  /api/info                 état des serveurs et du simulateur
    POST /api/call                 un appel (protocole, méthode, arguments) + détail « sous le capot »
    POST /api/faults               injecter / retirer une panne sur ces serveurs
    GET  /api/stream               flux Custom RPC relayé au navigateur (Server-Sent Events)
    POST /api/stream_unary         la même série de mesures en UNE réponse (comparaison)
    POST /api/benchmark            campagne de latence courte sur les 5 variantes
    POST /api/experiment/<nom>     une expérience de lab/failures.py ou du contrat

Le tableau de bord n'est qu'une INTERFACE : toute la logique reste dans
rpc_core / grpc_impl / rest / lab (aucun calcul de résultat ici).
"""

import io
import json
import os
import threading
import time
import webbrowser
from contextlib import redirect_stdout
from typing import Any, Dict

import grpc
import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.serving import make_server

from benchmark import BenchmarkRunner
from benchmark.adapters import CustomRPCAdapter, GRPCAdapter, LocalAdapter, RESTAdapter
from failure_simulator import FailureSimulator
from lab.servers import LabServers
from rest.rest_client import RestClientError
from rpc_core import RPCError
from under_the_hood.protobuf_inspector import GRPCInspectorInterceptor, decode_wire
from under_the_hood.tracer import RPCTracer, preview_bytes

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
METHODS = {
    "calculate_factorial": {"n": 5},
    "get_product_details": {"item_id": "PROD-001"},
    "update_stock": {"item_id": "PROD-001", "quantity_delta": -1},
    "stream_analytics": {"metric_name": "cpu_usage", "num_events": 3},
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return preview_bytes(bytes(value), 600)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _proto_view(message) -> Dict[str, Any]:
    data = message.SerializeToString()
    names = {f.number: f.name for f in message.DESCRIPTOR.fields}
    return {
        "type": message.DESCRIPTOR.full_name,
        "size": len(data),
        "hex": data.hex(" "),
        "fields": [dict(f, name=names.get(f["field_number"], "?")) for f in decode_wire(data)],
    }


class Dashboard:
    def __init__(self):
        self.tracer = RPCTracer()
        self.simulator = FailureSimulator()
        self.lab = LabServers(tracer=self.tracer, failure_simulator=self.simulator)
        self._call_lock = threading.Lock()
        self.app = self._build_app()

    # ------------------------------------------------------------------ #
    def info(self) -> Dict[str, Any]:
        return {
            "servers": {"custom": self.lab.custom_port, "grpc": self.lab.grpc_port, "rest": self.lab.rest_port},
            "simulator": self.simulator.get_status(),
            "methods": METHODS,
            "catalog": [{"item_id": k, "name": v["name"], "stock": v["stock"]}
                        for k, v in self.lab.service._catalog.items()],
        }

    def call(self, protocol: str, method: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if method not in METHODS:
            raise ValueError(f"Méthode inconnue : {method}")
        out: Dict[str, Any] = {"protocol": protocol, "method": method, "args": args}
        with self._call_lock:
            self.tracer.clear()
            t0 = time.perf_counter()
            try:
                if protocol == "custom":
                    out["result"] = self._call_custom(method, args)
                elif protocol == "grpc":
                    out.update(self._call_grpc(method, args))
                elif protocol == "rest":
                    out.update(self._call_rest(method, args))
                else:
                    raise ValueError(f"Protocole inconnu : {protocol}")
                out["status"] = "OK"
            except RPCError as e:
                out["status"], out["error"] = e.code, e.message
            except grpc.RpcError as e:
                out["status"], out["error"] = e.code().name, e.details()
            except RestClientError as e:
                out["status"], out["error"] = f"HTTP {e.status_code} {e.error_code}", e.message
            except (ConnectionError, TimeoutError) as e:
                out["status"], out["error"] = type(e).__name__, str(e)
            out["elapsed_ms"] = (time.perf_counter() - t0) * 1000
            if protocol == "custom":
                events = self.tracer.get_trace()
                base = events[0]["t"] if events else 0
                out["trace"] = [{"step": e["step"], "side": e["side"], "t_ms": (e["t"] - base) * 1000,
                                 "details": _jsonable(e["details"])} for e in events]
        out["result"] = _jsonable(out.get("result"))
        return out

    def _call_custom(self, method, args):
        client = self.lab.custom_client(timeout=2.0, tracer=self.tracer)
        if method == "stream_analytics":
            return list(client.stream(method, **args))
        return client.call(method, **args)

    def _call_grpc(self, method, args):
        from protos import inventory_pb2 as pb
        inspector = GRPCInspectorInterceptor()
        client = self.lab.grpc_client(timeout=2.0, interceptors=[inspector])
        try:
            if method == "calculate_factorial":
                res = client.calculate_factorial(args["n"])
            elif method == "get_product_details":
                res = client.get_product_details(args["item_id"])
            elif method == "update_stock":
                res = client.update_stock(args["item_id"], args["quantity_delta"])
            else:
                res = list(client.stream_analytics(args["metric_name"], args.get("num_events", 3)))
                req = pb.AnalyticsRequest(metric_name=args["metric_name"], count=args.get("num_events", 3))
                return {"result": res, "grpc": {"path": "/inventory.InventoryRPCService/StreamAnalytics",
                                                "request": _proto_view(req), "streamed_messages": len(res)}}
        finally:
            client.close()
        rec = inspector.calls[-1]
        return {"result": res, "grpc": {"path": rec["method"], "request": _proto_view(rec["request"]),
                                        "response": _proto_view(rec["response"]) if "response" in rec else None}}

    def _call_rest(self, method, args):
        base = f"http://127.0.0.1:{self.lab.rest_port}"
        if method == "calculate_factorial":
            req = requests.Request("POST", f"{base}/api/factorial", json={"n": args["n"]})
        elif method == "get_product_details":
            req = requests.Request("GET", f"{base}/api/products/{args['item_id']}")
        elif method == "update_stock":
            req = requests.Request("POST", f"{base}/api/products/{args['item_id']}/stock",
                                   json={"quantity_delta": args["quantity_delta"]})
        else:
            req = requests.Request("GET", f"{base}/api/analytics/{args['metric_name']}",
                                   params={"count": args.get("num_events", 3)})
        with requests.Session() as s:
            prepared = s.prepare_request(req)
            from under_the_hood.explorer import _http_text
            raw = _http_text(prepared)
            try:
                resp = s.send(prepared, timeout=2.0)
            except requests.Timeout as e:
                raise RestClientError(str(e), 504, "TIMEOUT")
            except requests.RequestException as e:
                raise RestClientError(str(e), 503, "CONNECTION_ERROR")
        http = {"request": raw, "request_size": len(raw.encode()),
                "response_status": f"{resp.status_code} {resp.reason}",
                "response_headers": dict(resp.headers), "response_body": resp.text,
                "response_size": len(resp.content)}
        body = resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else resp.text
        if not resp.ok:
            raise RestClientError(body.get("error", resp.text) if isinstance(body, dict) else body,
                                  resp.status_code, body.get("code", "HTTP_ERROR") if isinstance(body, dict) else "HTTP_ERROR")
        return {"result": body, "http": http}

    def faults(self, kind: str, value: float = 0) -> Dict[str, Any]:
        self.simulator.reset()
        if kind == "latency":
            self.simulator.enable_latency_spike(float(value or 200))
        elif kind == "timeout":
            self.simulator.simulate_timeout(float(value or 3))
        elif kind == "crash":
            self.simulator.simulate_server_crash()
        elif kind != "reset":
            raise ValueError(f"Panne inconnue : {kind}")
        return self.simulator.get_status()

    def benchmark(self, iterations: int, operation: str) -> Dict[str, Any]:
        iterations = max(10, min(int(iterations), 5000))
        kwargs = {"calculate_factorial": {"n": 10}, "get_product_details": {"item_id": "PROD-001"}}[operation]
        runner = BenchmarkRunner()
        lab = self.lab
        adapters = [
            LocalAdapter(service=lab.service),
            CustomRPCAdapter(port=lab.custom_port, client=lab.custom_client(persistent=False)),
            CustomRPCAdapter(port=lab.custom_port, client=lab.custom_client(persistent=True)),
            GRPCAdapter(port=lab.grpc_port, client=lab.grpc_client()),
            RESTAdapter(base_url=f"http://127.0.0.1:{lab.rest_port}", client=lab.rest_client()),
        ]
        labels = ["Local", "Custom RPC (1 cnx/appel)", "Custom RPC (cnx persistante)", "gRPC", "REST"]
        results = []
        try:
            for label, a in zip(labels, adapters):
                r = runner.run_latency_benchmark(a, operation=operation, iterations=iterations,
                                                 warmup_iterations=max(5, iterations // 10), **kwargs)
                d = r.to_dict()
                d["name"] = label
                results.append(d)
        finally:
            for a in adapters:
                a.close()
        sizes = runner.run_payload_size_comparison()
        return {"iterations": iterations, "operation": operation, "results": results,
                "payload_sizes": sizes[operation], "simulator_active": self.simulator.is_active}

    def experiment(self, name: str) -> Dict[str, Any]:
        from lab import failures
        runners = {
            "latency": lambda: failures.scenario_latency(),
            "timeout": lambda: failures.scenario_timeout(),
            "server_down": lambda: failures.scenario_server_down(),
            "retry_restart": lambda: failures.scenario_retry_on_restart(),
            "idempotence": lambda: failures.scenario_retry_not_idempotent(),
        }
        if name == "contract":
            from contract_evolution.demo import run_custom_rpc_scenarios, run_grpc_scenarios
            runners["contract"] = lambda: {"custom_rpc": run_custom_rpc_scenarios(), "grpc": run_grpc_scenarios()}
        if name not in runners:
            raise ValueError(f"Expérience inconnue : {name}")
        with redirect_stdout(io.StringIO()):  # les expériences impriment aussi pour la console
            return _jsonable(runners[name]())

    def stream_events(self, num_events: int, interval_ms: float):
        """Relaie un flux Custom RPC vers le navigateur, élément par élément (Server-Sent Events)."""
        client = self.lab.custom_client(timeout=10)
        t0 = time.perf_counter()
        try:
            for item in client.stream("stream_analytics", metric_name="cpu_usage",
                                      num_events=num_events, interval_ms=interval_ms):
                payload = {"t_ms": (time.perf_counter() - t0) * 1000, "item": item}
                yield f"data: {json.dumps(payload)}\n\n"
            yield f"event: end\ndata: {json.dumps({'t_ms': (time.perf_counter() - t0) * 1000})}\n\n"
        except (RPCError, ConnectionError, TimeoutError) as e:
            yield f"event: failure\ndata: {json.dumps({'error': str(e)})}\n\n"

    # ------------------------------------------------------------------ #
    def _build_app(self) -> Flask:
        app = Flask(__name__, static_folder=None)

        @app.errorhandler(ValueError)
        def bad_request(e):
            return jsonify({"error": str(e)}), 400

        @app.get("/")
        def index():
            return send_from_directory(STATIC_DIR, "index.html")

        @app.get("/static/<path:filename>")
        def static_files(filename):
            # Polices embarquées : le tableau de bord fonctionne sans Internet.
            return send_from_directory(STATIC_DIR, filename, max_age=86400)

        @app.get("/api/info")
        def api_info():
            return jsonify(self.info())

        @app.post("/api/call")
        def api_call():
            body = request.get_json(force=True)
            return jsonify(self.call(body.get("protocol", "custom"), body.get("method", ""),
                                     body.get("args") or {}))

        @app.post("/api/faults")
        def api_faults():
            body = request.get_json(force=True)
            return jsonify(self.faults(body.get("kind", "reset"), body.get("value", 0)))

        @app.post("/api/benchmark")
        def api_benchmark():
            body = request.get_json(force=True)
            return jsonify(self.benchmark(body.get("iterations", 300),
                                          body.get("operation", "calculate_factorial")))

        @app.post("/api/experiment/<name>")
        def api_experiment(name):
            return jsonify(self.experiment(name))

        @app.post("/api/stream_unary")
        def api_stream_unary():
            body = request.get_json(force=True)
            n = max(1, min(int(body.get("n", 10)), 100))
            interval = max(0.0, min(float(body.get("interval", 300)), 2000.0))
            return jsonify(self.unary_batch(n, interval))

        @app.get("/api/stream")
        def api_stream():
            n = max(1, min(int(request.args.get("n", 10)), 100))
            interval = max(0.0, min(float(request.args.get("interval", 300)), 2000.0))
            return Response(self.stream_events(n, interval), mimetype="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

        return app

    def start(self):
        self.lab.start()
        # Variante « réponse unique » du même capteur lent, pour la comparaison avec le flux :
        # le serveur attend toutes les mesures puis renvoie UNE réponse.
        svc = self.lab.service
        self.lab.custom.register_method(
            "stream_analytics_batch",
            lambda metric_name, num_events, interval_ms=0.0:
                list(svc.stream_analytics_iter(metric_name, num_events, interval_ms)))
        return self

    def unary_batch(self, num_events: int, interval_ms: float) -> Dict[str, Any]:
        client = self.lab.custom_client(timeout=30)
        t0 = time.perf_counter()
        items = client.call("stream_analytics_batch", metric_name="cpu_usage",
                            num_events=num_events, interval_ms=interval_ms)
        return {"t_ms": (time.perf_counter() - t0) * 1000, "items": items}

    def stop(self):
        self.lab.stop()


def run_dashboard(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = True) -> None:
    dash = Dashboard().start()
    server = make_server(host, port, dash.app, threaded=True)
    url = f"http://{host}:{server.server_port}"
    print(f"Tableau de bord : {url}   (Ctrl+C pour arrêter)")
    print(dash.lab.describe())
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du tableau de bord…")
    finally:
        dash.stop()
