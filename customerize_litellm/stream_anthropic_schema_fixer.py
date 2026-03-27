"""
Anthropic Schema Fixer Hook for LiteLLM

This hook fixes Anthropic streaming schema issues from AWS Bedrock/Sagemaker.

Issues fixed:
1. Add cache_creation field to message_start usage
2. Add usage field to message_stop event
3. Ensure stop_sequence is present in message_delta

Usage in config.yaml:
    litellm_settings:
      callbacks: ["stream_anthropic_schema_fixer.hook"]
"""

import json
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from litellm._logging import verbose_logger
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth


class AnthropicSchemaFixerHook(CustomLogger):
    """
    Fix Anthropic streaming response schema issues for Bedrock/Sagemaker.

    This hook intercepts the raw SSE byte stream from Anthropic API and:
    - Adds missing cache_creation field to message_start events
    - Tracks usage information and adds it to message_stop events
    - Ensures all required fields are present per Anthropic Messages API spec
    """

    def __init__(self):
        super().__init__()
        self.name = "anthropic_schema_fixer"
        verbose_logger.info("AnthropicSchemaFixerHook initialized")

    def _parse_sse(self, sse_data: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Parse SSE format data.

        Args:
            sse_data: Raw SSE string, e.g., "event: message_start\ndata: {...}\n\n"

        Returns:
            Tuple of (event_type, data_json)
        """
        lines = sse_data.strip().split("\n")
        event_type = None
        data_json = None

        for line in lines:
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    try:
                        data_json = json.loads(data_str)
                    except json.JSONDecodeError as e:
                        verbose_logger.error(
                            f"AnthropicSchemaFixer: Failed to parse JSON: {e}"
                        )
                        return None, None

        return event_type, data_json

    def _rebuild_sse(self, event_type: Optional[str], data_json: Dict[str, Any]) -> bytes:
        """
        Rebuild SSE format from parsed data.

        Args:
            event_type: Event type (e.g., "message_start")
            data_json: JSON data to encode

        Returns:
            SSE formatted bytes
        """
        sse_parts = []

        if event_type:
            sse_parts.append(f"event: {event_type}")

        sse_parts.append(f"data: {json.dumps(data_json)}")
        sse_parts.append("")  # Empty line for SSE format
        sse_parts.append("")  # Double newline at end

        return "\n".join(sse_parts).encode("utf-8")

    def _fix_message_start(self, data_json: Dict[str, Any]) -> bool:
        """
        Fix message_start event by adding cache_creation field.

        Args:
            data_json: The message_start event data

        Returns:
            True if modified, False otherwise
        """
        message = data_json.get("message", {})
        usage = message.get("usage", {})

        if not usage:
            return False

        modified = False

        # Add cache_creation field if missing
        if "cache_creation" not in usage:
            usage["cache_creation"] = {
                "ephemeral_5m_input_tokens": 0,
                "ephemeral_1h_input_tokens": 0,
            }
            modified = True

        # Ensure cache token fields exist
        if "cache_creation_input_tokens" not in usage:
            usage["cache_creation_input_tokens"] = 0
            modified = True

        if "cache_read_input_tokens" not in usage:
            usage["cache_read_input_tokens"] = 0
            modified = True

        if modified:
            message["usage"] = usage
            data_json["message"] = message
            verbose_logger.debug(
                "AnthropicSchemaFixer: Added cache_creation to message_start"
            )

        return modified

    def _fix_message_delta(self, data_json: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Fix message_delta event and extract usage.

        Args:
            data_json: The message_delta event data

        Returns:
            Tuple of (modified, usage_dict)
        """
        modified = False
        usage = data_json.get("usage")

        # Ensure stop_sequence is present in delta if stop_reason exists
        delta = data_json.get("delta", {})
        if "stop_reason" in delta and "stop_sequence" not in delta:
            delta["stop_sequence"] = None
            data_json["delta"] = delta
            modified = True
            verbose_logger.debug(
                "AnthropicSchemaFixer: Added stop_sequence to message_delta"
            )

        return modified, usage

    def _fix_message_stop(
        self, data_json: Dict[str, Any], last_usage: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Fix message_stop event by adding usage field.

        Args:
            data_json: The message_stop event data
            last_usage: Usage data from message_delta

        Returns:
            True if modified, False otherwise
        """
        if "usage" not in data_json and last_usage:
            data_json["usage"] = last_usage
            verbose_logger.debug(
                f"AnthropicSchemaFixer: Added usage to message_stop: {last_usage}"
            )
            return True

        return False

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: AsyncGenerator[bytes, None],
        request_data: dict,
    ) -> AsyncGenerator[bytes, None]:
        """
        Transform Anthropic SSE stream to fix schema issues.

        Args:
            user_api_key_dict: API key authentication info
            response: Original SSE byte stream from Anthropic API
            request_data: Original request data

        Yields:
            Modified SSE byte stream with schema fixes applied
        """
        # Track usage across the stream for message_stop event
        last_usage: Optional[Dict[str, Any]] = None
        chunk_count = 0

        async for chunk in response:
            chunk_count += 1

            # Pass through non-bytes chunks
            if not isinstance(chunk, bytes):
                yield chunk
                continue

            try:
                # Decode SSE format: "event: xxx\ndata: {...}\n\n"
                decoded = chunk.decode("utf-8")

                # Check if this is an SSE event with data
                if not decoded.startswith("event:") and not decoded.startswith("data:"):
                    yield chunk
                    continue

                # Parse SSE format
                event_type, data_json = self._parse_sse(decoded)

                if not data_json:
                    yield chunk
                    continue

                # Determine event type (from event: line or type field in data)
                if not event_type:
                    event_type = data_json.get("type")

                if not event_type:
                    yield chunk
                    continue

                # Apply fixes based on event type
                modified = False

                if event_type == "message_start":
                    modified = self._fix_message_start(data_json)

                elif event_type == "message_delta":
                    delta_modified, usage = self._fix_message_delta(data_json)
                    modified = delta_modified
                    # Track usage for message_stop
                    if usage:
                        last_usage = usage

                elif event_type == "message_stop":
                    modified = self._fix_message_stop(data_json, last_usage)

                # Re-encode if modified
                if modified:
                    yield self._rebuild_sse(event_type, data_json)
                else:
                    yield chunk

            except Exception as e:
                # If parsing fails, pass through original chunk
                verbose_logger.error(
                    f"AnthropicSchemaFixer error processing chunk {chunk_count}: {e}, "
                    "passing through original chunk"
                )
                yield chunk

        verbose_logger.debug(
            f"AnthropicSchemaFixer: Processed {chunk_count} chunks, "
            f"last_usage={'present' if last_usage else 'not found'}"
        )


# Export hook instance (not class) to avoid "missing self" error
# when LiteLLM calls non-streaming hooks
hook = AnthropicSchemaFixerHook()
