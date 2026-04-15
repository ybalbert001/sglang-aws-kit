"""
Ping Keepalive Handler for LiteLLM Proxy
在等待上游响应期间定期发送 ping 消息，防止客户端超时

解决问题：
- 上游（Bedrock）生成大 chunk 时间过长（如 60 秒+）
- 客户端 read timeout，无法收到任何数据
- 通过定期发送 ping 保持连接活跃

工作原理：
- 使用 asyncio.wait_for() 检测是否有数据到来
- 如果超时（无数据），发送 ping 保活
- 如果有数据，立即转发
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict

from litellm._logging import verbose_logger
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth


class PingKeepaliveHandler(CustomLogger):
    """
    在等待上游响应期间定期发送 ping 消息，防止客户端超时
    """

    def __init__(self):
        super().__init__()
        self.name = "ping_keepalive"
        # 配置参数
        self.ping_interval = 30.0  # 如果 30 秒内没有数据，发送 ping
        print(f"✅ PingKeepaliveHandler 已初始化 (ping_interval={self.ping_interval}s)")
        verbose_logger.info(
            f"✅ PingKeepaliveHandler 已初始化 (ping_interval={self.ping_interval}s)"
        )

    def _build_ping(self) -> bytes:
        """
        构建 ping 消息（SSE 格式）
        参考：bedrock_api_converter/app/services/bedrock_service.py#L1334

        Returns:
            Ping SSE 消息
        """
        # Ping 事件数据（只包含 type 字段，不包含其他数据）
        ping_event = {
            "type": "ping"
        }

        # Anthropic SSE 格式:
        # event: {event_type}
        # data: {json_data}
        # (blank line)
        event_type = ping_event["type"]
        event_data = json.dumps(ping_event)

        return f"event: {event_type}\ndata: {event_data}\n\n".encode("utf-8")

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: AsyncGenerator[bytes, None],
        request_data: dict,
    ) -> AsyncGenerator[bytes, None]:
        """
        处理流式响应，在等待期间发送 ping 保活

        核心思路：
        1. 创建一个独立的 Task 来获取下一个 chunk（不会被 wait_for 取消）
        2. 使用 asyncio.wait() 检查是否有数据或超时
        3. 如果超时发送 ping，但 Task 继续运行等待数据
        4. 如果有数据，立即转发

        Args:
            user_api_key_dict: API key 认证信息
            response: 原始 SSE 字节流
            request_data: 原始请求数据

        Yields:
            处理后的 SSE 字节流（原始数据 + ping）
        """
        chunk_count = 0
        ping_count = 0
        total_wait_time = 0.0

        print("PingKeepalive: 开始处理流式响应")
        verbose_logger.info("PingKeepalive: 开始处理流式响应")

        # 创建异步迭代器
        response_iter = response.__aiter__()

        # 当前正在等待的 task（用于持续等待数据）
        pending_task = None

        while True:
            try:
                # 如果没有 pending task，创建一个新的
                if pending_task is None:
                    print(f"PingKeepalive: 创建新的 __anext__() task...")
                    pending_task = asyncio.create_task(response_iter.__anext__())

                # 等待数据或超时
                wait_start = time.time()
                done, pending = await asyncio.wait(
                    {pending_task},
                    timeout=self.ping_interval
                )
                wait_duration = time.time() - wait_start

                if done:
                    # 有数据到达
                    chunk_count += 1
                    total_wait_time += wait_duration

                    try:
                        chunk = pending_task.result()
                        print(
                            f"PingKeepalive: 收到 chunk #{chunk_count} "
                            f"(等待 {wait_duration:.2f}s, 大小 {len(chunk) if isinstance(chunk, bytes) else 'N/A'} bytes)"
                        )
                        verbose_logger.debug(
                            f"PingKeepalive: 收到 chunk #{chunk_count} "
                            f"(等待 {wait_duration:.2f}s, 大小 {len(chunk) if isinstance(chunk, bytes) else 'N/A'} bytes)"
                        )

                        # 重置 pending_task，下次循环会创建新的
                        pending_task = None

                        # 立即转发
                        yield chunk

                    except StopAsyncIteration:
                        # 流结束
                        print(
                            f"PingKeepalive: 流结束 (StopAsyncIteration) - "
                            f"总 chunks: {chunk_count}, ping 数: {ping_count}, "
                            f"累计等待: {total_wait_time:.1f}s"
                        )
                        verbose_logger.info(
                            f"PingKeepalive: 处理完成 - "
                            f"总 chunks: {chunk_count}, ping 数: {ping_count}, "
                            f"累计等待: {total_wait_time:.1f}s"
                        )
                        break

                else:
                    # 超时：发送 ping，但 task 继续运行
                    ping_count += 1
                    total_wait_time += self.ping_interval

                    print(
                        f"PingKeepalive: {self.ping_interval}s 无数据，发送 ping #{ping_count} "
                        f"(累计等待 {total_wait_time:.1f}s, task 继续等待...)"
                    )
                    verbose_logger.info(
                        f"PingKeepalive: {self.ping_interval}s 无数据，发送 ping #{ping_count} "
                        f"(累计等待 {total_wait_time:.1f}s)"
                    )

                    # 发送 ping
                    ping_message = self._build_ping()
                    yield ping_message

                    # pending_task 保持不变，继续等待它完成
                    # 下次循环会再次 await 这个 task

            except Exception as e:
                # 其他错误
                print(f"PingKeepalive: 处理出错: {e}")
                verbose_logger.error(
                    f"PingKeepalive: 处理出错: {e}",
                    exc_info=True
                )
                # 取消 pending task
                if pending_task and not pending_task.done():
                    pending_task.cancel()
                break


# 导出 hook 实例
hook = PingKeepaliveHandler()
