import os
import webbrowser
from datetime import datetime
import random
from deep_translator import GoogleTranslator  # NEW
from app_indexer import build_index

# ---------- VOICE MOD IMPORTS ----------
from voice_mod import (
    nudge_speed,
    nudge_pitch,
    toggle_echo,
    toggle_robotic,
    save_current_voice,
    load_voice,
    list_presets,
    reset_voice,
    describe_settings,
)

# ---------- APP SHORTCUTS ----------
APP_SHORTCUTS = {
    "notepad": "notepad.exe",
    "vs code": r"C:\Users\HP\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
}

# ---------- WEBSITE SHORTCUTS ----------
WEBSITE_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
}

# ---------- JOKES ----------
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "There are only 10 types of people in this world: those who understand binary and those who don't.",
    "My code never has bugs. It just develops random features.",
]

# ---------- LANGUAGE MAP (names -> codes) ----------
LANGUAGE_MAP = {
    "hindi": "hi",
    "english": "en",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "japanese": "ja",
    "korean": "ko",
    "telugu": "te",
    "tamil": "ta",
    "bengali": "bn",
    "marathi": "mr",
}

# =========================================================
# VOICE CONTROL HELPERS
# =========================================================

def _handle_voice_commands(cmd: str, speak) -> bool:
    """
    Handle voice-modulation related commands.
    Returns True if it handled the command, else False.
    """
    lower = cmd.lower()

    # ---- Speed: faster / slower ----
    if "speak faster" in lower or "talk faster" in lower or "increase speed" in lower:
        nudge_speed(faster=True)
        speak("Okay, I will speak a bit faster.")
        speak(describe_settings())
        return True

    if "speak slower" in lower or "talk slower" in lower or "decrease speed" in lower:
        nudge_speed(faster=False)
        speak("Okay, I will speak a bit slower.")
        speak(describe_settings())
        return True

    # ---- Pitch: higher / lower ----
    if "higher pitch" in lower or "increase pitch" in lower or "raise your pitch" in lower:
        nudge_pitch(higher=True)
        speak("Alright, I will use a slightly higher pitch.")
        speak(describe_settings())
        return True

    if (
        "lower pitch" in lower
        or "decrease pitch" in lower
        or "make your voice deeper" in lower
        or "deeper voice" in lower
    ):
        nudge_pitch(higher=False)
        speak("Okay, I will use a slightly deeper voice.")
        speak(describe_settings())
        return True

    # ---- Echo on/off ----
    if "turn on echo" in lower or "enable echo" in lower or "add echo" in lower:
        toggle_echo(True)
        speak("Echo effect enabled.")
        return True

    if "turn off echo" in lower or "disable echo" in lower or "remove echo" in lower:
        toggle_echo(False)
        speak("Echo effect disabled.")
        return True

    # ---- Robotic effect ----
    if (
        "robotic voice" in lower
        or "sound more robotic" in lower
        or "enable robot voice" in lower
        or "turn on robot voice" in lower
    ):
        toggle_robotic(True)
        speak("Robot voice enabled.")
        return True

    if "turn off robot voice" in lower or "disable robot voice" in lower or "normal voice" in lower:
        toggle_robotic(False)
        speak("Robot voice disabled. Back to normal tone.")
        return True

    # ---- Reset to default ----
    if "reset voice" in lower or "default voice" in lower or "normal settings" in lower:
        reset_voice()
        speak("Voice reset to default settings.")
        return True

    # ---- Describe current voice ----
    if (
        "how does your voice sound" in lower
        or "current voice settings" in lower
        or "describe your voice" in lower
    ):
        speak(describe_settings())
        return True

    # ---- Save current voice preset ----
    # e.g. "save this voice as chill mode"
    if "save this voice as" in lower or "save voice as" in lower:
        if "save this voice as" in lower:
            name = lower.split("save this voice as", 1)[1].strip()
        else:
            name = lower.split("save voice as", 1)[1].strip()

        # Remove quotes if the user says "chill mode"
        name = name.strip("'\" ")

        if not name:
            speak("Please tell me a name to save this voice as.")
            return True

        try:
            save_current_voice(name)
            speak(f"I have saved this voice as {name}.")
        except Exception:
            speak("I could not save this voice preset.")
        return True

    # ---- Load a voice preset ----
    # e.g. "use my chill mode voice", "use chill mode voice"
    if "use" in lower and "voice" in lower:
        # get text between 'use' and 'voice'
        between = lower.split("use", 1)[1]
        between = between.split("voice", 1)[0]
        name = between.replace("my", "").strip("'\" ").strip()

        if not name:
            speak("Please say the name of the voice you want to use.")
            return True

        if load_voice(name):
            speak(f"Loaded the {name} voice preset.")
            speak(describe_settings())
        else:
            speak(f"I couldn't find a voice preset called {name}.")
        return True

    # ---- List saved voices ----
    if (
        "list my voices" in lower
        or "list custom voices" in lower
        or "what voices did i save" in lower
    ):
        presets = list_presets()
        if not presets:
            speak("You have not saved any custom voices yet.")
        else:
            names_str = ", ".join(presets)
            speak(f"Your saved voices are: {names_str}.")
        return True

    return False  # nothing related to voice was handled


# =========================================================
# EXISTING HELPERS (UNCHANGED)
# =========================================================

def open_app(app_name: str, speak):
    app_name = app_name.lower().strip()
    for key, path in APP_SHORTCUTS.items():
        if key in app_name:
            speak(f"Opening {key}")
            try:
                os.startfile(path)
                return True
            except Exception as e:
                speak(f"I couldn't open {key}.")
                print(e)
            return False
    return False


def open_website(site_name: str, speak):
    site_name = site_name.lower().strip()
    for key, url in WEBSITE_SHORTCUTS.items():
        if key in site_name:
            speak(f"Opening {key}")
            webbrowser.open(url)
            return
    speak("I don't know that website yet.")


def tell_time(speak):
    now = datetime.now().strftime("%I:%M %p")
    speak(f"The time is {now}")


def tell_date(speak):
    today = datetime.now().strftime("%A, %d %B %Y")
    speak(f"Today is {today}")


def tell_joke(speak):
    speak(random.choice(JOKES))


def translate_text(cmd: str, speak):
    """
    Expected pattern:
      'translate <text> to <language>'
    Example:
      'translate hello how are you to hindi'
    """
    try:
        lower = cmd.lower()

        if "translate" not in lower or " to " not in lower:
            speak("Say: translate <text> to <language>.")
            return

        # strip off "translate" then split into text + language
        after_translate = lower.split("translate", 1)[1].strip()
        parts = after_translate.split(" to ", 1)
        if len(parts) != 2:
            speak("Please specify the language. For example, translate hello to Hindi.")
            return

        text_part = parts[0].strip()
        lang_part = parts[1].strip()

        # Map language name to code if possible
        lang_key = lang_part.lower()
        target_lang = LANGUAGE_MAP.get(lang_key, lang_key)  # fallback to whatever user said

        # Use deep-translator
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text_part)

        speak(f"In {lang_part.capitalize()}, that is: {translated}")

    except Exception as e:
        speak("I couldn't translate that right now.")
        print("[TRANSLATE ERROR]", e)


# =========================================================
# MAIN DISPATCH
# =========================================================

def execute_command(cmd: str, speak):

    # --- Voice modulation & presets ---
    if _handle_voice_commands(cmd, speak):
        return

    # --- Time & Date ---
    if "time" in cmd:
        tell_time(speak)
        return

    if "date" in cmd or "day" in cmd:
        tell_date(speak)
        return

    # --- Jokes ---
    if "joke" in cmd:
        tell_joke(speak)
        return

    # --- Translate ---
    if "translate" in cmd:
        translate_text(cmd, speak)
        return

    # --- Open websites ---
    if "open" in cmd and any(site in cmd for site in WEBSITE_SHORTCUTS.keys()):
        open_website(cmd, speak)
        return

    # --- Open apps ---
    if cmd.startswith("open "):
        name = cmd[len("open "):].strip()
        # 1) try built-in shortcuts
        handled = open_app(name, speak)
        if handled:
            return

        # 2) fallback: try app_indexer
        try:
            import app_indexer
            match = app_indexer.find_app(name)
            if match:
                display_name, path = match
                speak(f"Opening {display_name}")
                try:
                    os.startfile(path)
                except Exception as e:
                    speak("I couldn't open that application.")
                    print(e)
            else:
                speak("I couldn't find that application on your system.")
        except Exception as e:
            print("[commands.app_indexer] Error:", e)
            speak("Sorry, I couldn't search for apps right now.")
        return
    
    # -----Rescan Apps-----
    if "rescan system apps" in cmd or "rescan apps" in cmd or "scan apps" in cmd:
        try:
            build_index(save=True)
            speak("Rescanned system applications.")
        except Exception as e:
            print("[commands.rescan] Error:", e)
            speak("I couldn't rescan the applications right now.")


    # Default fallback
    speak(" ")
    # I heard you, but I don't know how to do that yet.