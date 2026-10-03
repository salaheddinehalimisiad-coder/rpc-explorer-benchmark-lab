"""
Inspection des messages gRPC / Protobuf "sous le capot".

Protobuf n'envoie PAS de JSON : il envoie des octets binaires. Chaque champ est
encodé sous la forme  [tag][valeur]  où  tag = (numéro_de_champ << 3) | wire_type.
Les NOMS des champs ne voyagent jamais sur le réseau, seulement leurs NUMÉROS :
c'est pour cela que le fichier .proto (le contrat) est indispensable des deux côtés.

Ce module fournit :
- decode_wire(data)       : décodeur pédagogique du format binaire (sans le .proto)
- explain_message(msg)    : tableau champ par champ d'un message Protobuf
- GRPCInspectorInterceptor: intercepteur client qui capture chaque appel unaire
"""

import struct
import time
from typing import Any, Dict, List, Tuple

import grpc

WIRE_TYPES = {0: "VARINT", 1: "I64 (8 octets)", 2: "LEN (longueur + octets)", 5: "I32 (4 octets)"}


def _read_varint(data: bytes, pos: int) -> Tuple[int, int]:
    result, shift = 0, 0
    while True:
        if pos >= len(data):
            raise ValueError("varint tronqué")
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def decode_wire(data: bytes) -> List[Dict[str, Any]]:
    """Décode le format binaire Protobuf brut (sans connaître le schéma)."""
    fields = []
    pos = 0
    while pos < len(data):
        start = pos
        tag, pos = _read_varint(data, pos)
        field_number, wire_type = tag >> 3, tag & 0x07
        note = ""
        if wire_type == 0:
            value, pos = _read_varint(data, pos)
            if value >= 1 << 63:
                # Entier négatif en int32/int64 : complément à deux sur 64 bits
                # -> toujours 10 octets ! (le type sint32 utiliserait le zigzag, plus compact)
                value -= 1 << 64
                note = "négatif int32/int64 → 10 octets (sint32 serait plus compact)"
        elif wire_type == 1:
            raw = data[pos:pos + 8]
            pos += 8
            value = struct.unpack("<d", raw)[0] if len(raw) == 8 else raw
        elif wire_type == 2:
            length, pos = _read_varint(data, pos)
            raw = data[pos:pos + length]
            pos += length
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                value = raw.hex(" ")
        elif wire_type == 5:
            raw = data[pos:pos + 4]
            pos += 4
            value = struct.unpack("<f", raw)[0] if len(raw) == 4 else raw
        else:
            raise ValueError(f"wire_type inconnu {wire_type} à l'offset {start}")
        fields.append({
            "field_number": field_number,
            "wire_type": WIRE_TYPES.get(wire_type, str(wire_type)),
            "bytes": data[start:pos].hex(" "),
            "value": value,
            "note": note,
        })
    return fields


def explain_message(message: Any) -> str:
    """Tableau lisible : nom du champ (connu grâce au .proto) ↔ octets réellement envoyés."""
    data = message.SerializeToString()
    by_number = {f.number: f.name for f in message.DESCRIPTOR.fields}
    lines = [
        f"Message {message.DESCRIPTOR.full_name} → {len(data)} octets binaires",
        f"  octets bruts : {data.hex(' ') or '(vide : tous les champs ont leur valeur par défaut)'}",
    ]
    for f in decode_wire(data):
        name = by_number.get(f["field_number"], "?? (inconnu du schéma)")
        lines.append(
            f"  champ n°{f['field_number']:<2} ({name:<18}) {f['wire_type']:<24} "
            f"octets=[{f['bytes']}]  valeur={f['value']!r}"
            + (f"  ⚠ {f['note']}" if f.get("note") else "")
        )
    return "\n".join(lines)


class _CallRecord(dict):
    pass


class GRPCInspectorInterceptor(grpc.UnaryUnaryClientInterceptor):
    """Intercepteur client gRPC : enregistre requête, réponse, tailles et durée de chaque appel."""

    def __init__(self):
        self.calls: List[_CallRecord] = []

    def intercept_unary_unary(self, continuation, client_call_details, request):
        t0 = time.perf_counter()
        outcome = continuation(client_call_details, request)
        record = _CallRecord(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            request=request,
            request_bytes=request.SerializeToString(),
        )
        try:
            response = outcome.result()
            record["response"] = response
            record["response_bytes"] = response.SerializeToString()
            record["status"] = "OK"
        except grpc.RpcError as err:
            record["status"] = f"{err.code().name}: {err.details()}"
        record["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        self.calls.append(record)
        return outcome

    @staticmethod
    def format_call(record: Dict[str, Any]) -> str:
        req_len = len(record["request_bytes"])
        lines = [
            f"Méthode HTTP/2 appelée : POST {record['method']}",
            "  (le chemin vient du .proto : /<package>.<Service>/<Rpc>)",
            f"Trame gRPC envoyée : 1 octet (compression=0) + 4 octets (longueur={req_len}) + {req_len} octets Protobuf",
            explain_message(record["request"]),
        ]
        if "response" in record:
            lines.append(explain_message(record["response"]))
        lines.append(f"Statut : {record['status']} — durée observée côté client : {record['elapsed_ms']:.3f} ms")
        return "\n".join(lines)
