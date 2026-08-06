"""
Skill: Translator
=================
Translate text between languages using deep-translator with Google Translate.

Requires: pip install deep-translator
"""

from __future__ import annotations

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

COMMON_LANGUAGES = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "japanese": "ja",
    "chinese": "zh-CN",
    "korean": "ko",
    "arabic": "ar",
    "hindi": "hi",
    "turkish": "tr",
    "dutch": "nl",
    "polish": "pl",
    "swedish": "sv",
    "thai": "th",
    "vietnamese": "vi",
    "indonesian": "id",
    "czech": "cs",
    "romanian": "ro",
    "greek": "el",
    "hebrew": "he",
    "finnish": "fi",
    "norwegian": "no",
    "danish": "da",
    "hungarian": "hu",
    "malay": "ms",
    "ukrainian": "uk",
}

LANG_BY_CODE = {v: k for k, v in COMMON_LANGUAGES.items()}

_translator_cls = None
_import_error: str | None = None


def _load_translator():
    global _translator_cls, _import_error
    if _translator_cls is not None or _import_error is not None:
        return
    try:
        from deep_translator import GoogleTranslator

        _translator_cls = GoogleTranslator
    except ImportError as e:
        _import_error = str(e)


def _resolve_lang_code(name: str) -> str | None:
    lower = name.strip().lower()
    if lower in COMMON_LANGUAGES:
        return COMMON_LANGUAGES[lower]
    if lower in LANG_BY_CODE:
        return lower
    if lower in {v.lower(): v for v in COMMON_LANGUAGES.values()}:
        return {v.lower(): v for v in COMMON_LANGUAGES.values()}[lower]
    return None


class TranslatorSkill(BaseSkill):
    metadata = SkillMetadata(
        name="translator",
        version="1.0.0",
        description="Translate text between languages using Google Translate",
        author="JARVIS Team",
        tags=["translate", "language", "i18n"],
    )

    async def on_initialize(self) -> None:
        _load_translator()

    async def execute(self, context: SkillContext) -> SkillResult:
        if _translator_cls is None:
            return SkillResult(
                success=False,
                error=f"deep-translator is not installed. Run: pip install deep-translator\nDetails: {_import_error}",
            )

        text = context.parameters.get("text", context.user_input.strip())
        if not text:
            return SkillResult(success=False, error="No text provided to translate.")

        target = context.parameters.get("target", "english")
        source = context.parameters.get("source", "auto")

        target_code = _resolve_lang_code(target)
        if target_code is None:
            return SkillResult(
                success=False,
                error=f"Unknown target language '{target}'. Supported: {', '.join(COMMON_LANGUAGES.keys())}",
            )

        source_code = "auto"
        if source.lower() != "auto":
            source_code = _resolve_lang_code(source)
            if source_code is None:
                return SkillResult(
                    success=False,
                    error=f"Unknown source language '{source}'. Supported: {', '.join(COMMON_LANGUAGES.keys())}",
                )

        try:
            if source_code == "auto":
                translator = _translator_cls(target=target_code)
            else:
                translator = _translator_cls(source=source_code, target=target_code)

            result = translator.translate(text)

            target_label = LANG_BY_CODE.get(target_code, target_code)
            source_label = "auto-detected" if source_code == "auto" else LANG_BY_CODE.get(source_code, source_code)

            return SkillResult(
                success=True,
                output=result,
                metadata={
                    "source_lang": source_label,
                    "target_lang": target_label,
                    "original": text,
                },
            )
        except Exception as e:
            return SkillResult(
                success=False,
                error=f"Translation failed: {e}",
            )
