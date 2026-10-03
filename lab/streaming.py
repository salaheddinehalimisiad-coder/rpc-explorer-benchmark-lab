"""
Démonstration : réponse unique vs STREAMING.

    python main.py --streaming-demo

Un « capteur » produit une mesure toutes les `interval_ms` millisecondes.
  • Réponse unique (call) : le serveur attend d'avoir TOUTES les mesures,
    puis envoie une seule grosse réponse → l'appelant ne voit rien pendant ce temps.
  • Streaming (stream)    : chaque mesure part dès qu'elle est prête
    → l'appelant reçoit la 1re presque tout de suite.
"""

import time
from typing import Any, Dict

from business.inventory_service import InventoryService
from cli.ui import explain, section, table, title
from lab.servers import build_custom_server
from rpc_core import RPCClient


class _SlowSensorService(InventoryService):
    """La version « réponse unique » attend aussi le capteur, pour une comparaison équitable."""

    def __init__(self, interval_ms: float):
        super().__init__()
        self._interval_ms = interval_ms

    def stream_analytics(self, metric_name: str, num_events: int = 10):
        return list(self.stream_analytics_iter(metric_name, num_events, self._interval_ms))


def run_streaming_demo(num_events: int = 8, interval_ms: float = 150.0) -> Dict[str, Any]:
    title(f"RÉPONSE UNIQUE vs STREAMING — {num_events} mesures, une toutes les {interval_ms:.0f} ms")
    server = build_custom_server(_SlowSensorService(interval_ms))
    server.start()
    results = {}
    try:
        client = RPCClient(port=server.port, timeout=10)

        section("1) Réponse unique : client.stream_analytics(...)")
        print('  events = client.stream_analytics(metric_name="cpu_usage", num_events=%d)' % num_events)
        t0 = time.perf_counter()
        events = client.stream_analytics(metric_name="cpu_usage", num_events=num_events)
        total = (time.perf_counter() - t0) * 1000
        for e in events:
            print(f"  [+{total:7.0f} ms] mesure n°{e['sequence']} = {e['value']}")
        results["unique"] = {"premier_ms": total, "total_ms": total, "messages": 1}

        section("2) Streaming : for e in client.stream(...)")
        print('  for e in client.stream("stream_analytics", metric_name="cpu_usage", '
              'num_events=%d, interval_ms=%d):' % (num_events, interval_ms))
        t0 = time.perf_counter()
        first = None
        n = 0
        for e in client.stream("stream_analytics", metric_name="cpu_usage",
                                 num_events=num_events, interval_ms=interval_ms):
            n += 1
            t = (time.perf_counter() - t0) * 1000
            first = first if first is not None else t
            print(f"  [+{t:7.0f} ms] mesure n°{e['sequence']} = {e['value']}")
        total = (time.perf_counter() - t0) * 1000
        results["stream"] = {"premier_ms": first, "total_ms": total, "messages": n + 1}
    finally:
        server.stop()

    section("Comparaison (mesures réelles)")
    print(table(["Mode", "1re mesure reçue après", "Toutes reçues après", "Trames réseau de réponse"],
                [("Réponse unique", f"{results['unique']['premier_ms']:.0f} ms",
                  f"{results['unique']['total_ms']:.0f} ms", results["unique"]["messages"]),
                 ("Streaming", f"{results['stream']['premier_ms']:.0f} ms",
                  f"{results['stream']['total_ms']:.0f} ms",
                  f"{results['stream']['messages']} ({num_events} données + 1 fin)")]))
    explain("""
La durée TOTALE est quasiment la même : le capteur ne va pas plus vite.
Ce qui change, c'est le délai avant la PREMIÈRE donnée : en streaming l'appelant
peut afficher/traiter chaque mesure dès qu'elle existe (tableau de bord, logs…).
Coût : une trame (et un en-tête JSON) par élément au lieu d'une seule réponse.
gRPC fait la même chose nativement (« server streaming », mot-clé `stream` du .proto).""")
    return results
