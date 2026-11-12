"""Local AI Chat — локальный чат-интерфейс для Ollama.

Тёмная тема в стиле ChatGPT, история чатов, контекст из файлов (RAG),
экспорт диалога, размышления DeepSeek-R1.

Запуск:  streamlit run app.py
Сервер Ollama ожидается на http://localhost:11434 (переопределяется через OLLAMA_URL).
"""

from __future__ import annotations

import io
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

# --------------------------------------------------------------------------
# Конфигурация
# --------------------------------------------------------------------------
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "deepseek-r1:7b")

APP_DIR = Path(__file__).resolve().parent
CHATS_DIR = APP_DIR / "chats"
CHATS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = ["txt", "py", "md", "pdf"]
MAX_CONTEXT_CHARS = 12_000  # сколько символов из файлов уходит в контекст
MAX_FILE_CHARS = 60_000  # больше не читаем из одного файла
NUM_CTX = 8192  # контекстное окно модели при работе с файлами

APP_TITLE = "Local AI Chat"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🖤",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Стили: тёмная тема, пузыри справа/слева, поле ввода снизу
# --------------------------------------------------------------------------
st.markdown(
    """
<style>
:root {
    --bg: #0f0f11;
    --bg-elev: #17171a;
    --bubble-assistant: #17171a;
    --bubble-user: #2563eb;
    --border: #26262b;
    --text: #ececf1;
    --muted: #9aa0a6;
}

/* ---------- общий фон ---------- */
.stApp, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
}
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
    background: transparent;
    display: none !important;
}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 6rem !important;
    max-width: 860px;
}

/* ---------- шапка ---------- */
.chat-header {
    display: flex; align-items: center; gap: 12px;
    padding: 6px 4px 18px 4px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 18px;
}
.chat-header .logo {
    width: 38px; height: 38px; border-radius: 11px;
    background: linear-gradient(135deg, #2f6feb, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-size: 19px;
}
.chat-header h1 { font-size: 1.15rem; margin: 0; font-weight: 600; letter-spacing: .2px; }
.chat-header .sub { font-size: .78rem; color: var(--muted); margin-top: 2px; }
.status-pill {
    margin-left: auto; font-size: .72rem; padding: 4px 10px;
    border-radius: 999px; border: 1px solid var(--border);
    color: var(--muted); white-space: nowrap;
}
.status-pill.on  { color: #7ee787; border-color: #1f6f3f; background: #0f2a1a; }
.status-pill.off { color: #ff7b72; border-color: #6e2a2a; background: #2a1214; }
.status-pill .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: currentColor; margin-right: 6px; vertical-align: middle; }

/* ---------- сообщения ---------- */
[data-testid="stChatMessage"] {
    background: var(--bubble-assistant);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 14px 18px;
    margin-bottom: 14px;
    max-width: 92%;
    display: flex;
    gap: 12px;
    align-items: flex-start;
    animation: fadeIn .18s ease-out;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* сообщения пользователя — справа, акцентный пузырь */
[data-testid="stChatMessage"]:has(.ua-marker) {
    flex-direction: row-reverse;
    margin-left: auto;
    background: var(--bubble-user);
    border-color: #3b7ff0;
    color: #fff;
}
[data-testid="stChatMessage"]:has(.ua-marker) p,
[data-testid="stChatMessage"]:has(.ua-marker) li,
[data-testid="stChatMessage"]:has(.ua-marker) strong { color: #fff; }
[data-testid="stChatMessage"]:has(.ua-marker) a { color: #dbeafe; }

/* аватар */
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
    border-radius: 10px; flex: 0 0 auto;
}

[data-testid="stChatMessageContent"] { overflow-wrap: anywhere; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0; }

/* ---------- блоки кода ---------- */
[data-testid="stChatMessage"] pre,
[data-testid="stCode"] { border-radius: 12px !important; }

/* ---------- размышления модели ---------- */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    background: #121215 !important;
}
[data-testid="stExpander"] summary { color: var(--muted) !important; font-size: .84rem; }

/* ---------- поле ввода снизу ---------- */
[data-testid="stBottom"] > div { background: transparent; }
[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 65%, transparent); }
[data-testid="stChatInput"] {
    background: #1a1a1e;
    border: 1px solid #303036;
    border-radius: 16px;
    box-shadow: 0 8px 28px rgba(0,0,0,.45);
}
[data-testid="stChatInput"] textarea {
    color: var(--text) !important;
    font-size: .95rem;
}
[data-testid="stChatInput"] textarea::placeholder { color: #6b7280 !important; }
[data-testid="stChatInputSubmitButton"] { color: #9aa0a6; }

/* ---------- сайдбар ---------- */
[data-testid="stSidebar"] {
    background: #0b0b0d;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text); }
[data-testid="stSidebar"] h2 { font-size: .95rem; margin-bottom: .4rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .35rem; }

/* карточка чата в истории */
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    text-align: left; justify-content: flex-start;
    font-size: .82rem; padding: .35rem .6rem; min-height: 2rem;
}

/* ---------- прочее ---------- */
.stButton > button {
    background: #1c1c20; color: var(--text);
    border: 1px solid #303036; border-radius: 10px;
}
.stButton > button:hover { background: #26262b; border-color: #3a3a42; color: #fff; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #2563eb; border-color: #2563eb; color: #fff;
}
code { background: #1b1b1f !important; color: #ffb86c !important; }
pre { background: #121215 !important; border: 1px solid var(--border); border-radius: 12px; }
hr { border-color: var(--border); }

/* файлы-вложения */
.file-chip {
    display: flex; justify-content: space-between; align-items: center;
    background: #131316; border: 1px solid var(--border); border-radius: 10px;
    padding: 6px 10px; margin-bottom: 6px; font-size: .78rem;
}
.file-chip .meta { color: var(--muted); font-size: .7rem; }
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Ollama API
# --------------------------------------------------------------------------
def api_get(path: str, timeout: float = 4.0):
    return requests.get(f"{OLLAMA_URL}{path}", timeout=timeout)


def server_alive() -> bool:
    try:
        return api_get("/api/version", timeout=2.0).ok
    except requests.RequestException:
        return False


def fetch_models() -> list[str]:
    """Список моделей из Ollama (без кеша — обновляется кнопкой)."""
    try:
        data = api_get("/api/tags", timeout=5.0).json()
        return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
    except (requests.RequestException, ValueError):
        return []


def stream_chat(model: str, messages: list[dict], temperature: float, context_chars: int = 0):
    """Генератор (thinking_chunk, content_chunk) из потокового ответа /api/chat."""
    options: dict = {"temperature": temperature}
    if context_chars:
        options["num_ctx"] = NUM_CTX

    payload = {"model": model, "messages": messages, "stream": True, "options": options}
    with requests.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=(10, 900)) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            try:
                chunk = json.loads(raw)
            except ValueError:
                continue
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            msg = chunk.get("message") or {}
            thinking = msg.get("thinking") or ""
            content = msg.get("content") or ""
            if thinking or content:
                yield thinking, content
            if chunk.get("done"):
                break


def split_think(text: str) -> tuple[str, str]:
    """Разделяет  thinking...<｜end▁of▁thinking｜> (DeepSeek-R1) на размышления и ответ."""
    if "<｜end▁of▁thinking｜>" in text:
        head, tail = text.split("<｜end▁of▁thinking｜>", 1)
        return head.replace(" thinking", "").strip(), tail.strip()
    if " thinking" in text:
        return text.replace(" thinking", "").strip(), ""
    return "", text


# --------------------------------------------------------------------------
# Работа с файлами (RAG)
# --------------------------------------------------------------------------
def extract_text(name: str, data: bytes) -> str:
    """Достаёт текст из загруженного файла."""
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                pages.append(f"\n--- страница {i} ---\n" + (page.extract_text() or ""))
            except Exception:  # noqa: BLE001 - повреждённая страница не должна ломать чат
                continue
        return "".join(pages).strip()

    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def build_context(docs: list[dict]) -> str:
    """Склеивает тексты файлов в единый контекст с ограничением по размеру."""
    if not docs:
        return ""
    parts, used = [], 0
    for doc in docs:
        text = doc["text"][:MAX_FILE_CHARS]
        header = f"\n\n===== Файл: {doc['name']} =====\n"
        room = MAX_CONTEXT_CHARS - used - len(header)
        if room <= 0:
            parts.append(f"\n\n(…файл «{doc['name']}» не поместился в контекст…)")
            continue
        chunk = text[:room]
        if len(chunk) < len(text):
            chunk += "\n…(файл обрезан)"
        parts.append(header + chunk)
        used += len(header) + len(chunk)
    return "".join(parts)


def compose_system_prompt(user_prompt: str, docs: list[dict]) -> str:
    context = build_context(docs)
    if not context:
        return user_prompt.strip()
    base = user_prompt.strip() or "Ты — полезный ассистент."
    return (
        f"{base}\n\n"
        "Ниже — содержимое файлов, которые пользователь приложил к диалогу. "
        "Отвечай на вопросы, опираясь в первую очередь на этот текст, "
        "и ссылайся на имена файлов.\n"
        f"{context}"
    )


# --------------------------------------------------------------------------
# История чатов: ./chats/<ГГГГ-ММ-ДД_ЧЧ-ММ-СС>.json
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _chat_file(chat_id: str) -> Path:
    return CHATS_DIR / f"{chat_id}.json"


def _new_chat_id() -> str:
    base = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chat_id, n = base, 1
    while _chat_file(chat_id).exists():
        n += 1
        chat_id = f"{base}_{n}"
    return chat_id


def empty_chat() -> dict:
    return {
        "id": _new_chat_id(),
        "created_at": _now(),
        "updated_at": _now(),
        "title": "Новый чат",
        "model": DEFAULT_MODEL,
        "messages": [],
    }


def chat_title(messages: list[dict]) -> str:
    for m in messages:
        if m.get("role") == "user" and m.get("content", "").strip():
            text = " ".join(m["content"].split())
            return text[:48] + ("…" if len(text) > 48 else "")
    return "Новый чат"


def save_chat(chat: dict) -> None:
    if not chat.get("messages"):
        return
    chat["updated_at"] = _now()
    chat["title"] = chat_title(chat["messages"])
    try:
        CHATS_DIR.mkdir(parents=True, exist_ok=True)
        _chat_file(chat["id"]).write_text(
            json.dumps(chat, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:  # диск/права — не роняем чат
        st.session_state.save_error = str(exc)


def load_chat(chat_id: str) -> dict | None:
    path = _chat_file(chat_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    data.setdefault("id", chat_id)
    data.setdefault("messages", [])
    data.setdefault("title", chat_title(data["messages"]))
    data.setdefault("created_at", chat_id.replace("_", " ")[:19])
    data.setdefault("updated_at", data["created_at"])
    return data


def delete_chat(chat_id: str) -> bool:
    path = _chat_file(chat_id)
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def list_chats() -> list[dict]:
    """Краткие данные всех сохранённых чатов, свежие сверху."""
    items = []
    for path in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        messages = data.get("messages") or []
        if not messages:
            continue
        items.append(
            {
                "id": path.stem,
                "title": data.get("title") or chat_title(messages),
                "updated_at": data.get("updated_at", ""),
                "count": len(messages),
            }
        )
    items.sort(key=lambda c: c["updated_at"], reverse=True)
    return items


# --------------------------------------------------------------------------
# Экспорт
# --------------------------------------------------------------------------
def chat_to_markdown(chat: dict) -> str:
    lines = [
        f"# {chat.get('title') or 'Чат'}",
        "",
        f"- **Создан:** {chat.get('created_at', '—')}",
        f"- **Модель:** {chat.get('model', DEFAULT_MODEL)}",
        f"- **Сообщений:** {len(chat.get('messages', []))}",
        "",
        "---",
        "",
    ]
    for m in chat.get("messages", []):
        who = "🧑 Вы" if m.get("role") == "user" else "🤖 Ассистент"
        lines.append(f"### {who}")
        lines.append("")
        if m.get("thinking"):
            lines.append("<details><summary>Размышления модели</summary>")
            lines.append("")
            lines.append(m["thinking"])
            lines.append("")
            lines.append("</details>")
            lines.append("")
        lines.append(m.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def chat_to_json(chat: dict) -> str:
    return json.dumps(chat, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Состояние приложения
# --------------------------------------------------------------------------
if "chat" not in st.session_state:
    st.session_state.chat = empty_chat()
if "docs" not in st.session_state:
    st.session_state.docs = []          # [{"name": str, "text": str}]
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = ""
if "models" not in st.session_state:
    st.session_state.models = []

alive = server_alive()
if alive and not st.session_state.models:
    st.session_state.models = fetch_models()

models = st.session_state.models
chat = st.session_state.chat

# --------------------------------------------------------------------------
# Сайдбар
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🖤 Local AI Chat")

    # ---------- новый чат ----------
    if st.button("➕ Новый чат", use_container_width=True, type="primary"):
        st.session_state.chat = empty_chat()
        st.rerun()

    # ---------- история ----------
    chats = list_chats()
    st.markdown("### 🕘 История")

    if not chats:
        st.caption("Пока пусто — задайте первый вопрос.")
    else:
        with st.container(height=210, border=False):
            for item in chats:
                is_current = item["id"] == chat["id"]
                col_open, col_del = st.columns([0.84, 0.16], gap="small")
                when = (item["updated_at"] or "")[5:16]  # ММ-ДД ЧЧ:ММ
                label = f"{'▸ ' if is_current else ''}{item['title']}"
                if col_open.button(
                    label,
                    key=f"open_{item['id']}",
                    use_container_width=True,
                    help=f"{item['updated_at']} · сообщений: {item['count']}",
                    disabled=is_current,
                ):
                    loaded = load_chat(item["id"])
                    if loaded:
                        st.session_state.chat = loaded
                        st.rerun()
                    else:
                        st.error("Не удалось прочитать файл чата.")
                if col_del.button("🗑", key=f"del_{item['id']}", help="Удалить этот чат"):
                    if delete_chat(item["id"]):
                        if is_current:
                            st.session_state.chat = empty_chat()
                        st.rerun()

    # ---------- удаление текущего ----------
    with st.popover("🗑 Удалить текущий чат", use_container_width=True):
        st.caption(f"«{chat.get('title') or 'Новый чат'}» будет удалён безвозвратно.")
        if st.button("Да, удалить", key="confirm_delete", type="primary", use_container_width=True):
            delete_chat(chat["id"])
            st.session_state.chat = empty_chat()
            st.rerun()

    # ---------- экспорт ----------
    st.markdown("### ⬇️ Экспорт")
    if chat.get("messages"):
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        safe_title = re.sub(r"[^\w\-]+", "_", chat.get("title", "chat"))[:40].strip("_") or "chat"
        st.download_button(
            "Скачать .md",
            data=chat_to_markdown(chat),
            file_name=f"{safe_title}_{stamp}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.download_button(
            "Скачать .json",
            data=chat_to_json(chat),
            file_name=f"{safe_title}_{stamp}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("Появится после первого сообщения.")

    st.divider()

    # ---------- модель ----------
    st.markdown("### ⚙️ Модель")
    if models:
        default_index = models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0
        if chat.get("model") in models:
            default_index = models.index(chat["model"])
        selected = st.selectbox("Модель", models, index=default_index)
        chat["model"] = selected
    else:
        selected = st.text_input("Модель", value=chat.get("model", DEFAULT_MODEL))
        chat["model"] = selected

    if st.button("🔄 Перезагрузить модели", use_container_width=True):
        with st.spinner("Обновляю список…"):
            st.session_state.models = fetch_models()
        st.rerun()

    st.session_state.temperature = st.slider(
        "Температура", 0.0, 1.5, st.session_state.temperature, 0.05
    )
    st.session_state.system_prompt = st.text_area(
        "Системный промпт",
        value=st.session_state.system_prompt,
        height=80,
        placeholder="Например: отвечай кратко и по делу.",
    )

    st.divider()

    # ---------- файлы ----------
    st.markdown("### 📎 Контекст из файлов")
    uploaded = st.file_uploader(
        "Файлы для контекста",
        type=SUPPORTED_EXTENSIONS,
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Текст файлов будет добавлен в системный промпт (txt, py, md, pdf).",
    )

    if uploaded:
        existing = {d["name"] for d in st.session_state.docs}
        for file in uploaded:
            if file.name in existing:
                continue
            try:
                text = extract_text(file.name, file.getvalue())
            except Exception as exc:  # noqa: BLE001
                st.error(f"{file.name}: не удалось прочитать ({exc})")
                continue
            if not text.strip():
                st.warning(f"{file.name}: текст не найден")
                continue
            st.session_state.docs.append({"name": file.name, "text": text})
            existing.add(file.name)

    if st.session_state.docs:
        for i, doc in enumerate(list(st.session_state.docs)):
            col_name, col_rm = st.columns([0.85, 0.15])
            col_name.markdown(
                f'<div class="file-chip"><span>📄 {doc["name"]}</span>'
                f'<span class="meta">{len(doc["text"]) / 1000:.1f}K</span></div>',
                unsafe_allow_html=True,
            )
            if col_rm.button("✕", key=f"rm_doc_{i}", help="Убрать файл"):
                st.session_state.docs.pop(i)
                st.rerun()
        total = len(build_context(st.session_state.docs))
        st.caption(f"В контекст уйдёт ≈{total / 1000:.1f}K символов (лимит {MAX_CONTEXT_CHARS / 1000:.0f}K).")
        if st.button("Очистить файлы", use_container_width=True):
            st.session_state.docs = []
            st.rerun()
    else:
        st.caption("Приложите .txt, .py, .md или .pdf — модель ответит по содержимому.")

    st.divider()
    # ---------- статус ----------
    if st.session_state.get("save_error"):
        st.caption(f"⚠️ История не сохранилась: {st.session_state.save_error}")
    if alive:
        try:
            version = (api_get("/api/version", 2.0).json() or {}).get("version", "?")
        except Exception:  # noqa: BLE001
            version = "?"
        st.caption(f"✅ Ollama {OLLAMA_URL} · v{version}")
        st.caption(f"Моделей доступно: {len(models)}")
    else:
        st.caption(f"⚠️ Ollama недоступен на {OLLAMA_URL}")
        st.code("ollama serve", language="bash")

if not alive:
    st.error(
        "Не удалось подключиться к Ollama на "
        f"`{OLLAMA_URL}`.\n\nЗапустите сервер командой `ollama serve` (или перезапустите ярлык "
        "«Local AI Chat» на рабочем столе)."
    )
    st.stop()

if not st.session_state.models:
    st.warning(
        f"Модель **{DEFAULT_MODEL}** ещё не загружена. Выполните в терминале:\n\n"
        f"```\nollama pull {DEFAULT_MODEL}\n```"
    )

# --------------------------------------------------------------------------
# Шапка
# --------------------------------------------------------------------------
files_note = f" · 📎 {len(st.session_state.docs)}" if st.session_state.docs else ""
st.markdown(
    f"""
<div class="chat-header">
  <div class="logo">💬</div>
  <div>
    <h1>{APP_TITLE}</h1>
    <div class="sub">{chat.get("model", DEFAULT_MODEL)} · только локально, без интернета{files_note}</div>
  </div>
  <div class="status-pill on"><span class="dot"></span>online</div>
</div>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Рендер сообщений
# --------------------------------------------------------------------------
FENCE_RE = re.compile(r"```([\w+-]*)[ \t]*\r?\n(.*?)(?:```|\Z)", re.DOTALL)


def render_markdown_with_code(text: str) -> None:
    """Markdown + подсветка блоков кода встроенным подсветчиком Streamlit."""
    if not text:
        return
    pos = 0
    for match in FENCE_RE.finditer(text):
        before = text[pos : match.start()]
        if before.strip():
            st.markdown(before)
        language = (match.group(1) or "").strip() or "text"
        st.code(match.group(2).rstrip("\n"), language=language)
        pos = match.end()
    rest = text[pos:]
    if rest.strip():
        st.markdown(rest)


def render_message(role: str, thinking: str, content: str) -> None:
    with st.chat_message(role, avatar="🧑" if role == "user" else "🤖"):
        if role == "user":
            st.markdown('<span class="ua-marker"></span>', unsafe_allow_html=True)
        if thinking:
            with st.expander("Размышления модели"):
                st.markdown(thinking)
        if content:
            render_markdown_with_code(content)


for message in chat["messages"]:
    render_message(message["role"], message.get("thinking", ""), message["content"])

# --------------------------------------------------------------------------
# Ввод и генерация
# --------------------------------------------------------------------------
prompt = st.chat_input("Спросите что-нибудь…")

if prompt:
    chat["messages"].append({"role": "user", "content": prompt, "thinking": ""})
    chat["title"] = chat_title(chat["messages"])
    render_message("user", "", prompt)

    system_prompt = compose_system_prompt(st.session_state.system_prompt, st.session_state.docs)
    history = [{"role": "system", "content": system_prompt}] if system_prompt else []
    history += [
        {"role": m["role"], "content": m["content"]}
        for m in chat["messages"]
        if m.get("content", "").strip()
    ]
    context_chars = len(build_context(st.session_state.docs))

    with st.chat_message("assistant", avatar="🤖"):
        think_box = st.expander("Размышления модели", expanded=True)
        think_slot = think_box.empty()
        answer_slot = st.empty()
        answer_slot.markdown("▌")

        think_acc, answer_acc = "", ""
        started = time.perf_counter()
        try:
            for thinking_chunk, content_chunk in stream_chat(
                chat.get("model", DEFAULT_MODEL),
                history,
                st.session_state.temperature,
                context_chars,
            ):
                if thinking_chunk:
                    think_acc += thinking_chunk
                    think_slot.markdown(think_acc)
                if content_chunk:
                    answer_acc += content_chunk
                    pure_think, pure_answer = split_think(answer_acc)
                    if pure_think and not think_acc:
                        think_slot.markdown(pure_think)
                    answer_slot.markdown(pure_answer + "▌")
        except requests.RequestException as exc:
            answer_slot.error(f"Ошибка запроса к Ollama: {exc}")
            st.stop()

        elapsed = time.perf_counter() - started
        pure_think, pure_answer = split_think(answer_acc)
        if pure_think:
            think_acc = pure_think
        if not pure_answer.strip():
            pure_answer = answer_acc.strip()

        if think_acc.strip():
            think_slot.markdown(think_acc)
        else:
            think_box.empty()
        answer_slot.empty()
        render_markdown_with_code(pure_answer or "_Пустой ответ модели._")

        tokens = max(1, len((pure_answer + think_acc).split()))
        st.caption(f"⏱ {elapsed:.1f} с · ≈{tokens / elapsed:.1f} слов/с")

    chat["messages"].append(
        {"role": "assistant", "content": pure_answer, "thinking": think_acc.strip()}
    )
    save_chat(chat)
    st.rerun()
