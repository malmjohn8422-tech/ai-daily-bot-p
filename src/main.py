#!/usr/bin/env python3
"""AI Daily Bot - 入口"""

import argparse
import os
import sys
import re
import yaml
from dotenv import load_dotenv

from .collectors import REGISTRY as COLLECTOR_REGISTRY
from .processors import REGISTRY as PROCESSOR_REGISTRY
from .notifiers import REGISTRY as NOTIFIER_REGISTRY


def _ensure_utf8_output():
    """Avoid UnicodeEncodeError when Windows consoles default to a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_ensure_utf8_output()


def load_config(path: str) -> dict:
    """加载 yaml 配置，并解析其中的 ${ENV_VAR} 占位符"""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    def replace_env(match):
        var = match.group(1)
        return os.environ.get(var, match.group(0))

    raw = re.sub(r'\$\{(\w+)\}', replace_env, raw)
    return yaml.safe_load(raw)


def _find_unresolved(obj, path: str) -> list[str]:
    """递归检查配置中是否有未解析的 ${VAR} 占位符"""
    errs = []
    if isinstance(obj, str):
        if "${" in obj:
            errs.append(f"{path} 中环境变量未设置: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            errs.extend(_find_unresolved(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs.extend(_find_unresolved(v, f"{path}[{i}]"))
    return errs


def validate_config(cfg: dict):
    """校验配置完整性，有问题则打印错误并退出"""
    errors = []

    if not isinstance(cfg, dict):
        errors.append("配置文件必须是 YAML 对象")
        cfg = {}

    # 检查必要配置中的未解析环境变量；未使用的通知器允许保留占位符。
    required_cfg = {k: v for k, v in cfg.items() if k != "notifiers"}
    errors.extend(_find_unresolved(required_cfg, "config"))

    ai_cfg = cfg.get("ai")
    if "ai" not in cfg:
        errors.append("配置缺少 ai 字段")
    elif not isinstance(ai_cfg, dict):
        errors.append("ai 配置必须是对象")
    elif not ai_cfg.get("api_base"):
        errors.append("ai 配置缺少 api_base")
    elif not ai_cfg.get("model"):
        errors.append("ai 配置缺少 model")

    notifier_configs = cfg.get("notifiers", {}) or {}
    if not isinstance(notifier_configs, dict):
        errors.append("notifiers 配置必须是对象")
        notifier_configs = {}

    tasks = cfg.get("tasks", []) or []
    if not isinstance(tasks, list):
        errors.append("tasks 配置必须是列表")
        tasks = []

    if not tasks:
        errors.append("配置中没有任务")

    for i, task in enumerate(tasks):
        prefix = f"  tasks[{i}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} 必须是对象")
            continue

        name = task.get("name")
        if not name:
            errors.append(f"{prefix} 缺少 name")

        if not task.get("schedule"):
            errors.append(f"{prefix} [{name}] 缺少 schedule")

        sources = task.get("sources")
        collector = task.get("collector")
        if sources:
            if not isinstance(sources, list):
                errors.append(f"{prefix} [{name}] sources 必须是列表")
            elif not sources:
                errors.append(f"{prefix} [{name}] sources 不能为空")
            else:
                for j, source in enumerate(sources):
                    source_prefix = f"{prefix}.sources[{j}]"
                    if not isinstance(source, dict):
                        errors.append(f"{source_prefix} 必须是对象")
                        continue
                    source_collector = source.get("collector")
                    if not source_collector:
                        errors.append(f"{source_prefix} 缺少 collector")
                    elif source_collector not in COLLECTOR_REGISTRY:
                        errors.append(
                            f"{source_prefix} 未知采集器 '{source_collector}'，可选: {list(COLLECTOR_REGISTRY.keys())}"
                        )
                    source_params = source.get("params", {})
                    if source_params is not None and not isinstance(source_params, dict):
                        errors.append(f"{source_prefix}.params 必须是对象")
        elif not collector:
            errors.append(f"{prefix} [{name}] 缺少 collector 或 sources")
        elif collector not in COLLECTOR_REGISTRY:
            errors.append(f"{prefix} [{name}] 未知采集器 '{collector}'，可选: {list(COLLECTOR_REGISTRY.keys())}")

        processor = task.get("processor")
        if not processor:
            errors.append(f"{prefix} [{name}] 缺少 processor")
        elif processor not in PROCESSOR_REGISTRY:
            errors.append(f"{prefix} [{name}] 未知处理器 '{processor}'，可选: {list(PROCESSOR_REGISTRY.keys())}")
        elif processor == "weekly":
            params = task.get("params") or {}
            if not isinstance(params, dict) or not params.get("task_name"):
                errors.append(f"{prefix} [{name}] weekly 处理器需要 params.task_name 指向每日趋势任务")

        notifier_name = task.get("notifier")
        if not notifier_name:
            errors.append(f"{prefix} [{name}] 缺少 notifier")
        elif notifier_name not in NOTIFIER_REGISTRY:
            errors.append(f"{prefix} [{name}] 未知通知器 '{notifier_name}'，可选: {list(NOTIFIER_REGISTRY.keys())}")
        elif notifier_name not in notifier_configs:
            errors.append(f"{prefix} [{name}] 未找到通知器 '{notifier_name}' 的配置")
        else:
            notifier_cfg = notifier_configs.get(notifier_name) or {}
            errors.extend(_find_unresolved(notifier_cfg, f"config.notifiers.{notifier_name}"))

        if notifier_name == "telegram" and notifier_name in notifier_configs:
            telegram_cfg = notifier_configs.get("telegram") or {}
            if not telegram_cfg.get("bot_token"):
                errors.append(f"{prefix} [{name}] telegram 配置缺少 bot_token")
            if not telegram_cfg.get("chat_id"):
                errors.append(f"{prefix} [{name}] telegram 配置缺少 chat_id")
        elif notifier_name == "email" and notifier_name in notifier_configs:
            email_cfg = notifier_configs.get("email") or {}
            if not email_cfg.get("smtp_server"):
                errors.append(f"{prefix} [{name}] email 配置缺少 smtp_server")
            try:
                smtp_port = int(email_cfg.get("smtp_port", 0))
                if smtp_port <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{prefix} [{name}] email 配置 smtp_port 必须是正整数")
            if not email_cfg.get("username"):
                errors.append(f"{prefix} [{name}] email 配置缺少 username")
            if not email_cfg.get("password"):
                errors.append(f"{prefix} [{name}] email 配置缺少 password")
            if not email_cfg.get("recipient"):
                errors.append(f"{prefix} [{name}] email 配置缺少 recipient")

        # 校验 cron 表达式（使用东八区）
        if task.get("schedule"):
            try:
                from zoneinfo import ZoneInfo
                from apscheduler.triggers.cron import CronTrigger
                CronTrigger.from_crontab(task["schedule"], timezone=ZoneInfo("Asia/Shanghai"))
            except (ValueError, TypeError) as e:
                errors.append(f"{prefix} [{name}] 无效的 cron 表达式 '{task['schedule']}': {e}")

    if errors:
        print("配置校验失败:")
        for e in errors:
            print(f"  ❌ {e}")
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Daily Bot")
    parser.add_argument("--once", action="store_true", help="立即执行任务后退出（CI 模式）")
    parser.add_argument("--task", action="append", help="指定要运行的任务名（可重复），默认全部")
    return parser.parse_args()


def main():
    args = _parse_args()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # 加载 .env
    dotenv_path = os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        print("⚠️  未找到 .env 文件，请从 .env.example 复制并填写")

    # 加载配置
    config_path = os.path.join(project_root, "config.yaml")
    if not os.path.exists(config_path):
        print(f"❌ 未找到配置文件: {config_path}")
        sys.exit(1)

    cfg = load_config(config_path)

    # 校验配置
    validate_config(cfg)

    ai_config = cfg["ai"]
    notifier_configs = cfg.get("notifiers", {})
    tasks = cfg.get("tasks", [])

    if not tasks:
        print("⚠️  配置中没有任务，请在 config.yaml 中添加 tasks")
        sys.exit(0)

    if args.once:
        from .scheduler import run_once
        run_once(tasks, ai_config, notifier_configs, task_names=args.task)
    else:
        from .scheduler import start
        start(tasks, ai_config, notifier_configs)


if __name__ == "__main__":
    main()
