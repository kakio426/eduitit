import time
import logging

logger = logging.getLogger(__name__)


class SimpleCircuitBreaker:
    """
    AI API 연속 실패 시 자동 차단하여 worker를 보호하는 간단한 Circuit Breaker.
    연속 failure_threshold회 실패 시 reset_timeout초간 요청을 즉시 차단.
    """

    def __init__(self, failure_threshold=5, reset_timeout=30):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.threshold:
            self.is_open = True
            logger.warning(
                f"[CircuitBreaker] OPEN - {self.failures} consecutive failures. "
                f"Blocking requests for {self.reset_timeout}s."
            )

    def record_success(self):
        if self.is_open:
            logger.info("[CircuitBreaker] CLOSED - recovered after success.")
        self.failures = 0
        self.is_open = False

    def can_execute(self):
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.reset_timeout:
            # Half-open: allow one request through to test recovery
            logger.info("[CircuitBreaker] HALF-OPEN - allowing test request.")
            self.is_open = False
            return True
        return False


# Global instance for AI API calls
ai_circuit_breaker = SimpleCircuitBreaker(failure_threshold=5, reset_timeout=30)
