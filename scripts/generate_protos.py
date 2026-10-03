#!/usr/bin/env python3
"""
Régénère le code Python à partir des contrats .proto (à lancer depuis la racine du projet).

    python scripts/generate_protos.py

- protos/inventory.proto                        -> protos/inventory_pb2.py, protos/inventory_pb2_grpc.py
- contract_evolution/protos_v2/inventory.proto  -> contract_evolution/generated_v2/*.py

Les fichiers *_pb2*.py sont GÉNÉRÉS : ne pas les modifier à la main.
NB : le code généré exige une version de `protobuf`/`grpcio` au moins égale à celle
de `grpcio-tools` utilisée pour le générer (voir requirements.txt).
"""

import os
import re
import sys

from grpc_tools import protoc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args):
    code = protoc.main(["grpc_tools.protoc"] + args)
    if code != 0:
        sys.exit(f"protoc a échoué ({code}) : {' '.join(args)}")


def main():
    os.chdir(ROOT)
    # Contrat v1 : chemin d'import "protos/..." -> imports `from protos import inventory_pb2`
    run(["-I.", "--python_out=.", "--grpc_python_out=.", "protos/inventory.proto"])
    print("✓ protos/inventory_pb2.py, protos/inventory_pb2_grpc.py")

    # Contrat v2 (démo d'évolution) : même package Protobuf, généré dans un autre dossier
    out = "contract_evolution/generated_v2"
    run(["-Icontract_evolution/protos_v2", f"--python_out={out}", f"--grpc_python_out={out}",
         "contract_evolution/protos_v2/inventory.proto"])
    grpc_file = os.path.join(out, "inventory_pb2_grpc.py")
    with open(grpc_file, encoding="utf-8") as f:
        src = f.read()
    src = re.sub(r"^import inventory_pb2 as inventory__pb2",
                 "from contract_evolution.generated_v2 import inventory_pb2 as inventory__pb2",
                 src, flags=re.M)
    with open(grpc_file, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"✓ {out}/inventory_pb2.py, {out}/inventory_pb2_grpc.py")


if __name__ == "__main__":
    main()
