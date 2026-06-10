"""Role-aware DeepSeek chat service for the local agent."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import httpx

from app.agent.schemas import AiChatResponse

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEEPSEEK_MODEL_ENV = "DEEPSEEK_MODEL"
DEEPSEEK_TIMEOUT_ENV = "DEEPSEEK_TIMEOUT_SECONDS"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_USER_PROFILE = "trash_sorter_user"
DEFAULT_ADMIN_PROFILE = "trash_sorter_admin"
DEFAULT_SAFETY_NOTICE = (
    "Gợi ý từ trợ lý chỉ để tham khảo thêm trong quá trình sử dụng EcoSort AI."
)
DEEPSEEK_KEY_SETUP_MESSAGE = (
    "Chưa cấu hình DeepSeek. Gắn key ở backend local agent bằng DEEPSEEK_API_KEY, ví dụ: "
    '$env:DEEPSEEK_API_KEY="sk-..."; powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1. '
    "Nếu dùng file env local, điền DEEPSEEK_API_KEY trong .env.local rồi khởi động lại agent."
)
USER_ASSISTANT_UNAVAILABLE_MESSAGE = (
    "EcoPet đang dùng gợi ý có sẵn trong ứng dụng. Bạn vẫn có thể xem biểu đồ, lịch sử rác "
    "và thử hỏi lại sau khi trợ lý trực tuyến."
)

AdminOrUser = Literal["admin", "user"]

ADMIN_QUICK_PROMPTS = [
    "Tóm tắt hệ thống hôm nay",
    "Thiết bị nào đang bất thường?",
    "Vì sao confidence AI thấp?",
    "Tóm tắt hoạt động 30 ngày",
]
USER_QUICK_PROMPTS = [
    "Hôm nay bạn thế nào?",
    "Hôm nay mình bỏ rác gì?",
    "Có thói quen nào nên giảm không?",
    "Eco Score của mình ổn không?",
]


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float


def build_chat_response(
    *,
    role: AdminOrUser,
    message: str,
    context: dict[str, object],
    profile: str | None = None,
    knowledge_snippets: Sequence[Mapping[str, str]] | None = None,
    conversation_style: str = "",
) -> AiChatResponse:
    cfg = _config()
    clean_profile = profile or (DEFAULT_ADMIN_PROFILE if role == "admin" else DEFAULT_USER_PROFILE)
    quick_prompts = ADMIN_QUICK_PROMPTS if role == "admin" else USER_QUICK_PROMPTS
    knowledge = _knowledge_payload(knowledge_snippets)
    knowledge_used = [item["title"] for item in knowledge if item["title"]]
    if not cfg.api_key:
        return AiChatResponse(
            generated_at=datetime.now().isoformat(),
            available=False,
            provider="deepseek",
            model=cfg.model,
            role=role,
            profile=clean_profile,
            message=DEEPSEEK_KEY_SETUP_MESSAGE if role == "admin" else USER_ASSISTANT_UNAVAILABLE_MESSAGE,
            quick_prompts=quick_prompts,
            knowledge_used=knowledge_used,
            safety_notice=DEFAULT_SAFETY_NOTICE,
        )
    try:
        answer = _call_deepseek(
            cfg,
            role=role,
            message=message.strip(),
            context=context,
            profile=clean_profile,
            knowledge=knowledge,
            conversation_style=conversation_style,
        )
    except httpx.TimeoutException:
        answer = (
            "DeepSeek phản hồi quá lâu. Hãy thử lại sau vài giây."
            if role == "admin"
            else "EcoPet phản hồi hơi chậm. Bạn thử lại sau vài giây nhé."
        )
        available = False
    except httpx.HTTPStatusError as exc:
        answer = _status_message(exc.response.status_code, role)
        available = False
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, IndexError):
        answer = (
            "Không thể kết nối DeepSeek lúc này. Hệ thống vẫn giữ dữ liệu local an toàn."
            if role == "admin"
            else "EcoPet chưa kết nối được lúc này. Bạn vẫn có thể xem biểu đồ và lịch sử rác bình thường."
        )
        available = False
    else:
        available = bool(answer)
        if not answer:
            answer = (
                "DeepSeek chưa trả về nội dung. Hãy thử lại với câu hỏi cụ thể hơn."
                if role == "admin"
                else "EcoPet chưa nhận được câu trả lời. Bạn thử hỏi ngắn hơn một chút nhé."
            )
    answer = _polish_answer(answer, role)
    return AiChatResponse(
        generated_at=datetime.now().isoformat(),
        available=available,
        provider="deepseek",
        model=cfg.model,
        role=role,
        profile=clean_profile,
        message=answer,
        quick_prompts=quick_prompts,
        knowledge_used=knowledge_used,
        safety_notice=DEFAULT_SAFETY_NOTICE,
    )


def _call_deepseek(
    cfg: DeepSeekConfig,
    *,
    role: AdminOrUser,
    message: str,
    context: dict[str, object],
    profile: str,
    knowledge: list[dict[str, str]],
    conversation_style: str,
) -> str:
    body = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": _system_prompt(role, profile, conversation_style)},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": message, "profile": profile, "knowledge": knowledge, "context": context},
                    ensure_ascii=False,
                ),
            },
        ],
        "thinking": {"type": "disabled"},
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 520,
    }
    with httpx.Client(timeout=cfg.timeout_s) as client:
        res = client.post(
            f"{cfg.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
            json=body,
        )
        res.raise_for_status()
        payload = res.json()
    return str(payload["choices"][0]["message"]["content"]).strip()


def _system_prompt(role: AdminOrUser, profile: str, conversation_style: str) -> str:
    shared_rules = (
        " Quy tắc bắt buộc: trả lời bằng tiếng Việt có dấu; không dùng Markdown thô, không dùng ký hiệu **, ##, ```; "
        "mỗi ý viết thành câu ngắn dễ đọc trong popup chat; tối đa 5 ý chính; nếu cần checklist thì dùng dòng bắt đầu bằng dấu •. "
        "Luôn gọi đúng tên tab trong web hiện tại: Giám sát, Lịch sử, Dữ liệu, Mapping, Cài đặt, Nhật ký, Tài khoản, Báo cáo. "
        "Nếu dữ liệu context thiếu, nói rõ là chưa có dữ liệu thay vì bịa số liệu. "
        "Không nhắc user gửi ảnh, path, token, mật khẩu, raw log hoặc file nhạy cảm. "
        "Không tự nhận là model chung; hãy trả lời như trợ lý EcoSort AI đã được cấu hình riêng cho dự án này."
    )
    if role == "admin":
        base = (
            "Bạn là trợ lý AI cho Admin của hệ thống phân loại rác tự động EcoSort AI. "
            "Profile hiện tại là {profile}. Chỉ phân tích dữ liệu tổng hợp đã được cung cấp: "
            "thống kê rác, thiết bị, confidence, trạng thái vận hành và log summary đã sanitize. "
            "Đây là trợ lý riêng cho dự án Trash Sorter Pro: phải dùng knowledge snippets như bộ nhớ chuyên môn "
            "của dự án, ưu tiên các tab hiện có gồm camera live, dataset, mapping, settings, logs, hardware test, accounts. "
            "Trả lời như kỹ sư vận hành đang hỗ trợ trực tiếp trên web: nêu tình trạng, nguyên nhân có thể, bước kiểm tra ngắn gọn và hành động an toàn. "
            "Ưu tiên cấu trúc chuyên nghiệp: Tình trạng hiện tại, việc nên kiểm tra, hành động tiếp theo. "
            "Không yêu cầu xóa dữ liệu, đổi quyền, tự ý thay đổi hệ thống, hoặc tiết lộ bí mật."
        )
    else:
        base = (
            "Bạn là trợ lý AI cá nhân cho người dùng EcoSort AI. Profile hiện tại là {profile}. "
            "Chỉ tư vấn dựa trên dữ liệu của tài khoản hiện tại và knowledge snippets được cung cấp. "
            "Đây là trợ lý riêng cho app phân loại rác: phải giải thích theo 3 thùng O/R/I, Eco Score, "
            "lịch sử rác của người dùng và trạng thái thiết bị local. "
            "Giải thích biểu đồ, Eco Score, lịch sử rác, và đưa lời khuyên phân loại rác thực tế bằng tiếng Việt thân thiện. "
            "Không dùng câu hỏi quá chuyên môn với User; ưu tiên câu hỏi đời thường như hôm nay bạn bỏ gì, thói quen nào có thể cải thiện, Eco Score đang ổn không. "
            "Nếu dữ liệu gần đây cho thấy nhiều chai nhựa, lon, ly nhựa hoặc bao bì đồ uống, hãy nói thân thiện theo kiểu: "
            "'Hôm nay bạn bỏ khá nhiều chai/lon đồ uống; nếu đó là nước ngọt, dùng thường xuyên có thể không tốt cho sức khỏe. "
            "Bạn thử giảm dần, uống thêm nước lọc hoặc dùng bình cá nhân nhé.' "
            "Chỉ dùng câu 'nếu đó là nước ngọt' khi dữ liệu không xác nhận rõ là nước ngọt; không được bịa tên đồ uống. "
            "Có thể gợi ý thói quen sống chung như giảm đồ dùng một lần, nhưng không chẩn đoán bệnh, "
            "không đưa lời khuyên y tế cá nhân, và không tiết lộ dữ liệu người khác."
        )
    style = conversation_style.strip()
    suffix = f" Phong cách trả lời: {style}" if style else ""
    return base.format(profile=profile) + shared_rules + suffix


def _knowledge_payload(snippets: Sequence[Mapping[str, str]] | None) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for item in snippets or []:
        payload.append(
            {
                "id": _clean_field(item.get("id", "")),
                "title": _clean_field(item.get("title", "")),
                "text": _clean_field(item.get("text", ""), limit=700),
            }
        )
    return payload[:6]


def _polish_answer(answer: str, role: AdminOrUser) -> str:
    """Keep DeepSeek replies compact and product-native before they reach the UI."""
    text = answer.strip()
    if not text:
        return text
    replacements = {
        "Camera Live": "Giám sát",
        "Hardware Test": "Cài đặt > Kiểm tra phần cứng",
        "Settings": "Cài đặt",
        "Logs": "Nhật ký",
        "Dataset": "Dữ liệu",
        "History": "Lịch sử",
        "Accounts": "Tài khoản",
        "Reports": "Báo cáo",
        "AI confidence": "độ tin cậy AI",
        "confidence": "độ tin cậy",
        "dashboard": "bảng điều khiển",
    }
    for raw, label in replacements.items():
        text = re.sub(re.escape(raw), label, text, flags=re.IGNORECASE)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        clean = line.strip()
        if not clean:
            continue
        clean = re.sub(r"^\s*[-*]\s+", "• ", clean)
        lines.append(clean)
    max_lines = 7 if role == "admin" else 5
    return "\n".join(lines[:max_lines]).strip()


def _clean_field(value: object, *, limit: int = 120) -> str:
    return " ".join(str(value or "").split())[:limit]


def _status_message(status_code: int, role: AdminOrUser) -> str:
    if role == "user":
        if status_code == 429:
            return "EcoPet đang có nhiều lượt hỏi. Bạn thử lại sau một chút nhé."
        return "EcoPet chưa sẵn sàng trả lời lúc này. Bạn vẫn có thể xem biểu đồ và lịch sử rác."
    if status_code == 401:
        return "DeepSeek từ chối API key. Hãy kiểm tra DEEPSEEK_API_KEY."
    if status_code == 429:
        return "DeepSeek đang giới hạn quota hoặc tốc độ gọi. Hãy thử lại sau."
    if status_code >= 500:
        return "DeepSeek đang lỗi phía dịch vụ. Hãy thử lại sau."
    return "DeepSeek trả về lỗi. Hãy kiểm tra cấu hình model/base URL."


def _config() -> DeepSeekConfig:
    return DeepSeekConfig(
        api_key=os.getenv(DEEPSEEK_API_KEY_ENV, "").strip(),
        base_url=os.getenv(DEEPSEEK_BASE_URL_ENV, DEFAULT_DEEPSEEK_BASE_URL).strip()
        or DEFAULT_DEEPSEEK_BASE_URL,
        model=_model(),
        timeout_s=_timeout_s(),
    )


def _model() -> str:
    return DEFAULT_DEEPSEEK_MODEL


def _timeout_s() -> float:
    try:
        return max(1.0, min(float(os.getenv(DEEPSEEK_TIMEOUT_ENV, "30")), 120.0))
    except ValueError:
        return 30.0


def deepseek_available() -> bool:
    return bool(os.getenv(DEEPSEEK_API_KEY_ENV, "").strip())


__all__ = [
    "ADMIN_QUICK_PROMPTS",
    "DEEPSEEK_API_KEY_ENV",
    "DEEPSEEK_BASE_URL_ENV",
    "DEEPSEEK_KEY_SETUP_MESSAGE",
    "DEEPSEEK_MODEL_ENV",
    "DEFAULT_ADMIN_PROFILE",
    "DEFAULT_DEEPSEEK_BASE_URL",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEFAULT_USER_PROFILE",
    "USER_QUICK_PROMPTS",
    "build_chat_response",
    "deepseek_available",
]
