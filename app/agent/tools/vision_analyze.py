"""Vision analyze tool — analyze images through the vision model.

The agent supplies base64-encoded image bytes; the tool decodes them, runs
analysis via VisionService, and returns the textual result.

Security: image bytes are never logged — only character counts and metadata.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.core.exceptions import (
    ImageTooLargeError,
    UnsupportedFileTypeError,
    VisionProviderUnavailableError,
)
from app.core.security_context import SecurityContext

logger = logging.getLogger(__name__)

_NAME = "vision_analyze"
_PERM = "vision.analyze"


class VisionAnalyzeTool(BaseTool):
    """Analyze an image with the local vision model (Qwen2.5-VL)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=_NAME,
            description=(
                "Analyze an image using the vision model. "
                "Can describe images, perform OCR, analyze screenshots, "
                "extract tables and charts. "
                "Pass base64-encoded image bytes and a filename for type detection."
            ),
            parameters=[
                ToolParameter(
                    "image_base64",
                    "string",
                    "Base64-encoded image bytes (JPEG, PNG, or WebP)",
                    required=True,
                ),
                ToolParameter(
                    "filename",
                    "string",
                    "Original filename (e.g. 'screenshot.png') for type detection",
                    required=True,
                ),
                ToolParameter(
                    "prompt",
                    "string",
                    "Instruction for the vision model. "
                    "Default: describe the image and extract visible text.",
                    required=False,
                    default="",
                ),
            ],
            required_permission=_PERM,
        )

    async def execute(
        self,
        params: dict[str, Any],
        ctx: SecurityContext,
        session: AsyncSession,
    ) -> ToolResult:
        image_b64: str = str(params.get("image_base64", "")).strip()
        filename: str = str(params.get("filename", "image.png")).strip()
        prompt: str = str(params.get("prompt", "")).strip()

        if not image_b64:
            return ToolResult(
                success=False, data=None, error="image_base64 is required"
            )
        if _PERM not in ctx.permissions:
            return ToolResult(
                success=False,
                data=None,
                error=f"Permission '{_PERM}' required",
            )

        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            return ToolResult(
                success=False, data=None, error="image_base64 is not valid base64"
            )

        logger.debug(
            "tool.vision_analyze tenant=%s filename=%s image_bytes=%d",
            ctx.tenant_id,
            filename,
            len(image_bytes),
        )

        try:
            from app.vision.service import VisionService

            svc = VisionService(session)
            result = await svc.analyze_image(
                file_bytes=image_bytes,
                filename=filename,
                ctx=ctx,
                prompt=prompt or None,
            )
            return ToolResult(
                success=True,
                data={
                    "analysis": result.analysis,
                    "model": result.model,
                    "filename": result.filename,
                },
            )
        except UnsupportedFileTypeError as exc:
            return ToolResult(
                success=False, data=None, error=f"Unsupported type: {exc.message}"
            )
        except ImageTooLargeError as exc:
            return ToolResult(
                success=False, data=None, error=f"Image too large: {exc.message}"
            )
        except VisionProviderUnavailableError as exc:
            return ToolResult(
                success=False,
                data=None,
                error=f"Vision provider unavailable: {exc.message}",
            )
        except Exception:
            logger.warning(
                "tool.vision_analyze.unexpected_error tenant=%s", ctx.tenant_id
            )
            return ToolResult(
                success=False, data=None, error="Vision analysis failed unexpectedly"
            )
