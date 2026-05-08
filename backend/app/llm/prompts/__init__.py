"""STE-20：Prompt 模板渲染。

模板文件位于本目录下的 `<name>.j2`，用 jinja2.FileSystemLoader 加载。

设计要点：
- `StrictUndefined`：模板里引用了未传入的变量直接抛 `UndefinedError`，
  避免静默漏传上下文导致 LLM 收到「{{ tenant_id }}」这种字面量。
- `autoescape=False`：prompt 不是 HTML，不要把 `<` `>` 转义成 `&lt;`。
- `trim_blocks` + `lstrip_blocks`：让 jinja 控制语句不在输出里留空行。

模块级 `Environment` 单例：避免每次调用都重新扫描磁盘 / 编译模板。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(default=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(name: str, **context: Any) -> str:
    """渲染指定名称的 jinja 模板。

    Args:
        name: 模板名（不带 `.j2` 后缀，如 `"sql_gen"`）。
        **context: 注入到模板的变量。模板里所有引用都必须在此提供，
            否则抛 `jinja2.UndefinedError`。

    Raises:
        jinja2.TemplateNotFound: 模板不存在。
        jinja2.UndefinedError: 模板引用了未提供的变量。
    """
    template = _env.get_template(f"{name}.j2")
    return template.render(**context)


__all__ = ["render_prompt"]
