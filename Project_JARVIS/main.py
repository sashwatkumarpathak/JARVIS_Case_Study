import time
import os
import tempfile

import speech_recognition as sr
from gtts import gTTS
import pygame
from deep_translator import GoogleTranslator

# ----------- CUSTOM MADE MODULES -----------

import commands
from voice_mod import (
    apply_voice_effects,
    set_voice,
    reset_voice,
    nudge_speed,
    nudge_pitch,
    toggle_echo,
    toggle_robotic,
    save_current_voice,
    load_voice,
    list_presets,
    describe_settings,
    get_current_settings,
)
import app_indexer

# ---------- CONFIG ----------
WAKE_WORD = "jarvis"
SESSION_TIMEOUT = 30  # seconds after last command before session ends

# ---------- STATE ----------
active_session = False
last_active_time = 0

# ---------- LANGUAGE CONFIG (OUTPUT LANGUAGE) ----------
CURRENT_LANG_CODE = "en"
CURRENT_LANG_NAME = "English"

LANGUAGE_MAP = {
    "english": "en",
    "hindi": "hi",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "japanese": "ja",
    "korean": "ko",
    "telugu": "te",
    "tamil": "ta",
    "bengali": "bn",
    "marathi": "mr"
    }

# ---------- STT LANGUAGE MAP (speech_recognition language codes) ----------
# This decides which language Google STT listens in, based on CURRENT_LANG_CODE
STT_LANGUAGE_MAP = {
    "en": "en-IN",  # English (India)
    "hi": "hi-IN",  # Hindi
    "te": "te-IN",  # Telugu
    "ta": "ta-IN",  # Tamil
    "bn": "bn-IN",  # Bengali
    "mr": "mr-IN",  # Marathi
    "fr": "fr-FR",  # French
    "es": "es-ES",  # Spanish
    "de": "de-DE",  # German
    "ja": "ja-JP",  # Japanese
    "ko": "ko-KR",  # Korean
}


def get_stt_language_code() -> str:
    """
    Returns the language code for Google STT based on CURRENT_LANG_CODE.
    Fallback is 'en-IN'.
    """
    return STT_LANGUAGE_MAP.get(CURRENT_LANG_CODE, "en-IN")


# ---------- AUDIO INIT ----------
pygame.mixer.init()


def tts_play(text: str, lang_code: str):
    """
    Use gTTS + pygame to play speech in the given language,
    then run the audio through voice_mod.apply_voice_effects before playback.
    """
    original_path = None
    modulated_path = None

    try:
        # Create a temp mp3 file for the raw gTTS output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            original_path = fp.name

        # Generate TTS audio
        tts = gTTS(text=text, lang=lang_code)
        tts.save(original_path)

        # Apply voice modulation effects (pitch, speed, echo, etc.)
        modulated_path = apply_voice_effects(original_path)

        # Play the modulated audio
        pygame.mixer.music.load(modulated_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.05)

        pygame.mixer.music.unload()

    except Exception as e:
        print("[TTS ERROR]", e)

    finally:
        # Clean up temp files
        if original_path and os.path.exists(original_path):
            try:
                os.remove(original_path)
            except Exception as e:
                print("[CLEANUP ERROR] original_path:", e)

        if modulated_path and os.path.exists(modulated_path):
            try:
                os.remove(modulated_path)
            except Exception as e:
                print("[CLEANUP ERROR] modulated_path:", e)


def speak(text: str):
    """
    Speak text in CURRENT_LANG_CODE.
    - Internal text is assumed English.
    - If CURRENT_LANG_CODE != 'en', translate response first.
    - Audio passes through voice_mod for pitch/speed/effects.
    """
    global CURRENT_LANG_CODE, CURRENT_LANG_NAME
    print(f"[ASSISTANT ({CURRENT_LANG_NAME})]: {text}")
    try:
        if CURRENT_LANG_CODE == "en":
            tts_play(text, "en")
        else:
            translated = GoogleTranslator(source="auto", target=CURRENT_LANG_CODE).translate(text)
            print(f"[ASSISTANT RAW {CURRENT_LANG_NAME}]: {translated}")
            tts_play(translated, CURRENT_LANG_CODE)
    except Exception as e:
        print("[SPEAK ERROR]", e)


# ---------- INPUT NORMALIZATION: ANY LANGUAGE -> ENGLISH ----------
def to_english(text: str) -> str:
    """
    Convert any recognized text to English for internal processing.
    This is your 'backend always English' layer.
    """
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(text)
        print(f"[CMD EN]: {translated}")
        return translated
    except Exception as e:
        print("[CMD TRANSLATE ERROR]", e)
        # Fallback: just return original text
        return text


# ---------- LANGUAGE SWITCHING (OUTPUT) ----------
def handle_language_change(cmd_en: str, speak_fn) -> bool:
    """
    cmd_en: command already normalized to English
    Detect things like:
      "speak in hindi", "switch language to french", "talk in telugu"
    and update CURRENT_LANG_CODE / NAME.
    """
    global CURRENT_LANG_CODE, CURRENT_LANG_NAME

    lower = cmd_en.lower()
    trigger_phrases = ["speak in", "switch language to", "change language to", "talk in"]
    if not any(p in lower for p in trigger_phrases):
        return False  # not a language change command

    for name, code in LANGUAGE_MAP.items():
        if name in lower:
            CURRENT_LANG_CODE = code
            CURRENT_LANG_NAME = name.capitalize()
            speak_fn(f"Okay, I will speak in {CURRENT_LANG_NAME} from now on.")
            return True

    speak_fn("I did not understand which language to switch to.")
    return True  # we did detect a language-intent, even if failed


# ---------- COMMAND HANDLER (ALWAYS GETS ENGLISH) ----------
def handle_command(command_en: str):
    """
    command_en: already translated to English via to_english()
    """
    global active_session, last_active_time

    cmd = command_en.lower().strip()

    # Remove wake word at the start if present
    if cmd.startswith(WAKE_WORD):
        cmd = cmd[len(WAKE_WORD):].strip()

    if not cmd:
        return

    print(f"[COMMAND EN]: {cmd}")

    # 1) language change (output language)
    if handle_language_change(cmd, speak):
        last_active_time = time.time()
        return

    # 2) exit / stop
    if "exit" in cmd or "quit" in cmd or "goodbye" in cmd:
        speak("Goodbye! Have a nice day.")
        active_session = False
        raise SystemExit

    if "stop listening" in cmd or "shut down" in cmd:
        speak("Okay, I will stop listening now.")
        active_session = False
        raise SystemExit

    # 3) delegate to commands.py (which expects English)
    commands.execute_command(cmd, speak)
    last_active_time = time.time()


# ---------- MAIN LOOP ----------
def main():
    global active_session, last_active_time

    r = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("Calibrating for ambient noise... please wait.")
        r.adjust_for_ambient_noise(source, duration=1)
        print(f"Energy threshold set to: {r.energy_threshold}")

    # Optional: ensure neutral voice on startup
    reset_voice()

    speak(f"Jarvis online. My current language is {CURRENT_LANG_NAME}. Say '{WAKE_WORD}' to wake me up.")

    while True:
        with mic as source:
            print(f"Listening... (STT language = {get_stt_language_code()})")
            audio = r.listen(source)

        try:
            # recognition language follows CURRENT_LANG_CODE
            text_raw = r.recognize_google(audio, language=get_stt_language_code())
            print(f"[YOU RAW]: {text_raw}")
        except sr.UnknownValueError:
            print("Didn't catch that.")
            continue
        except sr.RequestError:
            print("[ERROR] Network issue with Google Speech API")
            continue

        now = time.time()
        lower_raw = text_raw.lower()

        # Normalize entire user utterance to English for backend logic
        text_en = to_english(text_raw)

        # 1) Wake word
        if WAKE_WORD in lower_raw:
            active_session = True
            last_active_time = now

            # In English version as well, strip 'jarvis' if present
            lower_en = text_en.lower()
            if WAKE_WORD in lower_en:
                rest_en = lower_en.split(WAKE_WORD, 1)[1].strip()
            else:
                rest_en = text_en

            speak("Yes?")
            if rest_en:
                handle_command(rest_en)
            continue

        # 2) If in active session, treat as command (in English)
        if active_session:
            if now - last_active_time > SESSION_TIMEOUT:
                print("[SESSION] Timed out. Say the wake word again.")
                active_session = False
                continue

            handle_command(text_en)

        # 3) If not in session, ignore random speech
        else:
            print("[INFO] Not in active session, ignoring speech.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        print("Jarvis has shut down.")
