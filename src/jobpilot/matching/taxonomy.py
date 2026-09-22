"""Skill taxonomy: normalization, variants and family relevance.

The same technology is written dozens of ways in job ads (``ROS2``, ``ros 2``,
``ROS-2``, ``ROS II``...). This module canonicalizes keywords coming from the
profile's ``skills`` blocks and expands them into matchable variants so the
scoring engine can find them reliably in free text.
"""

from __future__ import annotations

import re

_VARIANT_RE = re.compile(r"[^a-z0-9#.+]")


def normalize_skill(name: str) -> str:
    """Lowercase, strip punctuation/whitespace and collapse separators."""
    raw = name.lower().strip()
    raw = raw.replace("+plus", "+")
    return _VARIANT_RE.sub("", raw)


def expand_skill(name: str) -> list[str]:
    """Matchable variants of a skill keyword, most specific first.

    The first variant is always the raw name (as the user wrote it), so
    multi-word skills like ``can bus`` or ``motion planning`` are still searchable
    as phrases before their token fragments.
    """
    name = name.strip()
    variants: list[str] = [name]
    norm = normalize_skill(name)
    if norm and norm != name:
        variants.append(norm)
    # token fragments: "can bus" -> "can bus", "canbus", "can-bus" (covered above),
    # plus individual meaningful tokens.
    for token in name.lower().split():
        if len(token) > 2 and token not in variants:
            variants.append(token)
    return variants


# Frequent aliases that survive normalization collisions only via explicit map.
SKILL_ALIASES: dict[str, set[str]] = {
    "c++": {"cpp", "c plus plus", "c++11", "c++14", "c++17", "c++20"},
    "c": {"ansi c", "c99", "c11"},
    "python": {"python3", "py"},
    "ros2": {"ros 2", "ros ii", "ros2 humble", "ros2-foxy"},
    "ros": {"robot operating system"},
    "opencv": {"cv"},
    "git": {"github", "gitlab", "version control"},
    "pytest": {"py.test"},
    "test automation": {"automated testing", "automation testing", "test automation engineer"},
    "ci/cd": {"ci cd", "cicd", "continuous integration", "continuous delivery"},
    "microcontroller": {"microcontrollers", "mcu", "micro-controller"},
    "pcb": {"pcb design", "printed circuit board"},
    "stm32": {"stm 32"},
    "rtos": {"free rtos", "freertos", "threadx", "zephyr"},
    "slam": {"simultaneous localization", "simultaneous localisation"},
    "computer vision": {"vision"},
    "deep learning": {"machine learning", "neural network", "ml"},
    "embedded": {"embedded systems", "embedded software"},
    "electronics": {"electronic", "analog", "analog electronics"},
    "power electronics": {"power electronics", "power converter"},
    "control systems": {"control theory", "automatic control", "controls"},
    "motion planning": {"path planning", "trajectory planning"},
    "verification": {"v&v", "qualification"},
    "testing": {"functional testing", "test", "qa"},
    "simulation": {"simulated"},
    "mvp": {"mvp"},
}


def skill_variants(name: str) -> set[str]:
    """Raw phrase-like match strings (spaces/hyphens intact + flex forms).

    Multi-word skills keep their spaces/hyphens so they can match the offer text
    as written (``test automation``, ``real-time``), instead of being collapsed
    into glued single tokens that never appear verbatim.
    """
    raw = name.lower().strip()
    out = {raw}
    for v in list(out):
        out.add(v.replace("-", " "))
        out.add(v.replace(" ", "-"))
    for alias in SKILL_ALIASES.get(raw, set()):
        v = alias.lower().strip()
        out.add(v)
        out.add(v.replace("-", " "))
        out.add(v.replace(" ", "-"))
    return {o for o in out if len(o) >= 2}


def skill_tokens(name: str) -> set[str]:
    """Single normalized tokens (len>=3) for exact word-token matching.

    Only whole-word variants survive; normalized single tokens must be checked
    against the offer's word set, never with substring ``in``.
    """
    tokens: set[str] = set()
    for v in skill_variants(name):
        if " " in v or "-" in v:
            continue
        if len(v) >= 2 and re.fullmatch(r"[a-z0-9#+.]+", v):
            tokens.add(v)
        t = normalize_skill(v)
        if len(t) >= 3:
            tokens.add(t)
    tokens.discard("")  # never match empty or single chars
    return tokens


def skill_aliases(name: str) -> set[str]:
    """All match strings (phrases + flex forms) for substring matching."""
    return skill_variants(name)
