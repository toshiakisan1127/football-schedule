from __future__ import annotations

import live_handler
import split_handler


def test_handler_modules_import() -> None:
    assert callable(split_handler.lambda_handler)
    assert callable(live_handler.lambda_handler)
