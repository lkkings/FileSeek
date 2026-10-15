from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")
Namespace = str


@dataclass(slots=True)
class _CacheEntry(Generic[V]):
    """单个缓存项。"""

    expires_at: float
    value: V


class TTLLRUCache(Generic[K, V]):
    """
    分组 TTL + LRU 缓存。

    数据结构：

        namespace
            ├── key -> CacheEntry
            ├── key -> CacheEntry
            └── ...

    例如：

        query
            ├── 123 -> result
            ├── 456 -> result
            └── 789 -> result

        user
            ├── 123 -> user
            └── 456 -> user

    特性：
    - namespace 隔离
    - entry 级 TTL
    - entry 级 LRU
    - namespace 级 clear
    - 全局 clear
    - 协程安全
    - 惰性清理过期数据
    """

    def __init__(
        self,
        maxsize: int = 128,
        ttl: float = 60.0,
    ) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be greater than 0")

        if ttl <= 0:
            raise ValueError("ttl must be greater than 0")

        self.maxsize = maxsize
        self.ttl = ttl

        # namespace -> OrderedDict[key, CacheEntry]
        self._cache: dict[
            Namespace,
            OrderedDict[K, _CacheEntry[V]],
        ] = {}

        # 所有 namespace 中 entry 的总数量
        self._size = 0

        # asyncio 协程锁
        self._lock = asyncio.Lock()

    def _remove_expired_locked(
        self,
        namespace: Namespace,
        now: float,
    ) -> None:
        """删除指定 namespace 中已经过期的 entry。必须在锁内调用。"""
        bucket = self._cache.get(namespace)

        if bucket is None:
            return

        expired_keys = [key for key, entry in bucket.items() if entry.expires_at <= now]

        for key in expired_keys:
            del bucket[key]
            self._size -= 1

        if not bucket:
            del self._cache[namespace]

    def _evict_if_needed_locked(self) -> None:
        """
        按 LRU 淘汰最旧 entry。

        必须在锁内调用。
        """
        while self._size > self.maxsize:
            # 找到所有 namespace 中最旧的 entry。
            oldest_namespace: Namespace | None = None
            oldest_key: K | None = None
            oldest_entry: _CacheEntry[V] | None = None

            for namespace, bucket in self._cache.items():
                if not bucket:
                    continue

                key, entry = next(iter(bucket.items()))

                if oldest_entry is None or entry.expires_at < oldest_entry.expires_at:
                    oldest_namespace = namespace
                    oldest_key = key
                    oldest_entry = entry

            if oldest_namespace is None or oldest_key is None:
                break

            bucket = self._cache[oldest_namespace]
            del bucket[oldest_key]
            self._size -= 1

            if not bucket:
                del self._cache[oldest_namespace]

    async def get(
        self,
        namespace: Namespace,
        key: K,
    ) -> V | None:
        """
        获取缓存。

        命中：
            返回 value，并更新 LRU。

        未命中或过期：
            返回 None。
        """
        now = time.monotonic()

        async with self._lock:
            bucket = self._cache.get(namespace)

            if bucket is None:
                return None

            entry = bucket.get(key)

            if entry is None:
                return None

            if entry.expires_at <= now:
                del bucket[key]
                self._size -= 1

                if not bucket:
                    del self._cache[namespace]

                return None

            # 更新 entry 的 LRU 位置
            bucket.move_to_end(key)

            return entry.value

    async def set(
        self,
        namespace: Namespace,
        key: K,
        value: V,
    ) -> None:
        """
        写入缓存。

        如果 key 已存在：
        - 覆盖 value
        - 重置 TTL
        - 更新 LRU
        """
        now = time.monotonic()

        async with self._lock:
            bucket = self._cache.get(namespace)

            if bucket is None:
                bucket = OrderedDict()
                self._cache[namespace] = bucket

            # 更新已有 entry
            if key in bucket:
                del bucket[key]
                self._size -= 1

            bucket[key] = _CacheEntry(
                expires_at=now + self.ttl,
                value=value,
            )

            self._size += 1

            self._evict_if_needed_locked()

    async def delete(
        self,
        namespace: Namespace,
        key: K,
    ) -> bool:
        """
        删除单个缓存。

        返回：
            True  -> 存在并删除
            False -> 不存在
        """
        async with self._lock:
            bucket = self._cache.get(namespace)

            if bucket is None or key not in bucket:
                return False

            del bucket[key]
            self._size -= 1

            if not bucket:
                del self._cache[namespace]

            return True

    async def clear(
        self,
        namespace: Namespace | None = None,
    ) -> None:
        """
        清理缓存。

        clear("query"):
            只清空 query namespace。

        clear():
            清空全部缓存。
        """
        async with self._lock:
            if namespace is None:
                self._cache.clear()
                self._size = 0
                return

            bucket = self._cache.pop(namespace, None)

            if bucket is not None:
                self._size -= len(bucket)

    async def size(self) -> int:
        """返回当前缓存 entry 总数量。"""
        async with self._lock:
            return self._size

    async def namespace_size(
        self,
        namespace: Namespace,
    ) -> int:
        """返回指定 namespace 中的 entry 数量。"""
        async with self._lock:
            bucket = self._cache.get(namespace)
            return len(bucket) if bucket else 0

    async def cleanup(self) -> int:
        """
        主动清理所有过期 entry。

        返回实际清理的数量。
        """
        now = time.monotonic()

        async with self._lock:
            before = self._size

            for namespace in list(self._cache):
                self._remove_expired_locked(namespace, now)

            return before - self._size


# ----------------------------------------------------------------------
# Global cache
# ----------------------------------------------------------------------

_cache = TTLLRUCache[str, Any](
    maxsize=128,
    ttl=60.0,
)


def get_cache_service() -> TTLLRUCache[str, Any]:
    return _cache
