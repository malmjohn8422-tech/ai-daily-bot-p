from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from time import sleep
import signal
import sys
import threading
import zoneinfo

from .collectors import get_collector
from .processors import get_processor
from .notifiers import get_notifier
from .notifiers.base import NotificationPartialFailure
from .reports import report_archive
from .storage import storage
from .logger import log


shutdown_event = threading.Event()
TIMEZONE = zoneinfo.ZoneInfo("Asia/Shanghai")


def _prepare_report(task_cfg: dict, ai_config: dict, record_id: int) -> tuple[str, list[dict], str]:
    """Generate a report once per task record, or reuse an existing archived report."""
    name = task_cfg["name"]
    existing_report_path = storage.get_report_path(record_id)
    if report_archive.exists(existing_report_path):
        result = report_archive.load(existing_report_path)
        data = report_archive.load_items(existing_report_path)
        log.info(f"  {name} 复用已生成报告: {existing_report_path}")
        return result, data, existing_report_path
    elif existing_report_path:
        log.warning(f"  {name} 已记录报告路径但文件不存在，将重新生成: {existing_report_path}")

    data = _fetch_task_data(task_cfg)
    log.info(f"  {name} 采集到 {len(data)} 条数据")

    history = storage.get_trend_history(name, days=7)
    params = dict(task_cfg.get("params") or {})
    if history:
        params["_trend_history"] = history

    processor_cls = get_processor(task_cfg["processor"])
    processor = processor_cls()
    result = processor.process(data, ai_config, params)
    log.info(f"  {name} 处理完成，共 {len(result)} 字")

    report_path = report_archive.save(name, record_id, result, data)
    storage.record_report(record_id, report_path)
    log.info(f"  {name} 报告已归档: {report_path}")

    return result, data, report_path


def _fetch_task_data(task_cfg: dict) -> list[dict]:
    sources = task_cfg.get("sources")
    if sources:
        data = []
        for source_cfg in sources:
            collector_name = source_cfg["collector"]
            source_required = bool(source_cfg.get("required", False))
            try:
                collector_cls = get_collector(collector_name)
                collector = collector_cls()
                source_params = dict(source_cfg.get("params") or {})
                items = collector.fetch(source_params)
            except Exception as e:
                if source_required:
                    raise
                log.warning(f"来源 {collector_name} 采集失败，已跳过: {e}")
                continue
            for item in items:
                item.setdefault("extra", {})["source_collector"] = collector_name
            data.extend(items)
        return data

    collector_cls = get_collector(task_cfg["collector"])
    collector = collector_cls()
    return collector.fetch(task_cfg.get("params"))


def _execute_task(task_cfg: dict, ai_config: dict, notifier_configs: dict, record_id: int) -> str:
    """执行任务核心逻辑（采集 → 处理 → 归档 → 推送），返回摘要"""
    name = task_cfg["name"]
    result, data, report_path = _prepare_report(task_cfg, ai_config, record_id)

    notifier_cls = get_notifier(task_cfg["notifier"])
    notifier = notifier_cls()
    notifier_cfg = notifier_configs.get(task_cfg["notifier"], {})
    ok = notifier.send(name, result, notifier_cfg)
    if not ok:
        raise RuntimeError(f"通知器 {task_cfg['notifier']} 推送返回失败")

    if task_cfg.get("save_trends", True) and data:
        try:
            storage.save_trend_items(name, data)
        except Exception as e:
            log.error(f"{name} 趋势历史保存失败，已跳过本次趋势入库: {e}")

    summary = f"✅ {name} · {len(data)}条数据 · {len(result)}字 · {report_path}"
    return summary


def run_task(task_cfg: dict, ai_config: dict, notifier_configs: dict) -> bool:
    """执行一个任务实例（带自动重试），返回是否成功。"""
    name = task_cfg["name"]
    log.info(f"开始任务: {name}")
    record_id = storage.record_start(name)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            summary = _execute_task(task_cfg, ai_config, notifier_configs, record_id)
            storage.record_success(record_id, summary)
            log.info(f"任务完成: {summary}")
            return True
        except NotificationPartialFailure as e:
            log.error(f"任务部分推送失败，不再重试以避免重复推送: {name} - {e}")
            storage.record_failure(record_id, str(e))
            return False
        except Exception as e:
            if attempt < max_attempts:
                wait = 2 * (2 ** (attempt - 1))
                log.warning(f"{name} 第{attempt}次失败: {e}, {wait}s后重试")
                sleep(wait)
            else:
                log.error(f"任务失败: {name} - {e}")
                storage.record_failure(record_id, str(e))
                return False


def run_once(tasks: list[dict], ai_config: dict, notifier_configs: dict, task_names: list[str] | None = None):
    """Run specified tasks immediately and exit. Used for CI / --once mode."""
    if task_names:
        filtered = [t for t in tasks if t.get("name") in task_names]
        if not filtered:
            log.error(f"未找到匹配的任务: {task_names}")
            sys.exit(1)
        tasks = filtered

    task_names_str = ", ".join(t["name"] for t in tasks)
    log.info(f"一次性模式：执行任务 [{task_names_str}]")
    any_failed = False
    for task_cfg in tasks:
        if not run_task(task_cfg, ai_config, notifier_configs):
            any_failed = True

    if any_failed:
        log.error("部分任务失败，退出码 1")
        sys.exit(1)
    log.info("所有任务执行完毕")


def start(tasks: list[dict], ai_config: dict, notifier_configs: dict):
    """启动调度器"""
    scheduler = BackgroundScheduler()

    for task_cfg in tasks:
        cron_expr = task_cfg["schedule"]
        scheduler.add_job(
            run_task,
            CronTrigger.from_crontab(cron_expr, timezone=TIMEZONE),
            args=[task_cfg, ai_config, notifier_configs],
            id=task_cfg["name"],
            replace_existing=True,
            misfire_grace_time=300,
        )
        log.info(f"已注册任务 [{task_cfg['name']}] 调度: {cron_expr}")

    scheduler.start()
    log.info("AI Daily Bot 已启动，等待调度...")

    def shutdown(signum, frame):
        log.info(f"收到信号 {signum}，正在关闭调度器...")
        scheduler.shutdown(wait=False)
        shutdown_event.set()

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    shutdown_event.wait()
    log.info("已停止")
