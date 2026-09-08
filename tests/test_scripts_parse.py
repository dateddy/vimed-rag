"""Mọi file trong `scripts/` phải PARSE được.

Vì sao cần: `pytest` không hề chạm `scripts/`, nên một lỗi cú pháp ở đó **im
lặng hoàn toàn** cho tới lúc chạy tay. 2026-09-08 đã xảy ra thật —
`smoke_pipeline.py` bị heredoc làm hỏng một chuỗi (`SyntaxError: unterminated
string literal`) trong khi 177/177 test vẫn xanh. Kịch bản tệ nhất là phát hiện
điều đó lúc demo trước hội đồng.

Chỉ `ast.parse`, **KHÔNG import**: import script là chạy `sys.path.insert`, nạp
config, và với vài script là mở kết nối — vi phạm ràng buộc #2. Parse đủ bắt
loại lỗi mà pytest đang bỏ sót, và rẻ như không.

⚠️ Đây KHÔNG phải test hành vi. Script vẫn có thể parse sạch mà chạy sai; chốt
chặn này chỉ chặn đúng một loại hỏng.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parent.parent / "scripts").glob("*.py"))


def test_there_are_scripts_to_check():
    """Nếu glob hỏng thì parametrize rỗng và test bên dưới xanh một cách vô nghĩa."""
    assert len(SCRIPTS) >= 10


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_script_parses(path: Path):
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - chỉ chạy khi thật sự hỏng
        pytest.fail(f"{path.name} lỗi cú pháp dòng {exc.lineno}: {exc.msg}")
