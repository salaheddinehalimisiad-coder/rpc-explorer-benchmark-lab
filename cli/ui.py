"""Petits utilitaires d'affichage console (sans dépendance externe)."""

import os
import sys

# Sous Windows, forcer l'UTF-8 pour afficher correctement accents et cadres.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # flux non reconfigurable (ex: capturé par pytest)
        pass
if os.name == "nt":
    os.system("")  # active les séquences ANSI dans la console Windows

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t): return _c("1", t)
def green(t): return _c("32", t)
def red(t): return _c("31", t)
def yellow(t): return _c("33", t)
def cyan(t): return _c("36", t)
def dim(t): return _c("2", t)


def title(text: str) -> None:
    line = "═" * max(60, len(text) + 4)
    print()
    print(cyan(line))
    print(cyan(f"  {text}"))
    print(cyan(line))


def section(text: str) -> None:
    print()
    print(bold(f"── {text} " + "─" * max(3, 56 - len(text))))


def table(headers, rows) -> str:
    """Retourne un tableau texte aligné."""
    cols = [list(map(str, col)) for col in zip(headers, *rows)] if rows else [[h] for h in headers]
    widths = [max(len(x) for x in col) for col in cols]
    sep = "─┼─".join("─" * w for w in widths)
    out = [" │ ".join(str(h).ljust(w) for h, w in zip(headers, widths)), sep]
    for r in rows:
        out.append(" │ ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    return "\n".join(out)


def explain(text: str) -> None:
    """Encadré pédagogique."""
    for line in text.strip("\n").splitlines():
        print(yellow("  💡 " + line) if line.strip() else "")
