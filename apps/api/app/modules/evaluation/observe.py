"""A hook for seeing the prompt that was actually sent. Used by the evaluation runner only."""

from collections.abc import Callable
from contextvars import ContextVar

_observer: ContextVar[Callable[[str], None] | None] = ContextVar("prompt_observer", default=None)


def set_prompt_observer(fn: Callable[[str], None] | None) -> None:
    _observer.set(fn)


def observe_prompt(system: str) -> None:
    fn = _observer.get()
    if fn is not None:
        fn(system)
