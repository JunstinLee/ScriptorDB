"""ApprovalSubmitRequest 的 override_args 结构契约。"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from schemas.approval import ApprovalSubmitRequest


# ---------- ApprovalSubmitRequest 结构 ----------


def test_approval_submit_request_override_args_shape():
    r = ApprovalSubmitRequest(
        request_id="r", approved_map={"c": True},
        override_args={"c": {"action": "select", "target": "Status"}},
    )
    assert r.override_args == {"c": {"action": "select", "target": "Status"}}


def test_approval_submit_request_override_args_defaults_empty():
    r = ApprovalSubmitRequest(request_id="r", approved_map={"c": True})
    assert r.override_args == {}


def test_approval_submit_request_rejects_non_dict_override():
    with pytest.raises(ValidationError):
        ApprovalSubmitRequest(
            request_id="r", approved_map={"c": True},
            override_args=cast(Any, {"c": "not-a-dict"}),
        )

