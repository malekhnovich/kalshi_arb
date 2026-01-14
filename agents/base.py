"""
Base agent class with async lifecycle management, retry logic, and circuit breaker.
"""

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Optional, Callable, TypeVar, Any

from events import EventBus, BaseEvent, EventType, EventHandler
import config

T = TypeVar("T")


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == self.CLOSED

    def record_success(self) -> None:
        """Record a successful call"""
        if self._state == self.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._reset()
        elif self._state == self.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call"""
        self._failure_count += 1
        self._last_failure_time = asyncio.get_event_loop().time()

        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN

    def can_execute(self) -> bool:
        """Check if a call can be executed"""
        if self._state == self.CLOSED:
            return True

        if self._state == self.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = asyncio.get_event_loop().time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    return True
            return False

        # HALF_OPEN: allow limited calls
        return True

    def _reset(self) -> None:
        """Reset to closed state"""
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


async def retry_with_backoff(
    func: Callable[..., Any],
    *args,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    **kwargs,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to call
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Result of the function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                break

            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            # Add jitter (0-50% of delay)
            if jitter:
                delay = delay * (0.5 + random.random() * 0.5)

            await asyncio.sleep(delay)

    raise last_exception


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides:
    - Async lifecycle management (start/stop)
    - Event bus integration (publish/subscribe)
    - Health monitoring
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    """

    def __init__(self, name: str, event_bus: EventBus):
        self.name = name
        self.event_bus = event_bus
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._started_at: Optional[float] = None

        # Circuit breaker for this agent
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=config.MAX_RESTART_ATTEMPTS,
            recovery_timeout=60.0,
        )

        # Error tracking
        self._consecutive_errors = 0
        self._total_errors = 0

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the agent's main loop"""
        if self._running:
            return

        self._running = True
        self._started_at = asyncio.get_event_loop().time()
        self._task = asyncio.create_task(self._run_loop())
        print(f"[{self.name}] Started")

    async def stop(self) -> None:
        """Stop the agent gracefully"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print(f"[{self.name}] Stopped")

    async def _run_loop(self) -> None:
        """Internal run loop with error handling and circuit breaker"""
        try:
            await self.on_start()
            while self._running:
                # Check circuit breaker
                if not self._circuit_breaker.can_execute():
                    print(f"[{self.name}] Circuit breaker OPEN - waiting for recovery")
                    await asyncio.sleep(5)
                    continue

                try:
                    await self.run()
                    # Success - reset error tracking
                    self._consecutive_errors = 0
                    self._circuit_breaker.record_success()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._consecutive_errors += 1
                    self._total_errors += 1
                    self._circuit_breaker.record_failure()

                    print(f"[{self.name}] Error in run loop ({self._consecutive_errors} consecutive): {e}")

                    # Exponential backoff based on consecutive errors
                    backoff = min(1 * (2 ** (self._consecutive_errors - 1)), 30)
                    await asyncio.sleep(backoff)
        finally:
            await self.on_stop()

    async def on_start(self) -> None:
        """Called when agent starts. Override for initialization."""
        pass

    async def on_stop(self) -> None:
        """Called when agent stops. Override for cleanup."""
        pass

    @abstractmethod
    async def run(self) -> None:
        """
        Main agent logic. Called repeatedly while agent is running.
        Must be implemented by subclasses.
        """
        pass

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type"""
        self.event_bus.subscribe(event_type, handler)

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to the bus"""
        await self.event_bus.publish(event)

    def get_health(self) -> dict:
        """Return health status of the agent"""
        return {
            "name": self.name,
            "running": self._running,
            "uptime": (
                asyncio.get_event_loop().time() - self._started_at
                if self._started_at else 0
            ),
            "circuit_breaker_state": self._circuit_breaker.state,
            "consecutive_errors": self._consecutive_errors,
            "total_errors": self._total_errors,
        }
