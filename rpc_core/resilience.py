"""
Résilience côté client : retry explicite avec backoff exponentiel.

Un appel distant peut échouer pour des raisons qui n'existent pas en local
(timeout, serveur redémarré, réseau coupé). Réessayer est souvent utile…
mais DANGEREUX pour une opération non idempotente (ex: update_stock) :
si la première tentative a été exécutée mais que la réponse s'est perdue,
le retry l'exécute une deuxième fois. Voir lab/failures.py (scénario 5).

Ce mécanisme n'est JAMAIS activé automatiquement : l'appelant le choisit.
"""

import time
from typing import Any, Callable, Optional, Tuple, Type

DEFAULT_RETRYABLE: Tuple[Type[BaseException], ...] = (TimeoutError, ConnectionError)


class RetryExhaustedError(Exception):
    """Toutes les tentatives ont échoué ; `last_error` contient la dernière erreur."""

    def __init__(self, attempts: int, last_error: BaseException):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Échec après {attempts} tentative(s) : {type(last_error).__name__}: {last_error}")


def call_with_retry(
    fn: Callable[[], Any],
    retries: int = 3,
    base_delay: float = 0.1,
    backoff: float = 2.0,
    retry_on: Tuple[Type[BaseException], ...] = DEFAULT_RETRYABLE,
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> Any:
    """
    Exécute `fn()` ; en cas d'erreur réseau "retryable", réessaie jusqu'à `retries` fois
    supplémentaires en attendant base_delay, base_delay*backoff, base_delay*backoff², …

    Les erreurs applicatives (ex: RPCError INVALID_ARGS) ne sont PAS réessayées :
    réessayer une requête invalide donnerait toujours la même erreur.
    """
    if retries < 0:
        raise ValueError("retries doit être >= 0")
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except retry_on as err:
            if attempt > retries:
                raise RetryExhaustedError(attempt, err) from err
            delay = base_delay * (backoff ** (attempt - 1))
            if on_retry is not None:
                on_retry(attempt, err, delay)
            time.sleep(delay)
