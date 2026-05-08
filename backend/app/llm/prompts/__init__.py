"""STE-20：Prompt 模板渲染（占位）。

模板文件位于本目录下的 `<name>.j2`，用 jinja2.FileSystemLoader 加载。
实现见 commit 2；本提交先暴露符号让测试 import 不爆。
"""

from __future__ import annotations

from typing import Any


def render_prompt(name: str, **context: Any) -> str:
    """渲染指定名称的 jinja 模板。

    Args:
        name: 模板名（不带 `.j2` 后缀，如 `"sql_gen"`）。
        **context: 注入到模板的变量。

    Returns:
        渲染后的 prompt 字符串。
    """
    raise NotImplementedError


__all__ = ["render_prompt"]
