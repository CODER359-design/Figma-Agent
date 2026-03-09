from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, Tuple

from anthropic import Anthropic
from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_prompt


@dataclass
class LLMConfig:
    provider: str
    openai_api_key: str | None
    anthropic_api_key: str | None
    openai_model: str
    anthropic_model: str


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._openai = None
        self._anthropic = None

    @classmethod
    def from_env(cls) -> "LLMClient":
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        return cls(
            LLMConfig(
                provider=provider,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            )
        )

    def generate(self, normalized: Dict) -> Tuple[str, str]:
        payload = json.dumps(normalized, ensure_ascii=False, indent=2)
        if self.config.provider == "anthropic":
            return self._call_anthropic(payload)
        return self._call_openai(payload)

    def _call_openai(self, normalized_json: str) -> Tuple[str, str]:
        if not self.config.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if not self._openai:
            self._openai = OpenAI(api_key=self.config.openai_api_key)
        response = self._openai.chat.completions.create(
            model=self.config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(normalized_json)},
            ],
        )
        content = response.choices[0].message.content or ""
        return _extract_html_css(content)

    def _call_anthropic(self, normalized_json: str) -> Tuple[str, str]:
        if not self.config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        if not self._anthropic:
            self._anthropic = Anthropic(api_key=self.config.anthropic_api_key)
        response = self._anthropic.messages.create(
            model=self.config.anthropic_model,
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(normalized_json)}],
        )
        content = response.content[0].text if response.content else ""
        return _extract_html_css(content)


def _extract_html_css(content: str) -> Tuple[str, str]:
    json_payload = _extract_json_block(content)
    if not json_payload:
        raise ValueError("LLM response does not contain JSON")
    data = json.loads(json_payload)
    html = data.get("html", "").strip()
    css = data.get("css", "").strip()
    if not html or not css:
        raise ValueError("LLM response missing html or css")
    return html, css


def _extract_json_block(content: str) -> str:
    content = content.strip()
    if content.startswith("{"):
        return content
    match = re.search(r"\{[\s\S]*\}", content)
    return match.group(0) if match else ""
