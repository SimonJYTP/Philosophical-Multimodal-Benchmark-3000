from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import hashlib
import json
import mimetypes
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "data" / "query.json"
PROMPTS_PATH = ROOT / "evaluation" / "prompts.json"
VULCA_FAMILY = "philosophical_aesthetics_dimension_identification"
HL_FAMILY = "scene_action_rationale"
CHOICE_FAMILIES = {
    "visual_multiple_choice_qa",
    "moral_judge",
    "moral_classification",
    "moral_response",
}
MULTIMODAL_FAMILIES = [HL_FAMILY, *sorted(CHOICE_FAMILIES)]
ALL_FAMILIES = [*MULTIMODAL_FAMILIES, VULCA_FAMILY]

PROMPT_MAP = {
    ("P0", "en", "choice"): "P0-choice-direct-en-v1",
    ("P1", "en", "choice"): "P1-choice-evidence-en-v1",
    ("P0", "en", "hl"): "P0-hl-direct-en-v1",
    ("P1", "en", "hl"): "P1-hl-evidence-en-v1",
    ("P0", "en", "vulca"): "P0-vulca-direct-en-v1",
    ("P1", "en", "vulca"): "P1-vulca-evidence-en-v1",
    ("P0", "zh", "hss"): "P0-hss-direct-zh-v1",
    ("P1", "zh", "hss"): "P1-hss-evidence-zh-v1",
    ("P0", "zh", "hl"): "P0-hl-direct-zh-v1",
    ("P1", "zh", "hl"): "P1-hl-evidence-zh-v1",
    ("P0", "zh", "vulca"): "P0-vulca-direct-zh-v1",
    ("P1", "zh", "vulca"): "P1-vulca-evidence-zh-v1",
}


class EvaluationError(RuntimeError):
    pass


class ApiError(EvaluationError):
    pass


@dataclass
class GenerationResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> tuple[dict, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body, response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise ApiError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"network error: {exc.reason}") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise ApiError(str(exc)) from exc


def endpoint(base_url: str, suffix: str) -> str:
    clean = base_url.rstrip("/")
    return clean if clean.endswith(suffix) else clean + suffix


def image_payload(path: Path) -> tuple[str, str, str]:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    return media_type, base64.b64encode(data).decode("ascii"), hashlib.sha256(data).hexdigest()


class Adapter:
    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        raise NotImplementedError


class OpenAICompatibleAdapter(Adapter):
    def __init__(self, args: argparse.Namespace, api_key: str):
        self.args = args
        self.api_key = api_key

    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        content: list[dict[str, Any]] = []
        if image:
            media_type, encoded = image
            image_url: dict[str, str] = {"url": f"data:{media_type};base64,{encoded}"}
            if self.args.image_detail != "omit":
                image_url["detail"] = self.args.image_detail
            content.append(
                {
                    "type": "image_url",
                    "image_url": image_url,
                }
            )
        content.append({"type": "text", "text": prompt})
        payload: dict[str, Any] = {
            "model": self.args.model,
            "messages": [
                {"role": "system", "content": self.args.system_prompt},
                {"role": "user", "content": content},
            ],
        }
        add_generation_parameters(payload, self.args, max_tokens)
        body, headers = post_json(
            endpoint(self.args.base_url, "/chat/completions"),
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
            self.args.timeout,
        )
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError(f"unexpected Chat Completions response: {str(body)[:1000]}") from exc
        usage = body.get("usage") or {}
        return GenerationResult(
            text=flatten_text(text),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            request_id=body.get("id") or headers.get("x-request-id"),
        )


class OpenAIResponsesAdapter(Adapter):
    def __init__(self, args: argparse.Namespace, api_key: str):
        self.args = args
        self.api_key = api_key

    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        content: list[dict[str, Any]] = []
        if image:
            media_type, encoded = image
            image_part = {"type": "input_image", "image_url": f"data:{media_type};base64,{encoded}"}
            if self.args.image_detail != "omit":
                image_part["detail"] = self.args.image_detail
            content.append(image_part)
        content.append({"type": "input_text", "text": prompt})
        payload: dict[str, Any] = {
            "model": self.args.model,
            "instructions": self.args.system_prompt,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": max_tokens,
        }
        if self.args.temperature is not None:
            payload["temperature"] = self.args.temperature
        if self.args.top_p is not None:
            payload["top_p"] = self.args.top_p
        body, headers = post_json(
            endpoint(self.args.base_url, "/responses"),
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
            self.args.timeout,
        )
        text = body.get("output_text") or ""
        if not text:
            blocks = []
            for output in body.get("output") or []:
                for part in output.get("content") or []:
                    if part.get("type") == "output_text":
                        blocks.append(part.get("text", ""))
            text = "\n".join(blocks)
        if not text:
            raise ApiError(f"unexpected Responses response: {str(body)[:1000]}")
        usage = body.get("usage") or {}
        return GenerationResult(
            text=text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            request_id=body.get("id") or headers.get("x-request-id"),
        )


class AnthropicAdapter(Adapter):
    def __init__(self, args: argparse.Namespace, api_key: str):
        self.args = args
        self.api_key = api_key

    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        content: list[dict[str, Any]] = []
        if image:
            media_type, encoded = image
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}}
            )
        content.append({"type": "text", "text": prompt})
        payload: dict[str, Any] = {
            "model": self.args.model,
            "system": self.args.system_prompt,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
        }
        if self.args.temperature is not None:
            payload["temperature"] = self.args.temperature
        if self.args.top_p is not None:
            payload["top_p"] = self.args.top_p
        body, headers = post_json(
            endpoint(self.args.base_url, "/messages"),
            {"x-api-key": self.api_key, "anthropic-version": self.args.anthropic_version},
            payload,
            self.args.timeout,
        )
        text = "\n".join(part.get("text", "") for part in body.get("content", []) if part.get("type") == "text")
        if not text:
            raise ApiError(f"unexpected Anthropic response: {str(body)[:1000]}")
        usage = body.get("usage") or {}
        return GenerationResult(
            text=text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            request_id=body.get("id") or headers.get("request-id"),
        )


class GeminiAdapter(Adapter):
    def __init__(self, args: argparse.Namespace, api_key: str):
        self.args = args
        self.api_key = api_key

    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        parts: list[dict[str, Any]] = []
        if image:
            media_type, encoded = image
            parts.append({"inline_data": {"mime_type": media_type, "data": encoded}})
        parts.append({"text": prompt})
        generation: dict[str, Any] = {"maxOutputTokens": max_tokens, "candidateCount": 1}
        if self.args.temperature is not None:
            generation["temperature"] = self.args.temperature
        if self.args.top_p is not None:
            generation["topP"] = self.args.top_p
        payload = {
            "systemInstruction": {"parts": [{"text": self.args.system_prompt}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation,
        }
        model = urllib.parse.quote(self.args.model, safe="")
        url = endpoint(self.args.base_url, f"/models/{model}:generateContent")
        separator = "&" if "?" in url else "?"
        body, headers = post_json(url + separator + "key=" + urllib.parse.quote(self.api_key), {}, payload, self.args.timeout)
        try:
            response_parts = body["candidates"][0]["content"]["parts"]
            text = "\n".join(part.get("text", "") for part in response_parts if "text" in part)
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError(f"unexpected Gemini response: {str(body)[:1000]}") from exc
        if not text:
            raise ApiError(f"empty Gemini response: {str(body)[:1000]}")
        usage = body.get("usageMetadata") or {}
        return GenerationResult(
            text=text,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            request_id=headers.get("x-request-id"),
        )


class MockAdapter(Adapter):
    def generate(self, prompt: str, image: tuple[str, str] | None, max_tokens: int) -> GenerationResult:
        if '"rationale"' in prompt:
            text = json.dumps(
                {
                    "scene": "uncertain",
                    "action": "uncertain",
                    "objects": [],
                    "visible_evidence": [],
                    "rationale": "uncertain",
                    "uncertainty": "high",
                }
            )
        elif '"answer"' in prompt:
            text = '{"visible_evidence":[],"uncertainty":"high","answer":"A"}'
        elif "L5 label" in prompt or "L5 标签" in prompt:
            text = ""
        else:
            text = "A"
        return GenerationResult(text=text, input_tokens=0, output_tokens=0, request_id="mock")


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(part.get("text", "")) for part in value if isinstance(part, dict))
    return str(value)


def add_generation_parameters(payload: dict[str, Any], args: argparse.Namespace, max_tokens: int) -> None:
    payload[args.max_tokens_field] = max_tokens
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.top_p is not None:
        payload["top_p"] = args.top_p
    if args.api_seed is not None:
        payload["seed"] = args.api_seed


def family_kind(family: str, language: str) -> str:
    if family == HL_FAMILY:
        return "hl"
    if family == VULCA_FAMILY:
        return "vulca"
    if family == "visual_multiple_choice_qa" and language == "zh":
        return "hss"
    if family in CHOICE_FAMILIES:
        return "choice"
    raise EvaluationError(f"unknown family: {family}")


def prompt_catalog() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = load_json(PROMPTS_PATH)
    return payload, {item["prompt_id"]: item for item in payload["prompts"]}


def render_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_options(options: Any, language: str) -> str:
    if not options:
        return ""
    selected = options.get(language) if isinstance(options, dict) else options
    if selected is None:
        return ""
    if isinstance(selected, dict):
        return "\n".join(f"{key}. {value}" for key, value in selected.items())
    return render_value(selected)


def read_codebook(path: Path | None) -> tuple[str, str]:
    if path is None:
        return "", ""
    if not path.is_file():
        raise EvaluationError(f"VULCA codebook not found: {path}")
    if path.suffix.lower() == ".json":
        content = load_json(path)
        rendered = json.dumps(content, ensure_ascii=False, indent=2)
    else:
        rendered = path.read_text(encoding="utf-8")
    if not rendered.strip() or "AUTHOR_INPUT_NEEDED" in rendered:
        raise EvaluationError("VULCA codebook is empty or still contains placeholders")
    return rendered, rendered


def choose_prompt_id(
    family: str, suite: str, language: str, condition: str, explicit_prompt_id: str | None
) -> str:
    if explicit_prompt_id:
        return explicit_prompt_id
    if condition == "hl_gold_context":
        if family != HL_FAMILY or suite != "P0" or language != "en":
            raise EvaluationError("hl_gold_context currently requires HL, P0 and en")
        return "P0-hl-gold-context-en-v1"
    key = (suite, language, family_kind(family, language))
    if key not in PROMPT_MAP:
        raise EvaluationError(f"no standardized prompt for suite={suite}, language={language}, family={family}")
    return PROMPT_MAP[key]


def render_prompt(
    record: dict[str, Any], template: str, language: str, codebook_en: str, codebook_zh: str
) -> str:
    inputs = record["input"]
    native_prompt = inputs["prompt"].get(language)
    if not native_prompt:
        raise EvaluationError(f"{record['id']} does not provide a native {language} prompt")
    context = inputs["context"].get(language)
    variables = {
        "native_prompt_en": inputs["prompt"].get("en") or "",
        "native_prompt_zh": inputs["prompt"].get("zh") or "",
        "options_en_or_empty": render_options(inputs.get("options"), "en"),
        "options_zh": render_options(inputs.get("options"), "zh"),
        "context_en": render_value(inputs["context"].get("en")),
        "context_zh": render_value(inputs["context"].get("zh")),
        "l5_codebook": codebook_en,
        "l5_codebook_zh": codebook_zh,
    }
    output = template
    for name, value in variables.items():
        output = output.replace("{{" + name + "}}", value)
    unresolved = re.findall(r"\{\{([^{}]+)\}\}", output)
    if unresolved:
        raise EvaluationError(f"unresolved prompt variables for {record['id']}: {unresolved}")
    if family_kind(record["task"]["family"], language) == "vulca" and not codebook_en:
        raise EvaluationError("VULCA requires --vulca-codebook with published global label definitions")
    if condition_needs_context(template) and not context:
        raise EvaluationError(f"{record['id']} is missing required {language} context")
    return output.strip()


def condition_needs_context(template: str) -> bool:
    return "{{context_" in template


def strict_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_refusal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cannot|can't|unable to|won't)\b.{0,40}\b(?:answer|assist|analy[sz]e)\b|无法(?:回答|分析)|不能(?:回答|分析)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )


def string_list(value: Any, maximum: int | None = None) -> bool:
    return isinstance(value, list) and (maximum is None or len(value) <= maximum) and all(
        isinstance(item, str) for item in value
    )


def parse_response(family: str, suite: str, raw: str) -> tuple[str, str, str | None]:
    text = raw.strip()
    if family in CHOICE_FAMILIES:
        valid = "ABCD" if family == "visual_multiple_choice_qa" else ("ABCDEFG" if family == "moral_classification" else "AB")
        if suite == "P1":
            parsed = strict_json(text)
            answer = str((parsed or {}).get("answer", "")).strip().upper()
            expected_keys = {"visible_evidence", "uncertainty", "answer"}
            if (
                parsed is not None
                and set(parsed) == expected_keys
                and string_list(parsed["visible_evidence"], maximum=3)
                and isinstance(parsed["uncertainty"], str)
                and parsed["uncertainty"] in {"none", "low", "high"}
                and answer in valid
                and len(answer) == 1
            ):
                return answer, "strict_ok", None
        if re.fullmatch(f"[{valid}]", text, flags=re.IGNORECASE):
            return text.upper(), "strict_ok", None
        matches = re.findall(rf"(?<![A-Z])([{valid}])(?![A-Z])", text.upper())
        if len(set(matches)) == 1:
            return matches[0], "lenient_only", "response did not match the strict output format"
        return "", "failed", "could not extract exactly one valid option"
    if family == VULCA_FAMILY:
        parsed = strict_json(text) if suite == "P1" else None
        source = parsed.get("labels", []) if parsed else text
        found_labels = sorted(set(re.findall(r"[A-Z]+_L5_D\d+", render_value(source).upper())))
        if not found_labels:
            return "", "failed", "no valid L5 labels found"
        if suite == "P1":
            valid_json = (
                parsed is not None
                and set(parsed) == {"textual_evidence", "labels"}
                and string_list(parsed["textual_evidence"])
                and string_list(parsed["labels"])
                and all(re.fullmatch(r"[A-Z]+_L5_D\d+", label.upper()) for label in parsed["labels"])
            )
            status = "strict_ok" if valid_json else "lenient_only"
            error = None if valid_json else "response did not match the strict P1 JSON schema"
        else:
            strict_labels = r"[A-Z]+_L5_D\d+(?:；[A-Z]+_L5_D\d+)*"
            valid_text = bool(re.fullmatch(strict_labels, text.upper()))
            status = "strict_ok" if valid_text else "lenient_only"
            error = None if valid_text else "response did not match the strict label-only format"
        return "；".join(found_labels), status, error
    if family == HL_FAMILY:
        if suite == "P1":
            parsed = strict_json(text)
            rationale = str((parsed or {}).get("rationale", "")).strip()
            valid_json = (
                parsed is not None
                and set(parsed) == {"scene", "action", "objects", "visible_evidence", "rationale", "uncertainty"}
                and all(isinstance(parsed[key], str) for key in ("scene", "action", "rationale"))
                and string_list(parsed["objects"])
                and string_list(parsed["visible_evidence"])
                and isinstance(parsed["uncertainty"], str)
                and parsed["uncertainty"] in {"none", "low", "high"}
                and bool(rationale)
            )
            if valid_json:
                return rationale, "strict_ok", None
            return rationale or text, "lenient_only", "response did not match the strict P1 JSON schema"
        return text, "strict_ok" if text else "failed", None if text else "empty response"
    raise EvaluationError(f"unsupported family: {family}")


def resolve_image(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = (ROOT / path_value).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise EvaluationError(f"image path escapes repository: {path_value}") from exc
    if not candidate.is_file():
        raise EvaluationError(f"image file not found: {path_value}")
    return candidate


def make_shuffled_paths(records: list[dict[str, Any]], seed: int) -> dict[str, str]:
    output: dict[str, str] = {}
    by_family: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record["input"]["image"].get("path"):
            by_family.setdefault(record["task"]["family"], []).append(record)
    for family, items in by_family.items():
        if len(items) < 2:
            raise EvaluationError(f"shuffled_image needs at least two image records in {family}")
        ordered = sorted(items, key=lambda item: item["id"])
        paths = [item["input"]["image"]["path"] for item in ordered]
        shift = random.Random(f"{seed}:{family}").randrange(1, len(paths))
        shifted = paths[shift:] + paths[:shift]
        output.update({item["id"]: path for item, path in zip(ordered, shifted)})
    return output


def max_tokens_for(family: str, suite: str, override: int | None) -> int:
    if override:
        return override
    if family in CHOICE_FAMILIES:
        return 16 if suite == "P0" else 256
    if family == HL_FAMILY:
        return 256 if suite == "P0" else 384
    return 128 if suite == "P0" else 384


def effective_condition(family: str, requested: str) -> str:
    if family == VULCA_FAMILY:
        return "text_only_native"
    if family == HL_FAMILY and requested == "correct_image":
        return "context_removed"
    return requested


def build_adapter(args: argparse.Namespace) -> Adapter:
    if args.provider == "mock":
        return MockAdapter()
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise EvaluationError(f"environment variable {args.api_key_env} is empty")
    if args.provider == "openai-compatible":
        return OpenAICompatibleAdapter(args, api_key)
    if args.provider == "openai-responses":
        return OpenAIResponsesAdapter(args, api_key)
    if args.provider == "anthropic":
        return AnthropicAdapter(args, api_key)
    if args.provider == "gemini":
        return GeminiAdapter(args, api_key)
    raise EvaluationError(f"unknown provider: {args.provider}")


def default_base_url(provider: str) -> str:
    return {
        "openai-compatible": "https://api.openai.com/v1",
        "openai-responses": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "mock": "mock://local",
    }[provider]


def parse_families(value: str) -> list[str]:
    if value == "multimodal":
        return MULTIMODAL_FAMILIES
    if value == "all":
        return ALL_FAMILIES
    families = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(families) - set(ALL_FAMILIES))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown task families: {unknown}")
    return families


def optional_float(value: str) -> float | None:
    if value.lower() in {"none", "null", "omit"}:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a number or 'none'") from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run PHILBENCH-3000 through common multimodal model APIs.")
    result.add_argument("--provider", choices=("openai-compatible", "openai-responses", "anthropic", "gemini", "mock"), required=True)
    result.add_argument("--model", required=True, help="Exact API model ID; avoid rolling aliases for paper results")
    result.add_argument("--api-key-env", default=None, help="Environment variable containing the API key")
    result.add_argument("--base-url", default=None, help="API base URL; OpenAI-compatible vendors can use their own endpoint")
    result.add_argument("--split", choices=("dev", "test"), default="dev")
    result.add_argument("--families", type=parse_families, default=MULTIMODAL_FAMILIES, help="multimodal, all, or comma-separated family names")
    result.add_argument("--prompt-suite", choices=("P0", "P1"), default="P0")
    result.add_argument("--prompt-id", default=None, help="Override automatic prompt selection; recommended only for one family")
    result.add_argument("--language", choices=("en", "zh"), default="en")
    result.add_argument("--condition", choices=("correct_image", "text_only", "shuffled_image", "hl_gold_context"), default="correct_image")
    result.add_argument("--vulca-codebook", type=Path, default=None)
    result.add_argument("--limit", type=int, default=None, help="Pilot only; first N selected records")
    result.add_argument("--workers", type=int, default=1)
    result.add_argument("--max-retries", type=int, default=3)
    result.add_argument("--timeout", type=float, default=120.0)
    result.add_argument("--temperature", type=optional_float, default=0.0, help="Number, or 'none' to omit")
    result.add_argument("--top-p", type=optional_float, default=1.0, help="Number, or 'none' to omit")
    result.add_argument("--seed", type=int, default=42, help="Benchmark randomization seed (for shuffled_image)")
    result.add_argument("--api-seed", type=int, default=None, help="Optional provider generation seed")
    result.add_argument("--max-output-tokens", type=int, default=None)
    result.add_argument("--max-tokens-field", choices=("max_tokens", "max_completion_tokens"), default="max_tokens")
    result.add_argument("--reasoning-setting", default=None)
    result.add_argument("--image-detail", choices=("auto", "low", "high", "omit"), default="auto")
    result.add_argument("--anthropic-version", default="2023-06-01")
    result.add_argument("--run-id", default=None)
    result.add_argument("--output-dir", type=Path, default=None)
    result.add_argument("--input-price-per-million", type=float, default=None)
    result.add_argument("--output-price-per-million", type=float, default=None)
    return result


def resolve_api_key_env(args: argparse.Namespace) -> str:
    if args.api_key_env:
        return args.api_key_env
    return {
        "openai-compatible": "OPENAI_API_KEY",
        "openai-responses": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "mock": "MOCK_API_KEY",
    }[args.provider]


def run_one(
    record: dict[str, Any],
    args: argparse.Namespace,
    adapter: Adapter,
    catalog: dict[str, dict[str, Any]],
    codebook_en: str,
    codebook_zh: str,
    shuffled: dict[str, str],
) -> dict[str, Any]:
    family = record["task"]["family"]
    item_condition = effective_condition(family, args.condition)
    prompt_id = choose_prompt_id(family, args.prompt_suite, args.language, args.condition, args.prompt_id)
    if prompt_id not in catalog:
        raise EvaluationError(f"prompt not found: {prompt_id}")
    prompt_spec = catalog[prompt_id]
    if family not in prompt_spec["applies_to"]:
        raise EvaluationError(f"prompt {prompt_id} does not apply to {family}")
    prompt = render_prompt(record, prompt_spec["template"], args.language, codebook_en, codebook_zh)
    item_max_tokens = max_tokens_for(family, args.prompt_suite, args.max_output_tokens)

    image_path_value = record["input"]["image"].get("path")
    if args.condition == "text_only" or family == VULCA_FAMILY:
        image_path_value = None
    elif args.condition == "shuffled_image":
        image_path_value = shuffled.get(record["id"])
    image_path = resolve_image(image_path_value)
    image = None
    image_hash = None
    if image_path:
        media_type, encoded, image_hash = image_payload(image_path)
        image = (media_type, encoded)

    started = time.perf_counter()
    last_error: str | None = None
    generated: GenerationResult | None = None
    attempts = 0
    for attempt in range(args.max_retries + 1):
        attempts = attempt
        try:
            generated = adapter.generate(prompt, image, item_max_tokens)
            break
        except ApiError as exc:
            last_error = str(exc)
            if attempt == args.max_retries:
                break
            time.sleep(min(2**attempt, 8))
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    if generated is None:
        return {
            "id": record["id"],
            "run_id": args.run_id,
            "family": family,
            "prompt_id": prompt_id,
            "condition": item_condition,
            "language": args.language,
            "max_output_tokens": item_max_tokens,
            "prediction": "",
            "raw_response": None,
            "parse_status": "failed",
            "parse_error": None,
            "refusal": False,
            "api_failure": True,
            "failure_type": last_error,
            "latency_ms": latency_ms,
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
            "retry_count": attempts,
            "provider_request_id": None,
            "image_sha256": image_hash,
            "timestamp_utc": utc_now(),
        }

    refusal = is_refusal(generated.text)
    prediction, parse_status, parse_error = parse_response(family, args.prompt_suite, generated.text)
    if refusal:
        prediction = ""
        parse_status = "failed"
        parse_error = "refusal"
    cost = None
    if generated.input_tokens is not None and generated.output_tokens is not None:
        if args.input_price_per_million is not None and args.output_price_per_million is not None:
            cost = round(
                generated.input_tokens * args.input_price_per_million / 1_000_000
                + generated.output_tokens * args.output_price_per_million / 1_000_000,
                8,
            )
    return {
        "id": record["id"],
        "run_id": args.run_id,
        "family": family,
        "prompt_id": prompt_id,
        "condition": item_condition,
        "language": args.language,
        "max_output_tokens": item_max_tokens,
        "prediction": prediction,
        "raw_response": generated.text,
        "parse_status": parse_status,
        "parse_error": parse_error,
        "refusal": refusal,
        "api_failure": False,
        "failure_type": None,
        "latency_ms": latency_ms,
        "input_tokens": generated.input_tokens,
        "output_tokens": generated.output_tokens,
        "cost_usd": cost,
        "retry_count": attempts,
        "provider_request_id": generated.request_id,
        "image_sha256": image_hash,
        "timestamp_utc": utc_now(),
    }


def main() -> None:
    args = parser().parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    args.api_key_env = resolve_api_key_env(args)
    args.base_url = args.base_url or default_base_url(args.provider)
    prompt_payload, catalog = prompt_catalog()
    args.system_prompt = prompt_payload["common_system"]
    codebook_en, codebook_zh = read_codebook(args.vulca_codebook)

    if VULCA_FAMILY in args.families and not args.vulca_codebook:
        raise SystemExit("VULCA is disabled until a published L5 codebook is supplied with --vulca-codebook")
    if args.language == "zh":
        unsupported = set(args.families) - {HL_FAMILY, "visual_multiple_choice_qa", VULCA_FAMILY}
        if unsupported:
            raise SystemExit(f"the dataset has no native Chinese prompt for: {sorted(unsupported)}")
    if args.condition == "hl_gold_context" and set(args.families) != {HL_FAMILY}:
        raise SystemExit("hl_gold_context requires --families scene_action_rationale")

    query = load_json(QUERY_PATH)
    records = [record for record in query if record["split"] == args.split and record["task"]["family"] in args.families]
    records.sort(key=lambda record: record["id"])
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise SystemExit("no records selected")

    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.model).strip("-")
    args.run_id = args.run_id or f"{stamp}_{safe_model}_{args.prompt_suite}_{args.condition}_{args.language}"
    output_dir = (args.output_dir or ROOT / "outputs" / "evaluation" / args.run_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    predictions_path = output_dir / "predictions.jsonl"
    manifest_path = output_dir / "run_manifest.json"

    shuffled = make_shuffled_paths(records, args.seed) if args.condition == "shuffled_image" else {}
    adapter = build_adapter(args)
    manifest = {
        "run_id": args.run_id,
        "benchmark_version": "3000-image-rich-v5",
        "benchmark_commit": git_commit() or "0000000",
        "query_sha256": sha256_path(QUERY_PATH),
        "answer_key_sha256": None,
        "code_commit": git_commit(),
        "provider": args.provider,
        "model_id": args.model,
        "model_snapshot_date": None,
        "access_mode": "local" if args.provider == "mock" or "localhost" in args.base_url else "api",
        "endpoint_region": None,
        "prompt_id": args.prompt_id or f"{args.prompt_suite}-auto",
        "prompt_ids_by_family": {
            family: choose_prompt_id(family, args.prompt_suite, args.language, args.condition, args.prompt_id)
            for family in args.families
        },
        "prompt_file_sha256": sha256_path(PROMPTS_PATH),
        "split": args.split,
        "condition": args.condition,
        "conditions_by_family": {family: effective_condition(family, args.condition) for family in args.families},
        "language": args.language,
        "generation": {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "seed": args.api_seed,
            "max_output_tokens": args.max_output_tokens or max(max_tokens_for(f, args.prompt_suite, None) for f in args.families),
            "reasoning_setting": args.reasoning_setting,
        },
        "image_policy": {
            "original_bytes": True,
            "resize_policy": None,
            "provider_detail_setting": (
                None
                if args.image_detail == "omit" or args.provider not in {"openai-compatible", "openai-responses"}
                else args.image_detail
            ),
        },
        "tools_disabled": True,
        "max_retries": args.max_retries,
        "timeout_seconds": args.timeout,
        "software_environment": {"python": sys.version.split()[0], "runner": "scripts/run_models.py"},
        "hardware_environment": None,
        "started_at_utc": utc_now(),
        "ended_at_utc": None,
        "total_input_tokens": None,
        "total_output_tokens": None,
        "total_cost_usd": None,
        "protocol_deviations": ([f"pilot limit={args.limit}"] if args.limit is not None else []),
    }
    atomic_json(manifest_path, manifest)

    print(f"Run: {args.run_id}")
    print(f"Selected: {len(records)} records; provider={args.provider}; model={args.model}")
    completed: list[dict[str, Any]] = []
    try:
        with predictions_path.open("w", encoding="utf-8", newline="\n") as stream:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(run_one, record, args, adapter, catalog, codebook_en, codebook_zh, shuffled): record
                    for record in records
                }
                for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                    record = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        raise EvaluationError(f"{record['id']}: {exc}") from exc
                    completed.append(result)
                    stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                    stream.flush()
                    if index == 1 or index % 10 == 0 or index == len(records):
                        print(f"Completed {index}/{len(records)}")
    finally:
        manifest["ended_at_utc"] = utc_now()
        manifest["total_input_tokens"] = sum(item["input_tokens"] or 0 for item in completed)
        manifest["total_output_tokens"] = sum(item["output_tokens"] or 0 for item in completed)
        costs = [item["cost_usd"] for item in completed if item["cost_usd"] is not None]
        manifest["total_cost_usd"] = round(sum(costs), 8) if costs else None
        atomic_json(manifest_path, manifest)

    failures = sum(item["api_failure"] for item in completed)
    parse_failures = sum(item["parse_status"] == "failed" for item in completed)
    print(f"Saved: {predictions_path}")
    print(f"API failures: {failures}; parse/refusal failures: {parse_failures}")


if __name__ == "__main__":
    try:
        main()
    except EvaluationError as exc:
        raise SystemExit(str(exc)) from exc
