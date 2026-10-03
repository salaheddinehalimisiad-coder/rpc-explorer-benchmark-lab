"""
Démonstration "Sous le capot" : le MÊME appel métier observé sur les trois protocoles.

    python main.py --under-the-hood
    python main.py --under-the-hood --method update_stock --args item_id=PROD-002 quantity_delta=-1
"""

from typing import Any, Dict

import requests

from cli.ui import explain, section, title
from lab.servers import LabServers
from under_the_hood.protobuf_inspector import GRPCInspectorInterceptor
from under_the_hood.tracer import RPCTracer

DEFAULT_ARGS = {
    "calculate_factorial": {"n": 5},
    "get_product_details": {"item_id": "PROD-001"},
    "update_stock": {"item_id": "PROD-002", "quantity_delta": -1},
    "stream_analytics": {"metric_name": "cpu_usage", "num_events": 3},
}


def _rest_request(base: str, method: str, args: Dict[str, Any]) -> requests.Request:
    if method == "calculate_factorial":
        req = requests.Request("POST", f"{base}/api/factorial", json={"n": args["n"]})
    elif method == "get_product_details":
        req = requests.Request("GET", f"{base}/api/products/{args['item_id']}")
    elif method == "update_stock":
        req = requests.Request("POST", f"{base}/api/products/{args['item_id']}/stock",
                               json={"quantity_delta": args["quantity_delta"]})
    elif method == "stream_analytics":
        req = requests.Request("GET", f"{base}/api/analytics/{args['metric_name']}",
                               params={"count": args.get("num_events", 5)})
    else:
        raise ValueError(f"Méthode inconnue : {method}")
    return req


def _http_text(prepared: requests.PreparedRequest) -> str:
    from urllib.parse import urlsplit
    url = urlsplit(prepared.url)
    path = url.path + (f"?{url.query}" if url.query else "")
    lines = [f"{prepared.method} {path} HTTP/1.1", f"Host: {url.netloc}"]
    lines += [f"{k}: {v}" for k, v in prepared.headers.items()]
    body = prepared.body or b""
    if isinstance(body, str):
        body = body.encode()
    return "\r\n".join(lines) + "\r\n\r\n" + body.decode("utf-8", "replace")


def _grpc_call(client, method: str, args: Dict[str, Any]):
    if method == "calculate_factorial":
        return client.calculate_factorial(args["n"])
    if method == "get_product_details":
        return client.get_product_details(args["item_id"])
    if method == "update_stock":
        return client.update_stock(args["item_id"], args["quantity_delta"])
    if method == "stream_analytics":
        return list(client.stream_analytics(args["metric_name"], args.get("num_events", 5)))
    raise ValueError(method)


def run_under_the_hood_demo(method: str = "calculate_factorial", args: Dict[str, Any] = None) -> None:
    args = dict(args or DEFAULT_ARGS[method])
    tracer = RPCTracer()
    with LabServers(tracer=tracer) as lab:
        title(f"SOUS LE CAPOT — {method}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
        print(lab.describe())

        # 1. Custom RPC ---------------------------------------------------
        section("1) CUSTOM RPC — JSON sur socket TCP (notre propre middleware)")
        client = lab.custom_client(tracer=tracer)
        result = getattr(client, method)(**args)  # <- ressemble à un appel local !
        tracer.display_trace(tracer.call_ids()[-1])
        print(f"\nRésultat reçu : {result!r}")
        explain("""
Le code appelant a juste écrit  client.%s(...)  : le STUB a fabriqué le message JSON,
le TRANSPORT l'a envoyé sur TCP, le SKELETON du serveur l'a décodé, le DISPATCHER a
vérifié la table blanche puis a exécuté la vraie fonction. Tout cela est invisible
pour l'appelant : c'est la « transparence de localisation ».""" % method)

        # 2. gRPC ----------------------------------------------------------
        section("2) gRPC — Protobuf binaire sur HTTP/2 (stub généré depuis le .proto)")
        inspector = GRPCInspectorInterceptor()
        gclient = lab.grpc_client(interceptors=[inspector])
        if method == "stream_analytics":
            res = _grpc_call(gclient, method, args)
            print("StreamAnalytics est un appel SERVER STREAMING : 1 requête → plusieurs réponses.")
            for i, ev in enumerate(res, 1):
                print(f"  message n°{i} reçu : {ev}")
        else:
            res = _grpc_call(gclient, method, args)
            print(GRPCInspectorInterceptor.format_call(inspector.calls[-1]))
            print(f"\nRésultat reçu : {res!r}")
        gclient.close()
        explain("""
Sur le réseau, Protobuf n'envoie PAS les noms des champs, seulement leurs NUMÉROS
(ex: « 08 05 » = champ n°1, varint, valeur 5). D'où des messages très compacts…
mais illisibles sans le contrat .proto partagé par le client et le serveur.""")

        # 3. REST ----------------------------------------------------------
        section("3) REST — JSON sur HTTP/1.1 (ressources + verbes HTTP)")
        with requests.Session() as s:
            prepared = s.prepare_request(_rest_request(f"http://{lab.host}:{lab.rest_port}", method, args))
            raw = _http_text(prepared)
            print(f"Requête HTTP envoyée (texte brut, {len(raw.encode())} octets au total) :")
            print("  " + raw.replace("\r\n", "\n  "))
            resp = s.send(prepared, timeout=5)
        print(f"\nRéponse : HTTP {resp.status_code} {resp.reason}")
        for k in ("Content-Type", "Content-Length"):
            if k in resp.headers:
                print(f"  {k}: {resp.headers[k]}")
        print(f"  corps ({len(resp.content)} octets) : {resp.text.strip()[:300]}")
        explain("""
REST ne parle pas de « procédures » mais de RESSOURCES (/api/products/PROD-001)
manipulées par des verbes HTTP (GET, POST…). Les en-têtes HTTP en texte ajoutent
des dizaines d'octets à chaque appel, en plus du JSON.""")
