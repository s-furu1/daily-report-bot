from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class DiskUsage:
    total_bytes: int
    used_bytes: int
    free_bytes: int


@dataclass(frozen=True)
class MemoryUsage:
    total_bytes: int
    available_bytes: int


@dataclass(frozen=True)
class LoadAverage:
    one: float
    five: float
    fifteen: float


@dataclass(frozen=True)
class ServerMetrics:
    disk: DiskUsage | None
    memory: MemoryUsage | None
    load_average: LoadAverage | None


def collect_server_metrics(root: str = "/") -> ServerMetrics:
    return ServerMetrics(
        disk=read_disk_usage(root),
        memory=read_memory_usage(),
        load_average=read_load_average(),
    )


def read_disk_usage(path: str = "/") -> DiskUsage | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return DiskUsage(int(usage.total), int(usage.used), int(usage.free))


def read_load_average() -> LoadAverage | None:
    try:
        one, five, fifteen = os.getloadavg()
    except (OSError, AttributeError):
        return None
    return LoadAverage(float(one), float(five), float(fifteen))


def read_memory_usage() -> MemoryUsage | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            data: dict[str, int] = {}
            for line in f:
                key, _, rest = line.partition(":")
                if not rest:
                    continue
                parts = rest.strip().split()
                if not parts:
                    continue
                try:
                    value_kb = int(parts[0])
                except ValueError:
                    continue
                data[key] = value_kb * 1024
    except OSError:
        return None
    if "MemTotal" not in data:
        return None
    available = data.get("MemAvailable", data.get("MemFree", 0))
    return MemoryUsage(total_bytes=data["MemTotal"], available_bytes=available)


def format_server_metrics(metrics: ServerMetrics) -> str:
    lines: list[str] = []
    if metrics.disk is None:
        lines.append("  disk: unavailable")
    else:
        lines.append(
            f"  disk: used {_to_gib(metrics.disk.used_bytes)} / "
            f"{_to_gib(metrics.disk.total_bytes)} GiB "
            f"(free {_to_gib(metrics.disk.free_bytes)} GiB)"
        )
    if metrics.memory is None:
        lines.append("  memory: unavailable")
    else:
        lines.append(
            f"  memory: available {_to_gib(metrics.memory.available_bytes)} / "
            f"{_to_gib(metrics.memory.total_bytes)} GiB"
        )
    if metrics.load_average is None:
        lines.append("  load average: unavailable")
    else:
        lines.append(
            f"  load average: {metrics.load_average.one:.2f} "
            f"{metrics.load_average.five:.2f} "
            f"{metrics.load_average.fifteen:.2f}"
        )
    return "\n".join(lines)


def _to_gib(value_bytes: int) -> str:
    return f"{value_bytes / (1024 ** 3):.1f}"
