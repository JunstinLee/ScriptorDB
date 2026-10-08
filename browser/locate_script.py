"""定位脚本的 Python 侧入口（JS 实体在 browser/scripts/*.js）。

``browser.runtime.locate_elements`` 第一段：一次 evaluate 完成布局初筛 + 信号抽取。
契约：JS 只产出原始信号（selector / enabled / receivesEvents / inViewport /
inActive / rect / visibility …），"可操作性三态"一律由 Python 侧的
``_confirm_actionable`` 判定，避免字段语义在两层之间漂移。
"""

from __future__ import annotations

from browser import js_assets

# 元素稳定签名（阶段 1 铸造 / 阶段 4 执行期复算共用同一份源码，避免两层语义漂移）。
# 只读属性派生信号：tag / role / aria-label / 归一化 text；刻意排除 value 与 rect ——
# value 随输入变化、rect 随布局变化，都会把「未变的元素」误判成 stale。
ELEMENT_SIGNATURE_JS = js_assets.load("element_signature")

# 定位主脚本；模板内的 __ELEMENT_SIGNATURE__ 占位由签名脚本填充，
# 使两处引用同一份签名源码。
LOCATE_ELEMENTS_JS = js_assets.load("locate_elements").replace(
    "__ELEMENT_SIGNATURE__", ELEMENT_SIGNATURE_JS
)
