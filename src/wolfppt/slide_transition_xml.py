"""Open XML slide transition XML inspection, creation, and manipulation."""

from __future__ import annotations

import math
import posixpath
import re
import struct
import zipfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P_STRICT_NS = "http://purl.oclc.org/ooxml/presentationml/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
R_STRICT_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"
P159_NS = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
AUDIO_REL_TYPE = f"{R_NS}/audio"
WAV_CONTENT_TYPE = "audio/wav"

VALID_SPEEDS = {"slow", "med", "fast"}
SPEED_ALIASES = {
    "medium": "med",
    "normal": "med",
}

MORPH_OPTION_ALIASES = {
    "byobject": "byObject",
    "by_object": "byObject",
    "object": "byObject",
    "byword": "byWord",
    "by_word": "byWord",
    "word": "byWord",
    "bychar": "byChar",
    "by_char": "byChar",
    "char": "byChar",
    "character": "byChar",
}
MORPH_OPTION_PUBLIC_NAMES = {
    "byObject": "by_object",
    "byWord": "by_word",
    "byChar": "by_char",
}

_SIDE = ("l", "u", "r", "d")
_CORNER = ("lu", "ru", "ld", "rd")
PRESET_TRANSITIONS = (
    "fallOver",
    "drape",
    "curtains",
    "wind",
    "prestige",
    "fracture",
    "crush",
    "peelOff",
    "pageCurlDouble",
    "pageCurlSingle",
    "airplane",
    "origami",
)
# Compact (lower case, no separators) spellings accepted for enumerated tokens.
_ENUM_ALIASES = {
    "left": "l",
    "right": "r",
    "up": "u",
    "down": "d",
    "leftup": "lu",
    "upleft": "lu",
    "rightup": "ru",
    "upright": "ru",
    "leftdown": "ld",
    "downleft": "ld",
    "rightdown": "rd",
    "downright": "rd",
    "horizontal": "horz",
    "vertical": "vert",
    "centre": "center",
}


class TransitionRefusal(ValueError):
    """A requested transition value cannot be represented safely."""


@dataclass(frozen=True)
class TransitionField:
    """One typed option of a transition effect element.

    ``name`` is the public field name, ``attribute`` the XML attribute,
    ``kind`` one of ``enum``, ``bool``, ``uint`` or ``morph``, and ``default``
    the schema default (None when the schema defines none).
    """

    name: str
    attribute: str
    kind: str
    default: Any = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionKind:
    """A transition effect element: XML local name, namespace and value family."""

    name: str
    namespace: str
    family: str

    @property
    def requires(self) -> str | None:
        """mc:Choice prefix needed to author this kind, or None for base PresentationML."""
        return _EXTENSION_PREFIXES.get(self.namespace)


_EXTENSION_PREFIXES = {P14_NS: "p14", P15_NS: "p15", P159_NS: "p159"}

TRANSITION_FAMILIES: dict[str, tuple[TransitionField, ...]] = {
    "empty": (),
    "corner": (TransitionField("direction", "dir", "enum", "lu", _CORNER),),
    "eight_direction": (TransitionField("direction", "dir", "enum", "l", _SIDE + _CORNER),),
    "side": (TransitionField("direction", "dir", "enum", "l", _SIDE),),
    "left_right": (TransitionField("direction", "dir", "enum", None, ("l", "r")),),
    "in_out": (TransitionField("direction", "dir", "enum", "out", ("in", "out")),),
    "orientation": (TransitionField("direction", "dir", "enum", "horz", ("horz", "vert")),),
    "optional_black": (TransitionField("through_black", "thruBlk", "bool", False),),
    "split": (
        TransitionField("orientation", "orient", "enum", "horz", ("horz", "vert")),
        TransitionField("direction", "dir", "enum", "out", ("in", "out")),
    ),
    "wheel": (TransitionField("spokes", "spokes", "uint", 4),),
    "reveal": (
        TransitionField("through_black", "thruBlk", "bool", False),
        TransitionField("direction", "dir", "enum", "l", ("l", "r")),
    ),
    "ripple": (TransitionField("direction", "dir", "enum", "center", ("center", *_CORNER)),),
    "shred": (
        TransitionField("pattern", "pattern", "enum", "strip", ("strip", "rectangle")),
        TransitionField("direction", "dir", "enum", "in", ("in", "out")),
    ),
    "glitter": (
        TransitionField("direction", "dir", "enum", "l", _SIDE),
        TransitionField("pattern", "pattern", "enum", "diamond", ("diamond", "hexagon")),
    ),
    "fly_through": (
        TransitionField("direction", "dir", "enum", "in", ("in", "out")),
        TransitionField("has_bounce", "hasBounce", "bool", False),
    ),
    "prism": (
        TransitionField("direction", "dir", "enum", "l", _SIDE),
        TransitionField("is_content", "isContent", "bool", False),
        TransitionField("is_inverted", "isInverted", "bool", False),
    ),
    "morph": (TransitionField("morph_type", "option", "morph", "byObject"),),
    "preset": (
        TransitionField("preset", "prst", "enum", "fallOver", PRESET_TRANSITIONS),
        TransitionField("invert_x", "invX", "bool", False),
        TransitionField("invert_y", "invY", "bool", False),
    ),
}

_KIND_TABLE: tuple[tuple[str, str, str], ...] = (
    # ECMA-376 CT_SlideTransition effects.
    ("blinds", P_NS, "orientation"),
    ("checker", P_NS, "orientation"),
    ("circle", P_NS, "empty"),
    ("comb", P_NS, "orientation"),
    ("cover", P_NS, "eight_direction"),
    ("cut", P_NS, "optional_black"),
    ("diamond", P_NS, "empty"),
    ("dissolve", P_NS, "empty"),
    ("fade", P_NS, "optional_black"),
    ("newsflash", P_NS, "empty"),
    ("plus", P_NS, "empty"),
    ("pull", P_NS, "eight_direction"),
    ("push", P_NS, "side"),
    ("random", P_NS, "empty"),
    ("randomBar", P_NS, "orientation"),
    ("split", P_NS, "split"),
    ("strips", P_NS, "corner"),
    ("wedge", P_NS, "empty"),
    ("wheel", P_NS, "wheel"),
    ("wipe", P_NS, "side"),
    ("zoom", P_NS, "in_out"),
    # [MS-PPTX] PowerPoint 2010 effects.
    ("vortex", P14_NS, "side"),
    ("switch", P14_NS, "left_right"),
    ("flip", P14_NS, "left_right"),
    ("ripple", P14_NS, "ripple"),
    ("honeycomb", P14_NS, "empty"),
    ("prism", P14_NS, "prism"),
    ("doors", P14_NS, "orientation"),
    ("window", P14_NS, "orientation"),
    ("ferris", P14_NS, "left_right"),
    ("gallery", P14_NS, "left_right"),
    ("conveyor", P14_NS, "left_right"),
    ("pan", P14_NS, "side"),
    ("glitter", P14_NS, "glitter"),
    ("warp", P14_NS, "in_out"),
    ("flythrough", P14_NS, "fly_through"),
    ("flash", P14_NS, "empty"),
    ("shred", P14_NS, "shred"),
    ("reveal", P14_NS, "reveal"),
    ("wheelReverse", P14_NS, "wheel"),
    # [MS-PPTX] PowerPoint 2013 preset effects and 2015/09 Morph.
    ("prstTrans", P15_NS, "preset"),
    ("morph", P159_NS, "morph"),
)
TRANSITION_KINDS: dict[str, TransitionKind] = {
    name: TransitionKind(name, namespace, family) for name, namespace, family in _KIND_TABLE
}


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


SUPPORTED_TRANSITIONS: dict[str, str] = {}
for _name in TRANSITION_KINDS:
    SUPPORTED_TRANSITIONS[_name.lower()] = _name
    SUPPORTED_TRANSITIONS[_snake_case(_name)] = _name
SUPPORTED_TRANSITIONS.update(
    {
        "randombars": "randomBar",
        "random_bars": "randomBar",
        "fly_through": "flythrough",
        "preset": "prstTrans",
    }
)

SUPPORTED_CANONICAL_NAMES = set(TRANSITION_KINDS)

# PowerPoint's built-in transition sounds: display name -> embedded sound name.
BUILT_IN_TRANSITION_SOUNDS: dict[str, str] = {
    "applause": "applause.wav",
    "arrow": "arrow.wav",
    "bomb": "bomb.wav",
    "breeze": "breeze.wav",
    "camera": "camera.wav",
    "cash register": "cashreg.wav",
    "chime": "chime.wav",
    "click": "click.wav",
    "coin": "coin.wav",
    "drum roll": "drumroll.wav",
    "explosion": "explode.wav",
    "hammer": "hammer.wav",
    "laser": "laser.wav",
    "push": "push.wav",
    "suction": "suction.wav",
    "typewriter": "type.wav",
    "voltage": "voltage.wav",
    "whoosh": "whoosh.wav",
    "wind": "wind.wav",
}

SOUND_MODES = ("start", "stop_previous")


@dataclass(frozen=True)
class TransitionSoundAction:
    """A p:sndAc action.

    ``mode`` is ``start`` (p:stSnd) or ``stop_previous`` (p:endSnd). Start sounds
    reference an embedded WAV by ``rel_id``; ``data`` carries a WAV payload that
    the package-aware applicator embeds as a new media part on save.
    """

    mode: str
    name: str = ""
    built_in: bool = False
    loop: bool = False
    rel_id: str | None = None
    data: bytes | None = None


def _xml_local_name(tag: str) -> str:
    """Return local name without XML namespace prefix."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def register_transition_namespaces() -> None:
    """Register common PresentationML and DrawingML namespaces for ElementTree."""
    ET.register_namespace("p", P_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)
    ET.register_namespace("p14", P14_NS)
    ET.register_namespace("mc", MC_NS)
    ET.register_namespace("p15", P15_NS)
    ET.register_namespace("p159", P159_NS)


def normalize_transition_type(value: Any) -> str | None:
    """Normalize and validate transition effect type string.

    Returns the canonical Open XML element local name (e.g. 'fade', 'randomBar', 'push').
    Returns None if value is None or 'none'.
    Raises TypeError if not a string or None.
    Raises ValueError if unsupported.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("transition type must be a string or None")
    cleaned = value.strip()
    if not cleaned or cleaned.lower() == "none":
        return None
    canonical = SUPPORTED_TRANSITIONS.get(cleaned.lower())
    if canonical is not None:
        return canonical
    raise TransitionRefusal(
        f"unsupported transition type: {value!r}. Supported types: "
        f"{', '.join(sorted(SUPPORTED_CANONICAL_NAMES))}"
    )


def normalize_morph_option(value: Any) -> str:
    """Normalize a public Morph mode to its required Open XML enum value."""
    if not isinstance(value, str):
        raise TypeError("morph option must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise TransitionRefusal("morph option must be by_object, by_word, or by_char")
    canonical = MORPH_OPTION_ALIASES.get(cleaned.lower())
    if canonical is None:
        raise TransitionRefusal(
            f"unsupported morph option: {value!r}. Supported options: by_object, by_word, by_char"
        )
    return canonical


def transition_fields(kind: str) -> tuple[TransitionField, ...]:
    """Return the typed option fields of a canonical transition kind."""
    return TRANSITION_FAMILIES[TRANSITION_KINDS[kind].family]


def transition_field(kind: str, key: str) -> TransitionField:
    """Return the field of ``kind`` named by public field name or XML attribute."""
    for field in transition_fields(kind):
        if key in (field.name, field.attribute):
            return field
    names = ", ".join(field.name for field in transition_fields(kind)) or "none"
    raise TransitionRefusal(f"{kind} transition has no option {key!r}; supported options: {names}")


def encode_transition_field(kind: str, field: TransitionField, value: Any) -> str:
    """Validate a field value and return its Open XML attribute text."""
    if field.kind == "bool":
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, str) and value.strip().lower() in {"1", "true"}:
            return "1"
        if isinstance(value, str) and value.strip().lower() in {"0", "false"}:
            return "0"
        raise TypeError(f"{kind} {field.name} must be a boolean")
    if field.kind == "uint":
        number: Any = value
        if isinstance(value, str) and value.strip().isdigit():
            number = int(value.strip())
        if isinstance(number, bool) or not isinstance(number, int):
            raise TypeError(f"{kind} {field.name} must be an integer")
        if not 1 <= number <= 4_294_967_295:
            raise TransitionRefusal(
                f"{kind} {field.name} must be between 1 and 4294967295, got {number}"
            )
        return str(number)
    if field.kind == "morph":
        return normalize_morph_option(value)
    if not isinstance(value, str):
        raise TypeError(f"{kind} {field.name} must be a string")
    compact = re.sub(r"[\s_-]", "", value).lower()
    compact = _ENUM_ALIASES.get(compact, compact)
    for choice in field.choices:
        if compact == choice.lower():
            return choice
    raise TransitionRefusal(
        f"unsupported {kind} {field.name}: {value!r}. Supported values: {', '.join(field.choices)}"
    )


def decode_transition_field(field: TransitionField, raw: str | None) -> Any:
    """Return the typed value of a stored attribute, or the schema default."""
    if raw is None:
        if field.kind == "morph":
            return MORPH_OPTION_PUBLIC_NAMES[field.default]
        return field.default
    if field.kind == "bool":
        lowered = raw.strip().lower()
        if lowered in {"1", "true"}:
            return True
        if lowered in {"0", "false"}:
            return False
        return field.default
    if field.kind == "uint":
        return int(raw) if raw.strip().isdigit() else field.default
    if field.kind == "morph":
        return MORPH_OPTION_PUBLIC_NAMES.get(raw, raw)
    return raw


def normalize_transition_options(kind: str, options: Mapping[str, Any]) -> dict[str, str]:
    """Validate effect options (public names or XML attributes) for ``kind``.

    Returns XML attribute text keyed by attribute name, in caller order.
    """
    if kind not in TRANSITION_KINDS:
        raise TransitionRefusal(f"unsupported transition type: {kind!r}")
    normalized: dict[str, str] = {}
    for key, value in options.items():
        field = transition_field(kind, str(key))
        if value is None:
            normalized.pop(field.attribute, None)
            continue
        normalized[field.attribute] = encode_transition_field(kind, field, value)
    if kind == "morph":
        normalized.setdefault("option", "byObject")
    return normalized


def compatible_transition_options(kind: str, options: Mapping[str, str]) -> dict[str, str]:
    """Keep only the stored options that remain valid for a new transition kind."""
    kept: dict[str, str] = {}
    for attribute, value in options.items():
        try:
            field = transition_field(kind, attribute)
            if field.attribute == attribute:
                kept[attribute] = encode_transition_field(kind, field, value)
        except (TypeError, ValueError):
            continue
    if kind == "morph":
        kept.setdefault("option", "byObject")
    return kept


def normalize_built_in_sound_name(value: Any) -> str:
    """Return PowerPoint's embedded name for a built-in transition sound."""
    if not isinstance(value, str):
        raise TypeError("built-in sound name must be a string")
    cleaned = re.sub(r"[\s_-]+", " ", value.strip()).lower()
    if cleaned in BUILT_IN_TRANSITION_SOUNDS:
        return BUILT_IN_TRANSITION_SOUNDS[cleaned]
    if cleaned in BUILT_IN_TRANSITION_SOUNDS.values():
        return cleaned
    raise TransitionRefusal(
        f"unknown built-in transition sound: {value!r}. Built-in sounds: "
        f"{', '.join(BUILT_IN_TRANSITION_SOUNDS)}"
    )


def validate_wav_bytes(data: Any) -> bytes:
    """Validate a RIFF/WAVE payload for an embedded transition sound."""
    if isinstance(data, bytearray | memoryview):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("transition sound data must be WAV bytes")
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise TransitionRefusal("transition sound data must be a RIFF/WAVE (.wav) file")
    return data


def synthesize_transition_tone(
    frequency: float = 880.0, seconds: float = 0.3, rate: int = 22050
) -> bytes:
    """Return a short 16-bit mono PCM WAV tone.

    CT_EmbeddedWAVAudioFile requires embedded audio even for built-in sounds;
    PowerPoint's own sound assets are not redistributable, so a built-in sound
    authored without data embeds this tone alongside builtIn="1" and the name.
    """
    count = int(rate * seconds)
    fade = max(1, count // 10)
    samples = bytearray()
    for index in range(count):
        envelope = min(1.0, index / fade, (count - index) / fade)
        sample = int(12000 * envelope * math.sin(2 * math.pi * frequency * index / rate))
        samples += struct.pack("<h", sample)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(samples),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        rate,
        rate * 2,
        2,
        16,
        b"data",
        len(samples),
    )
    return header + bytes(samples)


def normalize_transition_speed(value: Any) -> str | None:
    """Normalize and validate transition speed ('slow', 'med', 'fast').

    Returns 'slow', 'med', or 'fast'.
    Returns None if value is None.
    Raises TypeError if not a string or None.
    Raises ValueError if unsupported.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("transition speed must be a string ('slow', 'med', 'fast') or None")
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    mapped = SPEED_ALIASES.get(cleaned, cleaned)
    if mapped not in VALID_SPEEDS:
        raise TransitionRefusal(
            f"unsupported transition speed: {value!r}. Supported speeds: "
            f"{', '.join(sorted(VALID_SPEEDS))}"
        )
    return mapped


def normalize_advance_on_click(value: Any) -> bool | None:
    """Validate advance_on_click boolean."""
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError("advance_on_click must be a boolean or None")
    return value


def normalize_advance_after(value: Any) -> float | None:
    """Normalize and validate advance_after in seconds.

    Returns float seconds.
    Returns None if value is None.
    Raises TypeError if not a number.
    Raises TransitionRefusal if negative, non-finite or outside unsigned milliseconds.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("advance_after must be a non-negative number of seconds or None")
    if not 0 <= value <= 4_294_967.295:
        raise TransitionRefusal(
            "advance_after must be non-negative, finite and at most 4294967.295 seconds, "
            f"got {value}"
        )
    return float(value)


def normalize_transition_duration(value: Any) -> int | None:
    """Normalize and validate transition duration in milliseconds.

    Normative schema type is xsd:unsignedInt (0 to 4294967295 ms).
    Maps to p14:dur in PresentationML XML.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("transition duration must be an integer (milliseconds) or None")
    if value < 0 or value > 4_294_967_295:
        raise TransitionRefusal(
            f"transition duration must be between 0 and 4294967295 milliseconds, got {value}"
        )
    return value


def _ensure_ignorable(slide_root: ET.Element, prefix: str) -> None:
    """Ensure a namespace prefix is listed in mc:Ignorable."""
    ignorable = slide_root.get(f"{{{MC_NS}}}Ignorable")
    prefixes = ignorable.split() if ignorable else []
    if prefix not in prefixes:
        prefixes.append(prefix)
        slide_root.set(f"{{{MC_NS}}}Ignorable", " ".join(prefixes))


def _clean_ignorable_if_unused(slide_root: ET.Element, prefix: str, namespace: str) -> None:
    """Remove an ignorable prefix when no element or attribute still uses it."""
    for element in slide_root.iter():
        if element.tag.startswith(f"{{{namespace}}}"):
            return
        if any(attr.startswith(f"{{{namespace}}}") for attr in element.attrib):
            return
    ignorable = slide_root.get(f"{{{MC_NS}}}Ignorable")
    if not ignorable:
        return
    prefixes = [item for item in ignorable.split() if item != prefix]
    if prefixes:
        slide_root.set(f"{{{MC_NS}}}Ignorable", " ".join(prefixes))
    else:
        slide_root.attrib.pop(f"{{{MC_NS}}}Ignorable", None)


def _ensure_p14_ignorable(slide_root: ET.Element) -> None:
    _ensure_ignorable(slide_root, "p14")


def _clean_p14_ignorable_if_unused(slide_root: ET.Element) -> None:
    _clean_ignorable_if_unused(slide_root, "p14", P14_NS)


def _transition_alternate_content(
    slide_root: ET.Element,
    presentation_ns: str = P_NS,
) -> tuple[ET.Element, ET.Element, ET.Element, ET.Element | None] | None:
    """Return the AlternateContent, its Choice, the Choice transition and fallback."""
    for alternate in slide_root.findall(f"{{{MC_NS}}}AlternateContent"):
        for choice in alternate.findall(f"{{{MC_NS}}}Choice"):
            transition = choice.find(f"{{{presentation_ns}}}transition")
            if transition is not None:
                fallback = alternate.find(f"{{{MC_NS}}}Fallback/{{{presentation_ns}}}transition")
                return alternate, choice, transition, fallback
    return None


def _is_effect(child: ET.Element) -> bool:
    return _xml_local_name(child.tag) not in {"sndAc", "extLst"}


def _read_effect(transition_el: ET.Element) -> tuple[str | None, dict[str, str], bool]:
    for child in transition_el:
        if not _is_effect(child):
            continue
        local_name = _xml_local_name(child.tag)
        kind = TRANSITION_KINDS.get(local_name)
        namespace = kind.namespace if kind is not None else None
        if namespace == P_NS and transition_el.tag == f"{{{P_STRICT_NS}}}transition":
            namespace = P_STRICT_NS
        supported = kind is not None and child.tag == f"{{{namespace}}}{local_name}"
        if supported and local_name == "morph":
            try:
                normalize_morph_option(child.get("option"))
            except (TypeError, ValueError):
                supported = False
        return local_name, dict(child.attrib), supported
    return None, {}, True


def _read_sound(transition_el: ET.Element) -> TransitionSoundAction | None:
    presentation_ns = P_STRICT_NS if transition_el.tag == f"{{{P_STRICT_NS}}}transition" else P_NS
    relationship_ns = R_STRICT_NS if presentation_ns == P_STRICT_NS else R_NS
    action = transition_el.find(f"{{{presentation_ns}}}sndAc")
    if action is None:
        return None
    if action.find(f"{{{presentation_ns}}}endSnd") is not None:
        return TransitionSoundAction(mode="stop_previous")
    start = action.find(f"{{{presentation_ns}}}stSnd")
    if start is None:
        return None
    sound = start.find(f"{{{presentation_ns}}}snd")
    loop = start.get("loop", "0").lower() in {"1", "true"}
    if sound is None:
        return TransitionSoundAction(mode="start", loop=loop)
    return TransitionSoundAction(
        mode="start",
        name=sound.get("name", ""),
        built_in=sound.get("builtIn", "0").lower() in {"1", "true"},
        loop=loop,
        rel_id=sound.get(f"{{{relationship_ns}}}embed"),
    )


def read_slide_transition_xml(slide_root: ET.Element) -> dict[str, Any]:
    """Inspect transitional or strict slide transitions, including extension effects."""
    presentation_ns = P_STRICT_NS if slide_root.tag == f"{{{P_STRICT_NS}}}sld" else P_NS
    alternate = _transition_alternate_content(slide_root, presentation_ns)
    transition_el = (
        alternate[2]
        if alternate is not None
        else slide_root.find(f"{{{presentation_ns}}}transition")
    )
    if transition_el is None:
        return {
            "has_transition": False,
            "type": None,
            "speed": None,
            "advance_on_click": True,
            "advance_after": None,
            "duration": None,
            "is_supported": True,
            "effect_options": {},
            "sound": None,
        }
    speed = transition_el.get("spd")
    if speed and speed.lower() in SPEED_ALIASES:
        speed = SPEED_ALIASES[speed.lower()]
    adv_click_attr = transition_el.get("advClick")
    advance_on_click = adv_click_attr not in {"0", "false", "False"}
    try:
        advance_after = (
            int(transition_el.get("advTm", "")) / 1000.0
            if transition_el.get("advTm") is not None
            else None
        )
    except (ValueError, TypeError):
        advance_after = None
    try:
        parsed_dur = int(transition_el.get(f"{{{P14_NS}}}dur", ""))
        duration = parsed_dur if 0 <= parsed_dur <= 4_294_967_295 else None
    except (ValueError, TypeError):
        duration = None
    effect_type, effect_options, is_supported = _read_effect(transition_el)
    return {
        "has_transition": True,
        "type": effect_type,
        "speed": speed,
        "advance_on_click": advance_on_click,
        "advance_after": advance_after,
        "duration": duration,
        "is_supported": is_supported,
        "effect_options": effect_options,
        "sound": _read_sound(transition_el),
    }


def _insert_slide_transition_element(
    slide_root: ET.Element, transition_element: ET.Element
) -> None:
    """Insert <p:transition> in PresentationML schema-compliant order.

    CT_Slide sequence:
      1. cSld (required)
      2. EG_SlideLifeCycleAdditions (optional)
      3. clrMapOvr (optional)
      4. transition (optional)
      5. timing (optional)
      6. extLst (optional)

    Place <p:transition> before <p:timing>/<p:extLst>
    and after <p:clrMapOvr>/<p:cSld>.
    """
    children = list(slide_root)
    insert_at = len(children)
    for index, child in enumerate(children):
        local_name = _xml_local_name(child.tag)
        if local_name in {"timing", "extLst"}:
            insert_at = index
            break
    slide_root.insert(insert_at, transition_element)


def _replace_effect(
    transition_el: ET.Element,
    effect_namespace: str,
    effect_name: str,
    attributes: dict[str, str],
) -> None:
    for child in list(transition_el):
        if _is_effect(child):
            transition_el.remove(child)
    effect_el = ET.Element(f"{{{effect_namespace}}}{effect_name}", attributes)
    insert_at = next(
        (index for index, child in enumerate(transition_el) if not _is_effect(child)),
        len(transition_el),
    )
    transition_el.insert(insert_at, effect_el)


def _replace_sound(
    transition_el: ET.Element, action: TransitionSoundAction | None, rel_id: str | None
) -> None:
    for child in transition_el.findall(f"{{{P_NS}}}sndAc"):
        transition_el.remove(child)
    if action is None:
        return
    sound_action = ET.Element(f"{{{P_NS}}}sndAc")
    if action.mode == "stop_previous":
        ET.SubElement(sound_action, f"{{{P_NS}}}endSnd")
    else:
        start = ET.SubElement(sound_action, f"{{{P_NS}}}stSnd")
        if action.loop:
            start.set("loop", "1")
        attributes = {f"{{{R_NS}}}embed": str(rel_id)}
        if action.name:
            attributes["name"] = action.name
        if action.built_in:
            attributes["builtIn"] = "1"
        ET.SubElement(start, f"{{{P_NS}}}snd", attributes)
    ext_list = transition_el.find(f"{{{P_NS}}}extLst")
    insert_at = list(transition_el).index(ext_list) if ext_list is not None else len(transition_el)
    transition_el.insert(insert_at, sound_action)


def _create_alternate_content(
    slide_root: ET.Element, transition_el: ET.Element | None, requires: str
) -> tuple[ET.Element, ET.Element]:
    """Replace a direct transition with an mc:AlternateContent Choice/Fallback pair."""
    choice_transition = (
        transition_el if transition_el is not None else ET.Element(f"{{{P_NS}}}transition")
    )
    fallback_transition = deepcopy(choice_transition)
    alternate = ET.Element(f"{{{MC_NS}}}AlternateContent")
    choice = ET.SubElement(alternate, f"{{{MC_NS}}}Choice", {"Requires": requires})
    choice.append(choice_transition)
    fallback = ET.SubElement(alternate, f"{{{MC_NS}}}Fallback")
    fallback.append(fallback_transition)
    if transition_el is None:
        _insert_slide_transition_element(slide_root, alternate)
    else:
        index = list(slide_root).index(transition_el)
        slide_root.remove(transition_el)
        slide_root.insert(index, alternate)
    return choice_transition, fallback_transition


def _clean_extension_ignorables(slide_root: ET.Element) -> None:
    _clean_p14_ignorable_if_unused(slide_root)
    _clean_ignorable_if_unused(slide_root, "p15", P15_NS)
    _clean_ignorable_if_unused(slide_root, "p159", P159_NS)


def remove_slide_transition_xml(slide_root: ET.Element) -> bool:
    """Remove a direct transition or its AlternateContent wrapper."""
    alternate = _transition_alternate_content(slide_root)
    if alternate is not None:
        slide_root.remove(alternate[0])
    else:
        transition_el = slide_root.find(f"{{{P_NS}}}transition")
        if transition_el is None:
            return False
        slide_root.remove(transition_el)
    _clean_extension_ignorables(slide_root)
    return True


def _transition_targets(
    slide_root: ET.Element, spec: Any, requires: str | None
) -> list[ET.Element] | None:
    """Return the transition elements an edit writes, creating the container shape."""
    effect_specified = getattr(spec, "effect_specified", False)
    alternate = _transition_alternate_content(slide_root)
    direct_transition = slide_root.find(f"{{{P_NS}}}transition")
    if effect_specified and requires is not None:
        if alternate is None:
            return list(_create_alternate_content(slide_root, direct_transition, requires))
        _, choice, choice_transition, fallback_transition = alternate
        choice.set("Requires", requires)
        if fallback_transition is None:
            fallback_transition = deepcopy(choice_transition)
            fallback = ET.SubElement(alternate[0], f"{{{MC_NS}}}Fallback")
            fallback.append(fallback_transition)
        return [choice_transition, fallback_transition]
    if alternate is not None:
        container, _, choice_transition, fallback_transition = alternate
        if effect_specified:
            index = list(slide_root).index(container)
            slide_root.remove(container)
            slide_root.insert(index, choice_transition)
            return [choice_transition]
        return [t for t in (choice_transition, fallback_transition) if t is not None]
    if direct_transition is None:
        has_content = any(
            getattr(spec, name, None) is not None
            for name in (
                "effect",
                "speed",
                "advance_on_click",
                "advance_after",
                "duration",
                "sound",
            )
        )
        if not has_content:
            return None
        direct_transition = ET.Element(f"{{{P_NS}}}transition")
        _insert_slide_transition_element(slide_root, direct_transition)
    return [direct_transition]


def set_slide_transition_xml(
    slide_root: ET.Element, spec: Any, *, sound_rel_id: str | None = None
) -> None:
    """Apply a transition spec without altering p:timing.

    Extension effects (p14, p15 and p159 Morph) use [MS-PPTX] §2.2.1
    AlternateContent: the Choice carries the effect and a base PresentationML
    fade is its fallback. ``sound_rel_id`` is the relationship id assigned to a
    newly embedded transition sound by :func:`apply_transition_package_edit`.
    """
    if getattr(spec, "remove", False):
        remove_slide_transition_xml(slide_root)
        return

    effect_specified = getattr(spec, "effect_specified", False)
    effect_name = getattr(spec, "effect", None)
    kind = TRANSITION_KINDS.get(effect_name) if effect_name is not None else None
    if effect_specified and effect_name is not None and kind is None:
        raise ValueError(f"unsupported transition type: {effect_name!r}")
    options: dict[str, str] = {}
    if effect_specified and kind is not None:
        raw_options = getattr(spec, "effect_options", {}) or {}
        if kind.name == "morph" and set(raw_options) - {"option", "morph_type"}:
            raise ValueError("Morph accepts only the option setting")
        options = normalize_transition_options(kind.name, raw_options)

    sound_specified = getattr(spec, "sound_specified", False)
    sound: TransitionSoundAction | None = getattr(spec, "sound", None)
    sound_rel = None
    if sound_specified and sound is not None and sound.mode == "start":
        sound_rel = sound_rel_id if sound.data is not None else sound.rel_id
        if sound_rel is None:
            raise ValueError(
                "a new embedded transition sound needs its package relationship; "
                "apply it with apply_transition_package_edit"
            )

    requires = kind.requires if kind is not None else None
    targets = _transition_targets(slide_root, spec, requires)
    if targets is None:
        return

    for transition_el in targets:
        if getattr(spec, "speed_specified", False):
            value = getattr(spec, "speed", None)
            if value is None:
                transition_el.attrib.pop("spd", None)
            else:
                transition_el.set("spd", value)
        if getattr(spec, "advance_on_click_specified", False):
            value = getattr(spec, "advance_on_click", None)
            if value is None:
                transition_el.attrib.pop("advClick", None)
            else:
                transition_el.set("advClick", "1" if value else "0")
        if getattr(spec, "advance_after_specified", False):
            value = getattr(spec, "advance_after", None)
            if value is None:
                transition_el.attrib.pop("advTm", None)
            else:
                transition_el.set("advTm", str(round(value * 1000)))
        if getattr(spec, "duration_specified", False):
            value = getattr(spec, "duration", None)
            if value is None:
                transition_el.attrib.pop(f"{{{P14_NS}}}dur", None)
            else:
                transition_el.set(f"{{{P14_NS}}}dur", str(normalize_transition_duration(value)))
                _ensure_p14_ignorable(slide_root)
        if sound_specified:
            _replace_sound(transition_el, sound, sound_rel)

    if effect_specified:
        if kind is None:
            for transition_el in targets:
                for child in list(transition_el):
                    if _is_effect(child):
                        transition_el.remove(child)
        elif requires is not None:
            _replace_effect(targets[0], kind.namespace, kind.name, options)
            _replace_effect(targets[1], P_NS, "fade", {})
            if kind.name == "morph":
                _ensure_ignorable(slide_root, "p159")
        else:
            _replace_effect(targets[0], P_NS, kind.name, options)
    _clean_extension_ignorables(slide_root)


def _rels_part_name(part_name: str) -> str:
    directory, name = posixpath.split(part_name.lstrip("/"))
    return posixpath.join(directory, "_rels", f"{name}.rels")


def _current_part(
    package: zipfile.ZipFile, replacements: Mapping[str, bytes], name: str
) -> bytes | None:
    if name in replacements:
        return replacements[name]
    try:
        return package.read(name)
    except KeyError:
        return None


def _serialize(root: ET.Element, namespace: str) -> bytes:
    """Serialize a flat OPC part (relationships, content types) unprefixed.

    Written by hand so the shared ElementTree prefix registry is untouched.
    """
    from xml.sax.saxutils import quoteattr

    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<{_xml_local_name(root.tag)} xmlns="{namespace}">',
    ]
    for child in root:
        if child.tag != f"{{{namespace}}}{_xml_local_name(child.tag)}" or len(child):
            raise ValueError(f"unexpected element in package part: {child.tag}")
        attributes = "".join(f" {name}={quoteattr(value)}" for name, value in child.attrib.items())
        lines.append(f"<{_xml_local_name(child.tag)}{attributes}/>")
    lines.append(f"</{_xml_local_name(root.tag)}>")
    return "".join(lines).encode("utf-8")


def _media_part_for(
    package: zipfile.ZipFile, replacements: Mapping[str, bytes], data: bytes
) -> str:
    """Reuse an identical embedded WAV part or allocate the next free media name."""
    names = set(package.namelist()) | set(replacements)
    for name in sorted(names):
        if (
            name.startswith("ppt/media/")
            and name.lower().endswith(".wav")
            and _current_part(package, replacements, name) == data
        ):
            return name
    used = [
        int(match.group(1))
        for name in names
        if (match := re.fullmatch(r"ppt/media/media(\d+)\.\w+", name))
    ]
    return f"ppt/media/media{max(used, default=0) + 1}.wav"


def _ensure_wav_content_type(
    package: zipfile.ZipFile, replacements: dict[str, bytes], media_part: str
) -> None:
    payload = _current_part(package, replacements, "[Content_Types].xml")
    if payload is None:
        raise KeyError("package has no [Content_Types].xml")
    types = ET.fromstring(payload)
    for default in types.findall(f"{{{CT_NS}}}Default"):
        if default.get("Extension", "").lower() == "wav":
            return
    for override in types.findall(f"{{{CT_NS}}}Override"):
        if override.get("PartName", "").lstrip("/") == media_part:
            return
    element = ET.Element(
        f"{{{CT_NS}}}Default", {"Extension": "wav", "ContentType": WAV_CONTENT_TYPE}
    )
    defaults = types.findall(f"{{{CT_NS}}}Default")
    insert_at = list(types).index(defaults[-1]) + 1 if defaults else 0
    types.insert(insert_at, element)
    replacements["[Content_Types].xml"] = _serialize(types, CT_NS)


def _load_relationships(
    package: zipfile.ZipFile, replacements: Mapping[str, bytes], rels_part: str
) -> ET.Element:
    payload = _current_part(package, replacements, rels_part)
    if payload is None:
        return ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    return ET.fromstring(payload)


def embed_transition_sound(
    package: zipfile.ZipFile,
    slide_part: str,
    spec: Any,
    replacements: dict[str, bytes],
) -> str | None:
    """Embed a pending transition WAV and return its new slide relationship id.

    Adds the ``ppt/media`` part (reusing an identical one), an audio
    relationship from the slide, and the ``wav`` content type default to
    ``replacements``. Returns None when the spec carries no new WAV payload.
    """
    sound: TransitionSoundAction | None = getattr(spec, "sound", None)
    if not getattr(spec, "sound_specified", False) or sound is None or sound.data is None:
        return None
    data = validate_wav_bytes(sound.data)
    slide_part = slide_part.lstrip("/")
    media_part = _media_part_for(package, replacements, data)
    replacements[media_part] = data
    _ensure_wav_content_type(package, replacements, media_part)
    rels_part = _rels_part_name(slide_part)
    relationships = _load_relationships(package, replacements, rels_part)
    target = posixpath.relpath(media_part, posixpath.dirname(slide_part))
    numbers = [
        int(match.group(1))
        for rel in relationships
        if (match := re.fullmatch(r"rId(\d+)", rel.get("Id", "")))
    ]
    rel_id = f"rId{max(numbers, default=0) + 1}"
    ET.SubElement(
        relationships,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": rel_id, "Type": AUDIO_REL_TYPE, "Target": target},
    )
    replacements[rels_part] = _serialize(relationships, PKG_REL_NS)
    return rel_id


def _transition_elements(slide_root: ET.Element) -> list[ET.Element]:
    alternate = _transition_alternate_content(slide_root)
    if alternate is not None:
        return [t for t in (alternate[2], alternate[3]) if t is not None]
    direct = slide_root.find(f"{{{P_NS}}}transition")
    return [] if direct is None else [direct]


def _sound_rel_ids(slide_root: ET.Element) -> set[str]:
    ids: set[str] = set()
    for transition_el in _transition_elements(slide_root):
        for sound in transition_el.iter(f"{{{P_NS}}}snd"):
            rel_id = sound.get(f"{{{R_NS}}}embed")
            if rel_id:
                ids.add(rel_id)
    return ids


def _referenced_rel_ids(slide_root: ET.Element) -> set[str]:
    return {
        value
        for element in slide_root.iter()
        for name, value in element.attrib.items()
        if name.startswith(f"{{{R_NS}}}")
    }


def apply_transition_package_edit(
    package: zipfile.ZipFile,
    slide_part: str,
    slide_root: ET.Element,
    spec: Any,
    replacements: dict[str, bytes],
) -> None:
    """Apply a transition spec to ``slide_root`` together with its package parts.

    Embeds a new transition sound, writes the slide XML edit, and drops audio
    relationships of replaced sounds that nothing in the slide still references.
    """
    previous_sounds = _sound_rel_ids(slide_root)
    rel_id = embed_transition_sound(package, slide_part, spec, replacements)
    set_slide_transition_xml(slide_root, spec, sound_rel_id=rel_id)
    stale = previous_sounds - _referenced_rel_ids(slide_root)
    if not stale:
        return
    rels_part = _rels_part_name(slide_part)
    relationships = _load_relationships(package, replacements, rels_part)
    removed = False
    for rel in list(relationships):
        if rel.get("Id") in stale and rel.get("Type") == AUDIO_REL_TYPE:
            relationships.remove(rel)
            removed = True
    if removed:
        replacements[rels_part] = _serialize(relationships, PKG_REL_NS)


def read_transition_sound_data(
    package: zipfile.ZipFile, slide_part: str, rel_id: str
) -> bytes | None:
    """Return the embedded WAV bytes a slide relationship id points to."""
    slide_part = slide_part.lstrip("/")
    try:
        relationships = ET.fromstring(package.read(_rels_part_name(slide_part)))
    except KeyError:
        return None
    for rel in relationships:
        if rel.get("Id") == rel_id and rel.get("TargetMode") != "External":
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(slide_part), rel.get("Target", ""))
            )
            try:
                return package.read(target.lstrip("/"))
            except KeyError:
                return None
    return None
