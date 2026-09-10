from __future__ import annotations

import handler


def test_handler_module_imports() -> None:
    assert callable(handler.lambda_handler)
