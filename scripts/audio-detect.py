#!/usr/bin/env python3
"""Detect the analog audio card and write asound.conf.

The hardcoded asound.conf (plughw:1,0) only worked for ONE specific piece of
hardware (A8-7410: HDMI=card0, analog=card1). Here we choose the FIRST card that
is NOT HDMI/DisplayPort, so the beep/audio works on any machine
(VBox, A8-7410, i5-1035G1...).
"""
import pathlib
import re
import subprocess
import time


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


def _count_cards():
    """How many cards are currently in /proc/asound/cards."""
    try:
        t = pathlib.Path("/proc/asound/cards").read_text()
    except OSError:
        return 0
    return len(re.findall(r"^\s*\d+\s*\[", t, re.M))


def _card_exists(card):
    """Is that card really in /proc/asound/cards right now?

    An EMPTY /proc/asound/cards at boot made the old code write the fallback card
    0 (HDMI): there is no line for card 0 to inspect, so _is_hdmi(0) said False
    and nothing stopped it. Never write a card we cannot see.
    """
    try:
        text = pathlib.Path("/proc/asound/cards").read_text()
    except OSError:
        return False
    return bool(re.search(rf"^\s*{card}\s*\[", text, re.M))


def _is_hdmi(card):
    try:
        text = pathlib.Path("/proc/asound/cards").read_text()
    except OSError:
        return False
    for line in text.splitlines():
        m = re.match(rf"^\s*{card}\s*\[", line)
        if m:
            return bool(re.search(r"HDMI|DisplayPort|\bDP\b", line, re.I))
    return False


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


# ---------------------------------------------------------------------------
# Capture gain
#
# The kernel default for the mic capture is +30 dB (Capture at 100%). On a
# laptop's internal mic that SATURATES the input: in complete silence the signal
# already sits at ~44% of full scale, so Vosk gets white noise and returns an
# empty transcription (voice.listen() -> None, Ctrl+G / /mic do nothing).
#
# Measured on the A8-7410 (ALC3227), noise floor in SILENCE:
#     Capture 63 (100%)  -> RMS 14409  (clipped, peak 32768)
#     Capture 30  (48%)  -> RMS  6452
#     Capture 20  (32%)  -> RMS  1222
#     Capture 15  (24%)  -> RMS   269   <- chosen
# With this setting real speech gave RMS 1628 with no clipping and transcribed.
# ---------------------------------------------------------------------------
CAPTURE_GAIN = "24%"
MIC_BOOST = "0"


def _amixer(card, *args):
    """Run amixer for one control; True if it applied.

    Control names differ between codecs (a laptop may expose 'Mic Boost',
    'Internal Mic Boost', both or neither), so every call is best-effort and a
    missing control is not an error.
    """
    try:
        r = subprocess.run(["amixer", "-c", str(card)] + list(args),
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def fix_capture_gain(card):
    """Lower the capture gain and the mic boosts so the mic does not saturate.

    Persists the result with `alsactl store` so alsa-restore.service reapplies
    it on every boot (a bare amixer call only lasts until reboot).
    """
    applied = []
    for ctl, val in (("Capture", CAPTURE_GAIN),
                     ("Mic Boost", MIC_BOOST),
                     ("Internal Mic Boost", MIC_BOOST)):
        if _amixer(card, "sset", ctl, val):
            applied.append(f"{ctl}={val}")
    if applied:
        try:
            subprocess.run(["alsactl", "store"], capture_output=True, timeout=20)
        except Exception:
            pass
    return applied


def main():
    # Pick the analog card EXPLICITLY, and only when it is really there.
    #
    # Measured failure (13 Sep 2026, laptop, after a reboot): this unit ran ~1 s
    # in, when /proc/asound/cards was still EMPTY. detect_analog_card() returned
    # the fallback 0 and _is_hdmi(0) returned False -- there was no line for card
    # 0 to inspect -- so the wait loop broke immediately and the guard was
    # skipped, writing plughw:0,0 (HDMI). That is why there was no sound, the
    # volume keys did nothing (card 0 has no such mixer) and no capture controls
    # were found (so the mic gain was never fixed either).
    #
    # An empty or partial /proc/asound/cards means NOT READY, not "card 0". Require
    # a card that exists AND is not HDMI before writing anything.
    card = None
    for _ in range(40):
        c = detect_analog_card()
        if _card_exists(c) and not _is_hdmi(c):
            card = c
            break
        time.sleep(1)
    if card is None:
        # Never overwrite a working asound.conf with a guess.
        print("audio-detect: no analog card available yet; keeping the existing asound.conf")
        return
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
    applied = fix_capture_gain(card)
    if applied:
        print("audio-detect: capture gain fixed (" + ", ".join(applied) + ")")
    else:
        print("audio-detect: no capture controls found (mic gain left as is)")


if __name__ == "__main__":
    main()
