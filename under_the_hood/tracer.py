"""
Traceur pédagogique du cycle RPC ("Mode Sous le capot").

Le client stub et le server skeleton du Custom RPC acceptent un paramètre
optionnel `tracer`. Quand il est fourni, chaque étape d'un appel est
enregistrée avec un horodatage précis, puis affichable sous forme de frise :

    1. CLIENT_CALL        appel de la fonction côté client
    2. STUB_MARSHAL       le stub construit le message (méthode + arguments)
    3. SERIALIZE          message -> octets JSON
    4. TRANSPORT_SEND     trame TCP envoyée (préfixe 4 octets + corps)
    5. SERVER_RECEIVE     le serveur lit la trame
    6. DESERIALIZE        octets -> dictionnaire Python
    7. DISPATCH           le dispatcher cherche la méthode dans la table blanche
    8. EXECUTE            la vraie fonction métier s'exécute
    9. SERIALIZE_RESPONSE résultat -> octets JSON
   10. TRANSPORT_REPLY    trame de réponse envoyée
   11. CLIENT_RECEIVE     le client lit la trame de réponse
   12. UNMARSHAL          octets -> valeur Python rendue à l'appelant

Le traceur est thread-safe (le serveur traite les connexions dans des threads).
"""

import threading
import time
from typing import Any, Dict, List, Optional


def preview_bytes(data: bytes, limit: int = 160) -> str:
    """Retourne un aperçu lisible d'une séquence d'octets (texte si possible, sinon hex)."""
    try:
        text = data.decode("utf-8")
        printable = all(ch.isprintable() or ch in "\r\n\t" for ch in text)
    except UnicodeDecodeError:
        printable = False
        text = ""
    if printable:
        return text if len(text) <= limit else text[:limit] + "…"
    hexa = data.hex(" ")
    return hexa if len(hexa) <= limit else hexa[:limit] + "…"


class RPCTracer:
    """Enregistreur et formateur des étapes d'un appel RPC."""

    def __init__(self, enabled: bool = True, live: bool = False):
        """
        Args:
            enabled: si False, aucun enregistrement (coût nul).
            live: si True, chaque étape est aussi affichée immédiatement
                  (utile côté serveur lancé dans un terminal séparé).
        """
        self.enabled = enabled
        self.live = live
        self.traces: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Enregistrement
    # ------------------------------------------------------------------ #
    def record_step(
        self,
        step_name: str,
        details: Optional[Dict[str, Any]] = None,
        call_id: Optional[str] = None,
        side: str = "client",
    ) -> None:
        """Enregistre un événement dans la trace d'un appel RPC."""
        if not self.enabled:
            return
        event = {
            "step": step_name,
            "side": side,
            "call_id": call_id,
            "t": time.perf_counter(),
            "thread": threading.current_thread().name,
            "details": dict(details or {}),
        }
        with self._lock:
            self.traces.append(event)
        if self.live:
            who = "CLIENT" if side == "client" else "SERVEUR"
            short = ", ".join(
                f"{k}={preview_bytes(bytes(v), 80) if isinstance(v, (bytes, bytearray)) else v}"
                for k, v in event["details"].items()
            )
            print(f"[{who}] {step_name} │ {short}", flush=True)

    def clear(self) -> None:
        with self._lock:
            self.traces.clear()

    def get_trace(self, call_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retourne les étapes (d'un appel précis si call_id est fourni), triées dans le temps."""
        with self._lock:
            events = [e for e in self.traces if call_id is None or e["call_id"] == call_id]
        return sorted(events, key=lambda e: e["t"])

    def call_ids(self) -> List[str]:
        seen: List[str] = []
        for e in self.get_trace():
            if e["call_id"] and e["call_id"] not in seen:
                seen.append(e["call_id"])
        return seen

    # ------------------------------------------------------------------ #
    # Affichage
    # ------------------------------------------------------------------ #
    def format_trace(self, call_id: Optional[str] = None) -> str:
        """Construit la frise textuelle d'un appel (ou de toutes les étapes)."""
        events = self.get_trace(call_id)
        if not events:
            return "(aucune étape enregistrée)"

        t0 = events[0]["t"]
        lines = []
        if call_id:
            lines.append(f"Appel {call_id}")
        for i, e in enumerate(events, start=1):
            delta_ms = (e["t"] - t0) * 1000.0
            who = "CLIENT" if e["side"] == "client" else "SERVEUR"
            lines.append(f"{i:>2}. [+{delta_ms:8.3f} ms] {who:<7} │ {e['step']}")
            for key, value in e["details"].items():
                if isinstance(value, (bytes, bytearray)):
                    value = preview_bytes(bytes(value))
                lines.append(f"{'':>24}│   {key}: {value}")
        total_ms = (events[-1]["t"] - t0) * 1000.0
        lines.append(f"{'':>24}└── Durée totale observée : {total_ms:.3f} ms")
        return "\n".join(lines)

    def display_trace(self, call_id: Optional[str] = None) -> str:
        """Affiche la frise de l'appel et la retourne (pratique pour les tests)."""
        text = self.format_trace(call_id)
        print(text)
        return text
