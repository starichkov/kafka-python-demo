import logging


def test_get_logger_is_idempotent_and_does_not_duplicate_handlers():
    from logger import get_logger

    # First call should attach one handler
    lg = get_logger("demo")
    n1 = len(lg.handlers)
    assert n1 == 1
    assert isinstance(lg.handlers[0], logging.StreamHandler)
    assert lg.propagate is False

    # Second call should not add another handler
    lg2 = get_logger("demo")
    assert lg2 is lg
    n2 = len(lg2.handlers)
    assert n2 == 1, "Logger should not accumulate duplicate handlers"
