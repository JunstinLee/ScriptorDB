"""工具层持有的元素引用（ref）注册表。

`browser_find` 对可用元素铸造一个短生命周期引用，模型只看到 ``ref_<hex>``
字符串；真实身份（页面对象 / 铸造时 URL / 定位器 / 稳定签名 / run 作用域）留在
本模块，不暴露给模型。动作工具在执行期用 :func:`resolve_ref` 取回记录，再校验
URL 与签名，命中才操作 —— 这样模型侧不再需要搬运结构坐标。

身份约定：``run_id`` 取 ``deps.run_id``（一次逻辑 run 恒定），``page_url`` 取铸造
时的 ``page.url``。失效由工具层的少数挂点控制（显式导航 / 页面重置），不经模型。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Page


@dataclass
class RefRecord:
    """一次 ref 铸造所需的全部信息。"""

    ref: str
    page: "Page"
    page_url: str
    locator: str
    signature: str
    run_id: str
    created_at: float
    locator_kind: str = "path"


_registry: dict[str, RefRecord] = {}


def mint_ref(
    page: "Page",
    locator: str,
    signature: str,
    run_id: str,
    *,
    locator_kind: str = "path",
) -> str:
    """铸造一个 ref，并在同一入口钉住铸造时的 ``page.url``。"""
    ref = "ref_" + secrets.token_hex(4)
    _registry[ref] = RefRecord(
        ref=ref,
        page=page,
        page_url=getattr(page, "url", "") or "",
        locator=locator,
        signature=signature,
        run_id=run_id,
        created_at=time(),
        locator_kind=locator_kind,
    )
    return ref


def resolve_ref(ref: str) -> RefRecord | None:
    """按 ref 取回记录；不存在返回 ``None``。"""
    return _registry.get(ref)


def invalidate_ref(ref: str) -> None:
    """失效指定的单条 ref；不存在则无操作。"""
    _registry.pop(ref, None)


def invalidate_page(page: Any) -> None:
    """失效指定 page 上的全部 ref（显式导航后调用）。"""
    if page is None:
        return
    for ref, record in list(_registry.items()):
        if record.page is page:
            _registry.pop(ref, None)


def invalidate_all() -> None:
    """失效全部 ref（页面重置 / 浏览器关闭时调用）。"""
    _registry.clear()
