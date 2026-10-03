"""
Tests de vérification de la structure du projet (Phase 01 - Fondation)

Vérifie l'existence des répertoires, des fichiers de configuration,
de la documentation officielle et des fichiers fondamentaux.
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestProjectStructure(unittest.TestCase):
    """Vérifie la conformité de l'arborescence et des fichiers socles."""

    def test_required_directories_exist(self):
        """Vérifie la présence de tous les répertoires d'architecture."""
        required_dirs = [
            "rpc_core",
            "protos",
            "grpc_impl",
            "rest",
            "business",
            "benchmark",
            "benchmark/adapters",
            "failure_simulator",
            "under_the_hood",
            "cli",
            "tests",
            "docs",
        ]
        for rel_dir in required_dirs:
            dir_path = PROJECT_ROOT / rel_dir
            self.assertTrue(
                dir_path.is_dir(),
                f"Le répertoire obligatoire '{rel_dir}' est introuvable."
            )

    def test_essential_files_exist(self):
        """Vérifie la présence des fichiers de configuration et de documentation."""
        essential_files = [
            "README.md",
            "requirements.txt",
            "pyproject.toml",
            ".gitignore",
            "CLAUDE.md",
            "PROJECT_AUDIT.md",
            "main.py",
            "docs/architecture.md",
            "docs/cahier_des_charges_officiel.md",
        ]
        for rel_file in essential_files:
            file_path = PROJECT_ROOT / rel_file
            self.assertTrue(
                file_path.is_file(),
                f"Le fichier obligatoire '{rel_file}' est introuvable."
            )

    def test_protobuf_contract_exists(self):
        """Vérifie la présence du contrat d'interface Protobuf IDL."""
        proto_file = PROJECT_ROOT / "protos" / "inventory.proto"
        self.assertTrue(proto_file.is_file(), "Le fichier protos/inventory.proto est manquant.")
        content = proto_file.read_text(encoding="utf-8")
        self.assertIn("service InventoryRPCService", content)
        self.assertIn("CalculateFactorial", content)
        self.assertIn("GetProductDetails", content)
        self.assertIn("UpdateStock", content)
        self.assertIn("StreamAnalytics", content)

    def test_package_init_files_exist(self):
        """Vérifie que tous les sous-dossiers de code sont des packages Python valides."""
        packages = [
            "rpc_core",
            "business",
            "grpc_impl",
            "rest",
            "benchmark",
            "benchmark/adapters",
            "failure_simulator",
            "under_the_hood",
            "cli",
            "tests",
        ]
        for pkg in packages:
            init_file = PROJECT_ROOT / pkg / "__init__.py"
            self.assertTrue(
                init_file.is_file(),
                f"Fichier __init__.py manquant pour le package '{pkg}'."
            )


if __name__ == "__main__":
    unittest.main()
