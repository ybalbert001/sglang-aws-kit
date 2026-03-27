"""
Dynamic Tagging Handler for LiteLLM Proxy
根据 message 内容动态添加 tags，用于智能路由

如果 message 包含 "Hook condition evaluator" system prompt 特征，则标记为 "easy_subtask"
"""

from typing import Optional, Union
from litellm.integrations.custom_logger import CustomLogger


class DynamicTaggingHandler(CustomLogger):
    """
    检测 message 是否包含特定的 system prompt
    如果包含 "Hook condition evaluator" prompt，动态修改 model
    """

    # Hook condition evaluator system prompt 的特征字符串
    HOOK_EVALUATOR_MARKERS = [
        "You are evaluating a hook in Claude Code",
        "Your response must be a JSON object",
        '{"ok": true}',
        '{"ok": false}',
    ]

    def __init__(self):
        super().__init__()
        print("✅ DynamicTaggingHandler 已初始化")
        print(f"📋 检测规则: Hook condition evaluator system prompt")

    def log_pre_api_call(self, model, messages, kwargs):
        """
        在 API 调用前修改 model（同步方法）
        这个方法在 router 选择 deployment 之前被调用
        """
        try:
            print("\n" + "="*60)
            print("🔍 DynamicTaggingHandler (log_pre_api_call): 开始分析")

            if not messages:
                print("⚠️  没有 messages，跳过")
                return

            # 提取文本
            all_text = []
            for msg in messages:
                content = msg.get("content", "")
                text = self._extract_text_from_content(content)
                if text:
                    all_text.append(text)

            combined_text = " ".join(all_text)
            print(f"📝 消息数量: {len(messages)}")
            print(f"💬 消息预览: {combined_text[:150]}...")

            # 检查是否为 Hook evaluator
            is_hook_evaluator = self._is_hook_evaluator_prompt(combined_text)

            if is_hook_evaluator:
                original_model = model
                target_model = "sagemaker-qwen3-5-9b"

                print(f"✅ 检测到 Hook evaluator prompt")
                print(f"🔄 路由修改: {original_model} → {target_model}")

                # 修改 kwargs 中的 model
                kwargs["model"] = target_model

                print(f"✅ 已修改 kwargs['model'] = {target_model}")
            else:
                print(f"✅ 普通请求，保持原 model: {model}")

            print("="*60 + "\n")

        except Exception as e:
            print(f"❌ log_pre_api_call 出错: {e}")
            import traceback
            traceback.print_exc()

    def _is_hook_evaluator_prompt(self, text: str) -> bool:
        """
        检查文本是否包含 Hook condition evaluator system prompt 的特征

        Args:
            text: 要检查的文本

        Returns:
            bool: 是否为 Hook evaluator prompt
        """
        if not text:
            return False

        # 至少需要匹配 3 个特征字符串才认为是该 prompt（避免误判）
        match_count = 0
        matched_markers = []

        for marker in self.HOOK_EVALUATOR_MARKERS:
            if marker in text:
                match_count += 1
                matched_markers.append(marker)

        if match_count >= 3:
            print(f"   🎯 检测到 Hook evaluator prompt (匹配 {match_count}/4 个特征)")
            print(f"   匹配的特征: {matched_markers}")
            return True

        return False

    def _extract_text_from_content(self, content) -> str:
        """
        从 message content 中提取文本
        支持 string 和 multimodal 格式

        Args:
            content: message 的 content 字段

        Returns:
            str: 提取的文本内容
        """
        if isinstance(content, str):
            return content

        # 处理多模态内容 (如图片 + 文本)
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            return " ".join(text_parts)

        return ""

# 实例化 handler - LiteLLM 会自动加载这个实例
proxy_handler_instance = DynamicTaggingHandler()
