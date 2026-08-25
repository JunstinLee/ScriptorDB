from __future__ import annotations

"""审批域包：编排器、策略、存储、可恢复流、暂停状态、接管控制器。

原 runtime/approval_orchestrator.py 与 runtime/approval_policy.py 已迁移
至此，旧路径保留为转发薄壳。
"""

from approval_part.orchestrator import ApprovalOrchestrator

__all__ = ["ApprovalOrchestrator"]
