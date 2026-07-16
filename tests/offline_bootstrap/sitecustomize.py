"""Install the pytest offline socket policy in Python child processes."""

from __future__ import annotations

import os

from tests.offline_socket_guard import SocketGuard


if os.environ.get("WOLFYSTOCK_TEST_OFFLINE") == "1":
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"

    _WOLFYSTOCK_CHILD_SOCKET_GUARD = SocketGuard()
    _WOLFYSTOCK_CHILD_SOCKET_GUARD.install()
