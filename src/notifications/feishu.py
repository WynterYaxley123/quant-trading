"""飞书通知接口骨架。

当前阶段：仅骨架，不发真实请求。
默认 dry_run=True，未配置凭证时返回未配置状态，不抛异常、不阻塞主流程。

真实凭证只允许放项目根目录 .env（已被 .gitignore 忽略）：
    FEISHU_WEBHOOK=
    FEISHU_APP_ID=
    FEISHU_APP_SECRET=
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationResult:
    """通知发送结果。

    Attributes:
        sent: 是否实际发出请求。dry_run 或未配置时为 False。
        status: 状态标识，取值 ok / dry_run / not_configured / error。
        message: 人类可读的说明。
        detail: 附加信息（如将要发送的 payload）。
    """

    sent: bool
    status: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


def _load_config() -> dict[str, str]:
    """从环境变量读取飞书配置。不读取 .env 文件本身，由上层注入。"""
    return {
        "webhook": os.environ.get("FEISHU_WEBHOOK", "").strip(),
        "app_id": os.environ.get("FEISHU_APP_ID", "").strip(),
        "app_secret": os.environ.get("FEISHU_APP_SECRET", "").strip(),
    }


def is_configured() -> bool:
    """判断是否已配置飞书凭证。"""
    cfg = _load_config()
    return bool(cfg["webhook"] or (cfg["app_id"] and cfg["app_secret"]))


def send_report(payload: dict[str, Any], dry_run: bool = True) -> NotificationResult:
    """发送研究报告通知。

    Args:
        payload: 消息载荷，建议由 build_research_payload 构造。
        dry_run: 为 True 时只返回将发送的内容，不发真实请求。

    Returns:
        NotificationResult
    """
    if dry_run:
        return NotificationResult(
            sent=False,
            status="dry_run",
            message="dry-run 模式：未发送真实请求",
            detail={"payload": payload},
        )

    if not is_configured():
        return NotificationResult(
            sent=False,
            status="not_configured",
            message="飞书凭证未配置，跳过发送（不阻塞主流程）",
            detail={"payload": payload},
        )

    # 真实发送逻辑留待实现（需用户明确指令）
    return NotificationResult(
        sent=False,
        status="error",
        message="发送功能尚未实现（当前阶段仅骨架）",
        detail={"payload": payload},
    )


def send_alert(
    task: str,
    stage: str,
    error: str,
    log_path: str = "",
    dry_run: bool = True,
) -> NotificationResult:
    """发送异常通知。"""
    payload = build_alert_payload(task=task, stage=stage, error=error, log_path=log_path)
    return send_report(payload, dry_run=dry_run)


def build_research_payload(
    strategy: str,
    version: str,
    status: str,
    hikyuu: dict[str, Any] | None = None,
    rqalpha: dict[str, Any] | None = None,
    validation: str = "",
    report: str = "",
    git_commit: str = "",
) -> dict[str, Any]:
    """构造【Quant Research Completed】标准消息载荷。

    未提供的指标保持 None，禁止用 0 或估计值填充。
    """
    return {
        "title": "Quant Research Completed",
        "strategy": strategy,
        "version": version,
        "status": status,
        "hikyuu": hikyuu or {},
        "rqalpha": rqalpha or {},
        "validation": validation or "未验证",
        "report": report,
        "git_commit": git_commit,
    }


def build_alert_payload(
    task: str,
    stage: str,
    error: str,
    log_path: str = "",
) -> dict[str, Any]:
    """构造【Quant Task Failed】标准告警载荷。"""
    return {
        "title": "Quant Task Failed",
        "task": task,
        "stage": stage,
        "error": error,
        "log": log_path,
    }


def render_text(payload: dict[str, Any]) -> str:
    """把载荷渲染为纯文本消息（飞书消息体用）。"""
    lines: list[str] = []
    title = payload.get("title", "Quant Notification")
    lines.append(f"【{title}】")
    lines.append("")

    if title == "Quant Research Completed":
        lines.append(f"Strategy: {payload.get('strategy', '')}")
        lines.append(f"Version: {payload.get('version', '')}")
        lines.append(f"Status: {payload.get('status', '')}")
        lines.append("")

        for fw_key, fw_label in (("hikyuu", "Hikyuu"), ("rqalpha", "RQAlpha")):
            fw = payload.get(fw_key) or {}
            lines.append(f"{fw_label}:")
            for label, key in (
                ("Annual Return", "annual_return"),
                ("Max Drawdown", "max_drawdown"),
                ("Sharpe", "sharpe"),
            ):
                value = fw.get(key)
                lines.append(f"  {label}: {'' if value is None else value}")
            lines.append("")

        lines.append(f"Validation: {payload.get('validation', '')}")
        lines.append(f"Report: {payload.get('report', '')}")
        lines.append(f"Git Commit: {payload.get('git_commit', '')}")

    else:  # 告警
        lines.append(f"Task: {payload.get('task', '')}")
        lines.append(f"Strategy: {payload.get('strategy', '')}")
        lines.append(f"Stage: {payload.get('stage', '')}")
        lines.append(f"Error: {payload.get('error', '')}")
        lines.append(f"Log: {payload.get('log', '')}")

    return "\n".join(lines)


def to_json(payload: dict[str, Any]) -> str:
    """序列化为 JSON 字符串。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 自检：dry-run，不发送任何真实请求
    demo = build_research_payload(
        strategy="demo",
        version="v0.0.0",
        status="未开始",
    )
    print(render_text(demo))
    print()
    print("configured:", is_configured())
