from __future__ import annotations

import os
import shlex
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    name: str
    cmd: str
    timeout: int = 900
    env: dict[str, str] = field(default_factory=dict)
    plugin: str | None = None  # repo-relative plugin folder handed to the agent as {plugin_dir}


def load_config(path: Path) -> Config:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not data.get("name") or not data.get("cmd"):
        raise ValueError(f"{path}: config needs 'name' and 'cmd'")
    env = {k: str(v) for k, v in (data.get("env") or {}).items()}
    return Config(name=data["name"], cmd=data["cmd"], timeout=int(data.get("timeout", 900)), env=env,
                  plugin=data.get("plugin"))


def render(template: str, values: dict[str, str], quote: bool = True) -> str:
    """Fill {key} placeholders. Shell commands get quoted values; env values do not."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", shlex.quote(str(value)) if quote else str(value))
    return template


def run_shell(config: Config, values: dict[str, str], cwd: Path) -> tuple[int | None, str, str, bool]:
    """Run config.cmd in cwd; on timeout kill the whole process group."""
    env = {**os.environ, **{k: render(v, values, quote=False) for k, v in config.env.items()}}
    proc = subprocess.Popen(render(config.cmd, values), shell=True, cwd=cwd, env=env, text=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=config.timeout)
        return proc.returncode, out, err, False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # a detached child still holds the pipes open
            out, err = "", ""
        return None, out, err, True
