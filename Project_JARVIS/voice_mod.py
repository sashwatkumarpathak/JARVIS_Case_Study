# voice_mod.py

import os
import json
import tempfile
from typing import Dict

from pydub import AudioSegment
from pydub.effects import speedup

# ========= CORE VOICE SETTINGS =========
# These are the live values Jarvis will use.
VOICE_SETTINGS: Dict[str, float | bool] = {
    "pitch": 1.0,      # 1.0 = normal, >1.0 higher, <1.0 lower
    "speed": 1.0,      # 1.0 = normal, >1.0 faster, <1.0 slower
    "echo": False,
    "robotic": False,
}

# Step sizes for relative adjustments
PITCH_STEP = 0.1     # per "higher / lower pitch"
SPEED_STEP = 0.1     # per "faster / slower"
MIN_FACTOR = 0.5
MAX_FACTOR = 2.0

# ========= PRESET STORAGE =========
PRESET_FILE = "voice_presets.json"
PRESETS: Dict[str, Dict[str, float | bool]] = {}


def _load_presets_from_disk():
    global PRESETS
    if os.path.exists(PRESET_FILE):
        try:
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                PRESETS = json.load(f)
        except Exception as e:
            print("[VOICE_MOD] Failed to load presets:", e)
            PRESETS = {}
    else:
        PRESETS = {}


def _save_presets_to_disk():
    try:
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(PRESETS, f, indent=2)
    except Exception as e:
        print("[VOICE_MOD] Failed to save presets:", e)


# Load presets at import
_load_presets_from_disk()


# ========= PUBLIC API: SETTINGS =========

def get_current_settings() -> Dict[str, float | bool]:
    """Return a copy of current voice settings."""
    return dict(VOICE_SETTINGS)


def set_voice(pitch=None, speed=None, echo=None, robotic=None):
    """
    Set absolute values. Used for direct control (e.g. preset load).
    """
    if pitch is not None:
        VOICE_SETTINGS["pitch"] = max(MIN_FACTOR, min(float(pitch), MAX_FACTOR))

    if speed is not None:
        VOICE_SETTINGS["speed"] = max(MIN_FACTOR, min(float(speed), MAX_FACTOR))

    if echo is not None:
        VOICE_SETTINGS["echo"] = bool(echo)

    if robotic is not None:
        VOICE_SETTINGS["robotic"] = bool(robotic)


def reset_voice():
    """Reset to neutral/default voice."""
    VOICE_SETTINGS["pitch"] = 1.0
    VOICE_SETTINGS["speed"] = 1.0
    VOICE_SETTINGS["echo"] = False
    VOICE_SETTINGS["robotic"] = False


# ========= PUBLIC API: RELATIVE CHANGES =========

def nudge_speed(faster: bool = True):
    """
    Increase or decrease speaking speed slightly.
    faster=True  -> 'speak faster'
    faster=False -> 'speak slower'
    """
    delta = SPEED_STEP if faster else -SPEED_STEP
    new_speed = VOICE_SETTINGS["speed"] + delta
    VOICE_SETTINGS["speed"] = max(MIN_FACTOR, min(new_speed, MAX_FACTOR))


def nudge_pitch(higher: bool = True):
    """
    Increase or decrease pitch slightly.
    higher=True  -> 'higher pitch'
    higher=False -> 'lower pitch'
    """
    delta = PITCH_STEP if higher else -PITCH_STEP
    new_pitch = VOICE_SETTINGS["pitch"] + delta
    VOICE_SETTINGS["pitch"] = max(MIN_FACTOR, min(new_pitch, MAX_FACTOR))


def toggle_echo(on: bool | None = None):
    """
    Turn echo on/off or toggle if on is None.
    """
    if on is None:
        VOICE_SETTINGS["echo"] = not VOICE_SETTINGS["echo"]
    else:
        VOICE_SETTINGS["echo"] = bool(on)


def toggle_robotic(on: bool | None = None):
    """
    Turn robotic effect on/off or toggle if on is None.
    """
    if on is None:
        VOICE_SETTINGS["robotic"] = not VOICE_SETTINGS["robotic"]
    else:
        VOICE_SETTINGS["robotic"] = bool(on)


def describe_settings() -> str:
    """
    Return a human-friendly description - can be spoken back to user so they
    know how the voice currently sounds.
    """
    pitch = VOICE_SETTINGS["pitch"]
    speed = VOICE_SETTINGS["speed"]
    echo = VOICE_SETTINGS["echo"]
    robotic = VOICE_SETTINGS["robotic"]

    def level_name(x: float) -> str:
        if x < 0.8:
            return "low"
        if x > 1.2:
            return "high"
        return "normal"

    desc = (
        f"Pitch is {level_name(pitch)} "
        f"({pitch:.2f}), speed is {level_name(speed)} "
        f"({speed:.2f})."
    )

    traits = []
    if echo:
        traits.append("echo enabled")
    if robotic:
        traits.append("robotic effect on")

    if traits:
        desc += " Also, " + " and ".join(traits) + "."

    return desc


# ========= PUBLIC API: PRESETS =========

def save_current_voice(name: str):
    """Save current VOICE_SETTINGS as a named preset."""
    clean_name = name.strip().lower()
    if not clean_name:
        raise ValueError("Preset name cannot be empty.")

    PRESETS[clean_name] = get_current_settings()
    _save_presets_to_disk()


def load_voice(name: str) -> bool:
    """
    Load a preset by name into VOICE_SETTINGS.
    Returns True if found, else False.
    """
    clean_name = name.strip().lower()
    data = PRESETS.get(clean_name)
    if not data:
        return False

    set_voice(
        pitch=data.get("pitch", 1.0),
        speed=data.get("speed", 1.0),
        echo=data.get("echo", False),
        robotic=data.get("robotic", False),
    )
    return True


def list_presets() -> list[str]:
    """Return a list of saved preset names."""
    return sorted(PRESETS.keys())


def delete_preset(name: str) -> bool:
    """Delete a preset if it exists. Returns True on success."""
    clean_name = name.strip().lower()
    if clean_name in PRESETS:
        del PRESETS[clean_name]
        _save_presets_to_disk()
        return True
    return False


# ========= AUDIO PROCESSING =========

def apply_voice_effects(input_mp3_path: str) -> str:
    """
    Apply current voice settings to the generated gTTS audio.
    Returns a path to a NEW temporary mp3 file with modified effects.
    """
    audio = AudioSegment.from_file(input_mp3_path)

    # ----- PITCH SHIFT -----
    # Using frame_rate trick: change frame rate then resample back.
    pitch_factor = VOICE_SETTINGS["pitch"]
    if pitch_factor != 1.0:
        audio = audio._spawn(
            audio.raw_data,
            overrides={"frame_rate": int(audio.frame_rate * pitch_factor)}
        ).set_frame_rate(audio.frame_rate)

    # ----- SPEED -----
    speed_factor = VOICE_SETTINGS["speed"]
    if speed_factor != 1.0:
        audio = speedup(audio, playback_speed=speed_factor, chunk_size=50)

    # ----- ROBOTIC EFFECT -----
    if VOICE_SETTINGS["robotic"]:
        # Simple phase-inversion overlay for metallic/robotic tone
        audio = audio.overlay(audio.invert_phase())

    # ----- ECHO -----
    if VOICE_SETTINGS["echo"]:
        delay_ms = 120
        attenuation_db = 8
        echo = audio - attenuation_db
        echo = AudioSegment.silent(delay_ms) + echo
        audio = audio.overlay(echo)

    # Save as a new temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        output_path = fp.name

    audio.export(output_path, format="mp3")
    return output_path
