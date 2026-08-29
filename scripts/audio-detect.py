#!/usr/bin/env python3
"""Detect the analog audio card and write asound.conf.

The hardcoded asound.conf (plughw:1,0) only worked for ONE specific piece of
hardware (A8-7410: HDMI=card0, analog=card1). Here we choose the FIRST card that
is NOT HDMI/DisplayPort, so the beep/audio works on any machine
(VBox, A8-7410, i5-1035G1...).
"""
import pathlib
import re


def detect_analog_card():
    try:
        text = pathlib.Path("/proc/asound/cards").read_text()
    except OSError:
        return 0
    cards = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s*\[", line)
        if m:
            cur = int(m.group(1))
            cards[cur] = line
        elif cur is not None:
            cards[cur] += "\n" + line
    # first card that is NOT HDMI/DisplayPort
    for c in sorted(cards):
        if not re.search(r"HDMI|DisplayPort|\bDP\b", cards[c], re.I):
            return c
    # fallback: the first card, or 0
    return min(cards) if cards else 0


def _write(conf):
    # /etc/asound.conf (system); if not writable (ro squashfs without overlay),
    # fall back to ~/.asoundrc (always writable and takes priority per user).
    for target in ("/etc/asound.conf", str(pathlib.Path.home() / ".asoundrc")):
        try:
            pathlib.Path(target).write_text(conf)
            return target
        except OSError:
            continue
    return None


def main():
    card = detect_analog_card()
    conf = (
        "pcm.!default {\n"
        "    type plug\n"
        f'    slave.pcm "plughw:{card},0"\n'
        "}\n"
        "ctl.!default {\n"
        "    type hw\n"
        f"    card {card}\n"
        "}\n"
    )
    where = _write(conf)
    if where:
        print(f"audio-detect: analog card {card} -> {where}")
    else:
        print(f"audio-detect: could not write asound.conf (card {card})")


if __name__ == "__main__":
    main()
