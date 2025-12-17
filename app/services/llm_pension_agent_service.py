from typing import List, Generator
import os
import logging

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.schemas.llm_chat import ChatMessage


SYSTEM_PROMPT = """אתה יועץ פנסיוני ומתכנן פרישה חכם. תפקידך לנתח את מצב הלקוח ולבנות עבורו אסטרטגיה אופטימלית להשגת יעדי הפרישה שלו (קצבה חודשית נטו והון פנוי).

## 🛠️ הנחיות להפעלת כלים (Tools) - חובה!
המערכת שלך עובדת במודל "סוכן עצמאי". הנתונים לא מחושבים אוטומטית יותר. עליך להחליט מתי להפעיל כלי!

## 📄 חוק בלעדי להפקת דוחות/מסמכים (MANDATORY)
כאשר המשתמש מבקש דוח/מסמך/PDF/קישור להורדה:
- חובה להפעיל כלי מסוג GENERATE_* (ובפרט GENERATE_FULL_REPORT לדוח פרישה מלא).
- אסור לכתוב דוח בעצמך ואסור לטעון "הופק דוח" אם לא הופעל כלי כזה ואם לא התקבל download_url או open_path מהמערכת.
- לאחר הצלחה, הפלט המרכזי למשתמש חייב להיות קישור ההורדה (download_url) או פתיחת הדוח בממשק (open_path).

1. **זיהוי צורך**: אם השאלה דורשת מידע שאינו ב-State או דורשת חישוב חדש - **הפעל כלי**.
2. **פורמט הפעלה**: כדי להפעיל כלי, עליך להחזיר בתשובתך בלוק JSON מיוחד בפורמט:
`###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {"arg_name": "value"}}`

**אכיפה קריטית - איסור ניחוש:**
לפני מענה לשאלה פיננסית הדורשת חישוב או ניתוח נתונים (כגון 'השוואה', 'כמה צריך למשוך', 'מהו הנטו'), עליך תמיד להפעיל את אחד מכלי הניתוח הרלוונטיים.
**אין להשיב ניתוח מספרי או המלצה פיננסית ללא הפעלת כלי קודם לכן. אסור לחלוטין לנחש מספרים או להסתמך על אינטואיציה.**
לאחר כל הודעת משתמש חדשה, התגובה הראשונה המותרת היא אחת משתי אפשרויות בלבד: (1) בלוק יחיד של `###TOOL_CALL### {"name": "TOOL_NAME", "arguments": {...}}` ללא טקסט נוסף; או (2) תשובה סופית מלאה במבנה הנדרש, ורק אם כל המספרים מבוססים על תוצאות כלים קיימות שנשלחו לך כהודעות system.
אם השאלה דורשת השוואה בין תרחישים (כמו פרישה ב-2028 מול 2029), עליך לפרק את השאלה לשתי קריאות כלים עוקבות ולאחר מכן לסכם בטבלת השוואה.

3. **חוקי שימוש בכלים**:
   - **BUILD_TARGET_PENSION_PLAN**: הפעל תמיד כשנדרש תכנון קצבה או משיכה. חובה לספק `target_monthly_pension`. אם המשתמש לא סיפק יעד, הנח 70% מהשכר או בקש ממנו.
   - **GET_TAX_PROJECTION**: הפעל רק לאחר שיש לך קצבה ברוטו (למשל מתוצאת התכנון או ניתוח התזרים). אל תנחש מס! כאשר המשתמש שואל על "נטו", "אחרי מס", "ביד" או "נקי", חובה להשתמש בתוצאת כלי זה כדי להסביר במפורש את ההכנסה החודשית נטו.

**דגש לניתוח נטו (אחרי מס):** כאשר המשתמש שואל במפורש על "נטו", "אחרי מס", "ביד" או "נקי" והופעל הכלי GET_TAX_PROJECTION, עליך לוודא כי:
- בבולטים שאחרי הטבלה אתה מציין במילים פשוטות וברורות מהי ההכנסה החודשית נטו המשוערת בכל תרחיש (לאחר מס).
- במסקנה הסופית אתה מדגיש לא רק את ההבדל בברוטו אלא גם את ההבדל בנטו – כמה כסף צפוי להישאר ללקוח ביד בכל חודש בכל תרחיש.

**כלל שרשור מחייב:** כאשר אתה מריץ שני כלי ניתוח או יותר ברצף לצורך השוואה (לדוגמה, השוואת פרישה בשנת 2028 מול 2029), אסור לך להגיב מילולית או לכתוב קטע "🤖 Analysis" לאחר כל קריאת כלי בודדת או בין קריאות הכלים. עליך:
- לאחר קריאת הכלי הראשון – להחזיר *רק* בלוק `###TOOL_CALL###` עבור הכלי הבא, ללא טקסט נוסף (ללא "שלום", ללא הסברים ביניים וללא מספרים).
- להימנע מכל ניסוח ביניים עד שכל קריאות הכלים הרציפות הושלמו.

המענה המילולי ללקוח (כולל טבלת ההשוואה והמסקנה הסופית) יינתן **רק פעם אחת** לאחר שכל התוצאות מכל הכלים הרלוונטיים להשוואה זמינות בקונטקסט.

**דרישת סיום מחייבת (מבנה היררכי):** בתום כל קריאות הכלים הדרושות להשוואה, חובה עליך לסיים את התשובה באופן מיידי ללא כל קריאת כלי נוספת. הפלט הסופי חייב להיות בנוי במדויק בסדר הבא:

1. **כותרת ניתוח (H2):** כותרת Markdown ברורה בעברית (למשל: `## ניתוח תרחישי פרישה לפי הנתונים הפיננסיים`).
2. **טבלת השוואה:** טבלת Markdown מלאה בעברית. כברירת מחדל, כותרות העמודות הן: "הכנסה חודשית מובטחת" (ברוטו), "הון נזיל זמין", ו-"כמה שנים יספיק ההון?". כאשר שאלת המשתמש עוסקת בנטו/אחרי מס, עליך להוסיף בטבלה גם עמודה "הכנסה חודשית נטו משוערת" ולהבהיר בכותרת הקיימת שהיא ברוטו (למשל: "הכנסה חודשית מובטחת ברוטו").
3. **רשימת ממצאים (Bullet Points):** רשימה של 2 עד 3 בולטים (ולא יותר) שמדגישה ממצאים מרכזיים שאינם מופיעים ישירות בטבלה (למשל הנחות תשואה, משמעות הפער בין התרחישים, או רמת הביטחון הכלכלי), ובשאלות נטו – גם הבדל משמעותי בהכנסה נטו.
4. **מסקנה סופית:** פסקה אחת קצרה ואמפתית המסכמת את ההמלצה או המשמעות הפרקטית עבור הלקוח, כולל ניסוח ברור של כמה צפוי להישאר לו נטו ביד (כאשר השאלה עסקה בנטו).

לעולם אל תכלול קטעי JSON גולמיים או טקסט טכני שאינו חלק מהניסוח הרשמי הזה עבור הלקוח.

## מבנה תשובה רצוי
1. הבנת השאלה וזיהוי נתונים חסרים.
2. החלטה על הפעלת כלי (אם צריך) -> פלט `###TOOL_CALL###`.
3. אם אין צורך בכלי -> תשובה מילולית מלאה על בסיס הקונטקסט.

זכור: אתה המוח המתכנן. אל תחכה שהמערכת תעבוד בשבילך. יזום פעולות!
"""


logger = logging.getLogger("app.llm_pension_agent")


class PensionLLMService:
    """שירות שיחה עם מודל LLM עבור יועץ פנסיוני."""

    def __init__(self) -> None:
        """מאתחל את שירות ה-LLM.

        ברירת המחדל היא שימוש ב-Ollama המקומי.
        ניתן לבחור בספק Gemini או Anthropic באמצעות משתנה הסביבה PENSION_LLM_PROVIDER.
        """
        self._provider: str = "ollama"
        self._llm: ChatOllama | None = None
        self._gemini_client = None
        self._gemini_model: str | None = None
        self._anthropic_client = None
        self._anthropic_model: str | None = None
        self._ollama_model_name: str | None = None

        # זיהוי ספק מבוקש ממשתנה סביבה (ברירת מחדל: Ollama מקומי)
        desired_provider = os.getenv("PENSION_LLM_PROVIDER", "ollama").lower()

        # Ollama – ברירת מחדל בטוחה שלא צורכת מכסת API חיצונית
        # אם המשתמש הגדיר PENSION_LLM_MODEL בשילוב ספק ollama – נשתמש בו.
        # אם הספק הוא ענני (gemini/anthropic) – נשמור על מודל מקומי ברירת מחדל ל-Ollama.
        # שימוש ב-gemma3:4b כברירת מחדל כי יש לו תמיכה טובה יותר בעברית
        if desired_provider == "ollama":
            ollama_model_name = os.getenv("PENSION_LLM_MODEL", "gemma3:4b")
        else:
            ollama_model_name = "gemma3:4b"

        self._ollama_model_name = ollama_model_name
        self._llm = ChatOllama(
            model=ollama_model_name,
            base_url="http://localhost:11434",
            temperature=0.2,
        )
        logger.info("PensionLLMService initialized with Ollama model '%s'", ollama_model_name)

        # ניסיון לעבור לספק חיצוני אם התבקש במפורש
        if desired_provider == "gemini":
            try:
                # הלקוח יקרא את המפתח ממשתנה הסביבה GEMINI_API_KEY
                from google import genai  # type: ignore[import]

                self._gemini_client = genai.Client()

                # אם PENSION_LLM_MODEL הוגדר ומתאים ל-Gemini (מתחיל ב-"gemini-") נשתמש בו,
                # אחרת נשתמש בברירת המחדל gemini-2.5-flash.
                env_model = os.getenv("PENSION_LLM_MODEL")
                if env_model and env_model.startswith("gemini-"):
                    gemini_model = env_model
                else:
                    gemini_model = "gemini-2.5-flash"

                self._gemini_model = gemini_model
                self._provider = "gemini"
                logger.info(
                    "PensionLLMService initialized with Gemini model '%s'", self._gemini_model
                )
            except Exception as e:  # pragma: no cover - הגנה מפני כשלי ספרייה חיצונית
                # במקרה של בעיה ב-Gemini נופלים חזרה ל-Ollama
                self._provider = "ollama"
                self._gemini_client = None
                self._gemini_model = None
                logger.warning(
                    "Failed to initialize Gemini provider, falling back to Ollama: %s",
                    e,
                )
        elif desired_provider == "anthropic":
            try:
                # הלקוח יקרא את המפתח ממשתנה הסביבה ANTHROPIC_API_KEY
                from anthropic import Anthropic  # type: ignore[import]

                self._anthropic_client = Anthropic()

                # אם PENSION_LLM_MODEL הוגדר ומתאים ל-Anthropic (מתחיל ב-"claude-") נשתמש בו,
                # אחרת נשתמש בברירת המחדל claude-3-haiku-20240307.
                env_model = os.getenv("PENSION_LLM_MODEL")
                if env_model and env_model.startswith("claude-"):
                    anthropic_model = env_model
                else:
                    anthropic_model = "claude-3-haiku-20240307"

                self._anthropic_model = anthropic_model
                self._provider = "anthropic"
                logger.info(
                    "PensionLLMService initialized with Anthropic model '%s'",
                    self._anthropic_model,
                )
            except Exception as e:  # pragma: no cover - הגנה מפני כשלי ספרייה חיצונית
                # במקרה של בעיה ב-Anthropic נופלים חזרה ל-Ollama
                self._provider = "ollama"
                self._anthropic_client = None
                self._anthropic_model = None
                logger.warning(
                    "Failed to initialize Anthropic provider, falling back to Ollama: %s",
                    e,
                )

    def _build_history(self, messages: List[ChatMessage]) -> List[BaseMessage]:
        history: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history.append(AIMessage(content=msg.content))
            elif msg.role == "system":
                # הודעות system מקורן בקוד השרת (לא מהמשתמש), ולכן בטוח לקדם אותן כהנחיות נוספות
                history.append(SystemMessage(content=msg.content))
        return history

    def _prepare_history(self, messages: List[ChatMessage], client_id: int | None = None) -> List[BaseMessage]:
        """מכין את היסטוריית השיחה עבור המודל."""
        history = self._build_history(messages)
        if client_id is not None:
            history.insert(
                1,
                SystemMessage(
                    content=f"מספר לקוח: {client_id}."
                ),
            )
        return history

    def _history_to_prompt(self, history: List[BaseMessage]) -> str:
        """ממיר היסטוריית הודעות לטקסט פשוט עבור Gemini."""
        lines: list[str] = []
        for msg in history:
            if isinstance(msg, SystemMessage):
                prefix = "System"
            elif isinstance(msg, HumanMessage):
                prefix = "User"
            elif isinstance(msg, AIMessage):
                prefix = "Assistant"
            else:
                prefix = "Message"
            lines.append(f"{prefix}: {msg.content}")
        return "\n\n".join(lines)

    def get_status(self) -> dict[str, str | None]:
        """מחזיר מידע על ספק ה-LLM והמודל הפעיל לצורך חיווי ב-UI."""
        provider = self._provider
        model_name: str | None

        if provider == "gemini":
            model_name = self._gemini_model
        elif provider == "anthropic":
            model_name = self._anthropic_model
        else:
            model_name = self._ollama_model_name

        backend: str
        if provider == "gemini":
            backend = "Gemini"
        elif provider == "anthropic":
            backend = "Anthropic"
        else:
            backend = "Ollama"

        return {
            "provider": provider,
            "backend": backend,
            "model_name": model_name,
        }

    def set_provider(self, provider: str, model_name: str | None = None) -> dict[str, str | None]:
        """מחליף ספק/מודל LLM בזמן ריצה.

        במקרה של כישלון בהחלפת ספק נשמרת התצורה הקודמת ומועלה חריג.
        מחזיר את מצב הספק לאחר ההחלפה (או לאחר חזרה לאחור במקרה תקלה).
        """

        normalized = (provider or "").strip().lower()
        if normalized not in {"ollama", "gemini", "anthropic"}:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        previous_provider = self._provider
        previous_llm = self._llm
        previous_ollama_model = self._ollama_model_name
        previous_gemini_client = self._gemini_client
        previous_gemini_model = self._gemini_model
        previous_anthropic_client = self._anthropic_client
        previous_anthropic_model = self._anthropic_model

        try:
            if normalized == "ollama":
                # אם התקבל model_name נשתמש בו, אחרת נשתמש במודל הנוכחי או ברירת מחדל מקומית
                effective_model = model_name or self._ollama_model_name or "gemma3:4b"
                self._ollama_model_name = effective_model
                self._llm = ChatOllama(
                    model=effective_model,
                    base_url="http://localhost:11434",
                    temperature=0.2,
                )
                self._provider = "ollama"
                logger.info("PensionLLMService switched to Ollama model '%s'", effective_model)

            elif normalized == "gemini":
                from google import genai  # type: ignore[import]

                self._gemini_client = genai.Client()
                self._gemini_model = model_name or os.getenv(
                    "PENSION_LLM_MODEL",
                    "gemini-2.5-flash",
                )
                self._provider = "gemini"
                logger.info(
                    "PensionLLMService switched to Gemini model '%s'",
                    self._gemini_model,
                )

            elif normalized == "anthropic":
                from anthropic import Anthropic  # type: ignore[import]

                self._anthropic_client = Anthropic()
                self._anthropic_model = model_name or os.getenv(
                    "PENSION_LLM_MODEL",
                    "claude-3-haiku-20240307",
                )
                self._provider = "anthropic"
                logger.info(
                    "PensionLLMService switched to Anthropic model '%s'",
                    self._anthropic_model,
                )

        except Exception as e:  # pragma: no cover - הגנה מפני כשלי ספרייה חיצונית
            # החזרה לתצורה הקודמת במקרה של תקלה
            self._provider = previous_provider
            self._llm = previous_llm
            self._ollama_model_name = previous_ollama_model
            self._gemini_client = previous_gemini_client
            self._gemini_model = previous_gemini_model
            self._anthropic_client = previous_anthropic_client
            self._anthropic_model = previous_anthropic_model
            logger.error("Failed to switch LLM provider to %s, reverting to previous config: %s", provider, e)
            raise RuntimeError(f"Failed to switch LLM provider to {provider}: {e}") from e

        return self.get_status()

    def _chat_gemini(self, history: List[BaseMessage]) -> str:
        """שולח את ההיסטוריה למודל Gemini ומחזיר טקסט תשובה אחד."""
        if not self._gemini_client or not self._gemini_model:
            raise RuntimeError("Gemini client is not initialized")

        prompt = self._history_to_prompt(history)
        try:
            response = self._gemini_client.models.generate_content(  # type: ignore[union-attr]
                model=self._gemini_model,
                contents=prompt,
            )
        except Exception as e:  # pragma: no cover - תקלה בספק חיצוני
            logger.error("Gemini generate_content failed, falling back to Ollama: %s", e)
            # כיבוי Gemini לשאר חיי הפרוסס כדי למנוע ניסיונות כושלים חוזרים
            self._provider = "ollama"
            self._gemini_client = None
            self._gemini_model = None
            if self._llm is not None:
                ai_message = self._llm.invoke(history)
                return ai_message.content
            raise

        text = getattr(response, "text", None)
        if not text:
            text = str(response)
        return text

    def _chat_anthropic(self, history: List[BaseMessage]) -> str:
        """שולח את ההיסטוריה למודל Claude (Anthropic) ומחזיר טקסט תשובה אחד."""
        if not self._anthropic_client or not self._anthropic_model:
            raise RuntimeError("Anthropic client is not initialized")

        prompt = self._history_to_prompt(history)
        try:
            response = self._anthropic_client.messages.create(  # type: ignore[union-attr]
                model=self._anthropic_model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
        except Exception as e:  # pragma: no cover - תקלה בספק חיצוני
            logger.error("Anthropic messages.create failed, falling back to Ollama: %s", e)
            if self._llm is not None:
                ai_message = self._llm.invoke(history)
                return ai_message.content
            raise

        # שליפת טקסט מהתשובה
        text_parts: list[str] = []
        content = getattr(response, "content", None)
        if content:
            for block in content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    block_text = getattr(block, "text", None)
                    if block_text:
                        text_parts.append(block_text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    if "text" in block:
                        text_parts.append(str(block["text"]))

        text = "".join(text_parts).strip()
        if not text:
            text = str(response)
        return text

    def chat(self, messages: List[ChatMessage], client_id: int | None = None) -> str:
        """מקבל היסטוריית צ'אט ומחזיר תשובת סוכן אחת."""
        history = self._prepare_history(messages, client_id)

        if self._provider == "gemini" and self._gemini_client is not None:
            return self._chat_gemini(history)

        if self._provider == "anthropic" and self._anthropic_client is not None:
            return self._chat_anthropic(history)

        if self._llm is None:
            raise RuntimeError("No LLM backend is configured")

        ai_message = self._llm.invoke(history)
        return ai_message.content

    def chat_stream(self, messages: List[ChatMessage], client_id: int | None = None) -> Generator[str, None, None]:
        """מקבל היסטוריית צ'אט ומחזיר תשובה בזרימה (streaming)."""
        history = self._prepare_history(messages, client_id)

        # עבור Gemini – מחזירים את כל התשובה כמקשה אחת
        if self._provider == "gemini" and self._gemini_client is not None:
            yield self._chat_gemini(history)
            return

        # עבור Anthropic – מחזירים את כל התשובה כמקשה אחת
        if self._provider == "anthropic" and self._anthropic_client is not None:
            yield self._chat_anthropic(history)
            return

        if self._llm is None:
            raise RuntimeError("No LLM backend is configured for streaming")

        for chunk in self._llm.stream(history):
            if chunk.content:
                yield chunk.content


pension_llm_service = PensionLLMService()
