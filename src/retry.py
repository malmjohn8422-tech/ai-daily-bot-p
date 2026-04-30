import time
import functools


def retry(max_attempts=3, delay=2, backoff=2, exceptions=(Exception,)):
    """简单重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        wait = delay * (backoff ** (attempt - 1))
                        from src.logger import log
                        log.warning(f"{func.__name__} 第{attempt}次失败: {e}, {wait}s后重试")
                        time.sleep(wait)
            raise last_exc
        return wrapper
    return decorator
