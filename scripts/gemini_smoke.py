"""Explicit opt-in real Gemini verification with three fictional messages only."""

import asyncio

from app.config import Settings
from app.gemini import build_processor
from app.services import ProcessingFailure

MESSAGES = {
    "English": (
        "Fictional learning exercise: we need a website. Which requirements should we clarify?"
    ),
    "Urdu": "یہ فرضی تعلیمی مثال ہے۔ ہمیں ایک ویب سائٹ چاہیے۔ کون سی تفصیلات واضح کریں؟",
    "Roman Urdu": (
        "Yeh farzi taleemi misaal hai. Hamein website chahiye. Kin features ki wazahat karein?"
    ),
}


async def main() -> int:
    settings = Settings()
    if (
        settings.processor_mode != "gemini"
        or not settings.gemini_api_key.get_secret_value().strip()
    ):
        print(
            "Real Gemini verification NOT RUN: explicitly enable Gemini mode "
            "and configure a server-side key."
        )
        return 0
    processor, timeout = build_processor(settings)
    for language, message in MESSAGES.items():
        try:
            await asyncio.wait_for(processor.process(message), timeout=timeout)
        except ProcessingFailure as exc:
            print(f"Real Gemini verification FAILED ({language}): {exc.code}. No automatic retry.")
            return 1
        except TimeoutError:
            print("Real Gemini verification FAILED: timeout. No automatic retry.")
            return 1
        except Exception:
            print("Real Gemini verification FAILED: sanitized unexpected provider error.")
            return 1
        print(f"{language}: valid structured result; manual review still required.")
    print(
        "Real Gemini verification PASSED: three fictional requests; "
        "no enquiries saved or replies sent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
