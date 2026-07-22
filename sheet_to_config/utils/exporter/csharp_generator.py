# -*- coding: utf-8 -*-
"""Optional .proto -> C# generation through the installed protoc compiler."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class CSharpGenerationError(Exception):
    """Raised when optional C# generation cannot be completed."""


def generate_csharp(proto_text: str, output_path: str, proto_name: str) -> bytes:
    """Generate one deterministic C# source file from a rendered .proto.

    The exporter deliberately does not bundle protoc.  Projects can install
    protoc (or set ``PROTOC`` to its executable) independently of the Python
    desktop tool.  The generated source is returned to the Protobuf exporter so
    it can be committed atomically with the .proto/.pb outputs.
    """
    executable = os.environ.get("PROTOC") or shutil.which("protoc")
    if not executable:
        raise CSharpGenerationError(
            "已配置C#输出目录，但找不到protoc；请安装protobuf编译器，"
            "或设置环境变量PROTOC指向protoc可执行文件"
        )

    stem = Path(proto_name).stem
    with tempfile.TemporaryDirectory(prefix="excel2json-protoc-") as work_dir:
        work = Path(work_dir)
        proto_path = work / f"{stem}.proto"
        out_dir = work / "cs"
        out_dir.mkdir()
        proto_path.write_text(proto_text, encoding="utf-8", newline="\n")
        command = [
            executable,
            f"--proto_path={work_dir}",
            f"--csharp_out={out_dir}",
            str(proto_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise CSharpGenerationError(f"启动protoc失败: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "未知错误").strip()
            raise CSharpGenerationError(
                f"protoc生成C#失败（退出码{completed.returncode}）: {detail}"
            )

        candidates = sorted(out_dir.rglob("*.cs"))
        if not candidates:
            raise CSharpGenerationError("protoc未生成任何C#文件")
        preferred = next((item for item in candidates if item.stem == stem), candidates[0])
        payload = preferred.read_bytes()
        if not payload:
            raise CSharpGenerationError("protoc生成的C#文件为空")

    # Validate the destination before the atomic writer creates its parent.
    if not str(output_path).strip():
        raise CSharpGenerationError("C#输出路径不能为空")
    return payload
