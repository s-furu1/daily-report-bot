from __future__ import annotations

from app.metrics.server import (
    DiskUsage,
    LoadAverage,
    MemoryUsage,
    ServerMetrics,
    collect_server_metrics,
    format_server_metrics,
    read_disk_usage,
)


def test_collect_server_metrics_returns_object(tmp_path):
    metrics = collect_server_metrics(str(tmp_path))
    assert isinstance(metrics, ServerMetrics)
    assert metrics.disk is None or isinstance(metrics.disk, DiskUsage)
    assert metrics.memory is None or isinstance(metrics.memory, MemoryUsage)
    assert metrics.load_average is None or isinstance(metrics.load_average, LoadAverage)


def test_disk_usage_for_temp_dir(tmp_path):
    usage = read_disk_usage(str(tmp_path))
    assert usage is not None
    assert usage.total_bytes > 0
    assert usage.free_bytes >= 0


def test_format_server_metrics_marks_unavailable_for_none_fields():
    metrics = ServerMetrics(disk=None, memory=None, load_average=None)
    text = format_server_metrics(metrics)
    assert "disk: unavailable" in text
    assert "memory: unavailable" in text
    assert "load average: unavailable" in text


def test_format_server_metrics_renders_values():
    metrics = ServerMetrics(
        disk=DiskUsage(total_bytes=10 * 1024**3, used_bytes=4 * 1024**3, free_bytes=6 * 1024**3),
        memory=MemoryUsage(total_bytes=8 * 1024**3, available_bytes=3 * 1024**3),
        load_average=LoadAverage(0.5, 0.7, 1.2),
    )
    text = format_server_metrics(metrics)
    assert "disk: used 4.0 / 10.0 GiB" in text
    assert "memory: available 3.0 / 8.0 GiB" in text
    assert "load average: 0.50 0.70 1.20" in text
