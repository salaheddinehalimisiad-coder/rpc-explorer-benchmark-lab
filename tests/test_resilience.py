"""Tests du retry explicite (rpc_core.resilience)."""

import unittest

from rpc_core import RPCError
from rpc_core.resilience import RetryExhaustedError, call_with_retry


class TestCallWithRetry(unittest.TestCase):
    def test_success_first_try(self):
        self.assertEqual(call_with_retry(lambda: 42, base_delay=0), 42)

    def test_succeeds_after_transient_failures(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("down")
            return "ok"

        seen = []
        self.assertEqual(call_with_retry(flaky, retries=3, base_delay=0,
                                         on_retry=lambda a, e, d: seen.append(a)), "ok")
        self.assertEqual(len(attempts), 3)
        self.assertEqual(seen, [1, 2])

    def test_exhausted(self):
        def always_timeout():
            raise TimeoutError("slow")

        with self.assertRaises(RetryExhaustedError) as ctx:
            call_with_retry(always_timeout, retries=2, base_delay=0)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertIsInstance(ctx.exception.last_error, TimeoutError)

    def test_application_errors_are_not_retried(self):
        calls = []

        def bad_args():
            calls.append(1)
            raise RPCError("INVALID_ARGS", "nope")

        with self.assertRaises(RPCError):
            call_with_retry(bad_args, retries=5, base_delay=0)
        self.assertEqual(len(calls), 1)

    def test_backoff_delays(self):
        delays = []

        def fail():
            raise TimeoutError()

        with self.assertRaises(RetryExhaustedError):
            call_with_retry(fail, retries=3, base_delay=0.001, backoff=2,
                            on_retry=lambda a, e, d: delays.append(d))
        self.assertEqual(delays, [0.001, 0.002, 0.004])

    def test_negative_retries_rejected(self):
        with self.assertRaises(ValueError):
            call_with_retry(lambda: 1, retries=-1)


if __name__ == "__main__":
    unittest.main()
