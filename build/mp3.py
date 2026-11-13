"""An MP3's frames, counted; and the frame that tells a player how many.

A player that is asked for a file's length, or to start at minute 30 of it,
does not read the file through: it takes the length from the Xing/Info frame
at its head, and where there is none it divides the file's size by the bit
rate the first frame names.  1,353 of Григорий Войнер's 1,627 files have no
such frame, and say 64 kbit/s in frames that are never padded: 208 bytes each
where 64 kbit/s is 208.98, so 63.7 kbit/s in truth.  Chrome took 181-02.mp3,
2,180.8 s long, for 2,170.6 s, and asked for 1,962.7 s it played from
1,972.0 s: late by 0.47% of the place, 9 s there, 1 s at three and a half
minutes (measured 2026-11-12, tools/audio/seek_e2e.py).  A paragraph's ▶
would have begun seconds into the paragraph.

So such a file is served with an Info frame, one frame of the file's own
kind, silent, holding the count of the frames after it and their bytes, where
a player looks for one: straight after the ID3v2 tag.  That is not always
where the first frame is: in 1,343 of his files a 128-byte "TAG" block, an
ID3v1 tag out of its place, stands between the two, which a player steps over
to the first frame; ffmpeg, which Chrome plays with, reads a length frame only
at the tag's end, and took one put after the block for sound.  Every player knows it (LAME writes one in every file it makes),
skips it, and has the length to the sample; and since the frames are all of a
size, a place found by proportion is the place.  No table of contents is
written: its hundred entries are whole 256ths of the file, 8 s of a file this
long.  The recording is a master and is not touched; the frame is put in as
the file is sent (ubsite/app.py), from what the build stored.

Pure functions over bytes, stdlib only: tools/audio/manifest.py reads the
files, and tests/test_mp3.py holds these to a file made by hand.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

# kbit/s by bitrate index, Layer III: MPEG-1, and MPEG-2 with 2.5.
RATES = {
    1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
    2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
}
HZ = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


class Frame(NamedTuple):
    size: int          # bytes, its header's four among them
    rate: int          # the bit rate it names, bit/s
    samples: int       # 1152, or 576 below MPEG-1
    hz: int
    mono: bool
    lsf: bool          # MPEG-2 or 2.5: the side information is shorter
    crc: bool


def frame(b: bytes, at: int) -> Frame | None:
    """The Layer III frame whose header stands at b[at:at+4], or None."""
    if at + 4 > len(b) or b[at] != 0xFF or b[at + 1] & 0xE0 != 0xE0:
        return None
    version = b[at + 1] >> 3 & 3            # 3 MPEG-1, 2 MPEG-2, 0 MPEG-2.5
    if version == 1 or b[at + 1] >> 1 & 3 != 1:     # reserved; not Layer III
        return None
    lsf = version != 3
    rate = RATES[2 if lsf else 1][b[at + 2] >> 4]
    if not rate or b[at + 2] >> 2 & 3 == 3:
        return None
    hz = HZ[version][b[at + 2] >> 2 & 3]
    size = (72 if lsf else 144) * rate * 1000 // hz + (b[at + 2] >> 1 & 1)
    return Frame(size, rate * 1000, 576 if lsf else 1152, hz, b[at + 3] >> 6 == 3, lsf, not b[at + 1] & 1)


def tag_at(f: Frame) -> int:
    """Where in a frame Xing, Info or nothing stands: after the header and the
    side information.  As ffmpeg and LAME count it, a CRC not allowed for."""
    return 4 + ((9 if f.mono else 17) if f.lsf else (17 if f.mono else 32))


class Scan(NamedTuple):
    head: int          # where the ID3v2 tag ends: a length frame's place
    at: int            # where the first frame stands, which may be further on
    end: int           # where the last frame ends
    frames: int        # the frames of sound: a Xing/Info/VBRI frame is not one
    samples: int
    hz: int
    header: bytes      # the first frame's four bytes
    tagged: bool       # it has a length frame of its own
    sizes: int         # how many frame sizes there are among them
    junk: int          # bytes between frames that are no frame


def scan(b: bytes) -> Scan:
    """The frames of an MP3, walked one by one from the first.  What stands
    between two frames and is no frame (a tag joined in with a second take) is
    stepped over, as a player does, and counted."""
    at = 0
    while b[at:at + 3] == b"ID3" and at + 10 <= len(b):
        n = b[at + 6] << 21 | b[at + 7] << 14 | b[at + 8] << 7 | b[at + 9]
        at += 10 + n + (10 if b[at + 5] & 0x10 else 0)
    head = at
    first = None
    frames = samples = junk = run = 0
    sizes = set()
    end = at
    tagged = False
    hz = 0
    synced = False                          # the last frame ended exactly here
    while at + 4 <= len(b):
        f = frame(b, at)
        # A header where the last frame ended is the next frame.  One found by
        # looking for it, at the start or after what is no frame, is believed
        # when another frame follows it, or a tag, or the file ends: four
        # bytes of anything can look like a header.
        if f is None or not (synced or at + f.size >= len(b) - 3 or frame(b, at + f.size)
                             or b[at + f.size:at + f.size + 3] in (b"TAG", b"ID3", b"APE")):
            at += 1
            run += 1                        # between two frames, if another frame comes
            synced = False
            continue
        synced = True
        if first is None:
            first, hz = at, f.hz
            t = at + tag_at(f)
            if b[t:t + 4] in (b"Xing", b"Info") or b[at + 36:at + 40] == b"VBRI":
                tagged = True
                at += f.size
                end = at
                run = 0
                continue
        else:
            junk += run
        run = 0
        frames += 1
        samples += f.samples
        sizes.add(f.size)
        at += f.size
        end = min(at, len(b))
    if first is None:
        raise ValueError("no MP3 frame found")
    return Scan(head, first, end, frames, samples, hz, bytes(b[first:first + 4]), tagged, len(sizes), junk)


def misjudged(s: Scan) -> bool:
    """Would a player take this file for shorter or longer than it is, by more
    than a frame?  One with no length frame is taken for its bytes at the bit
    rate its first frame names."""
    f = frame(s.header, 0)
    return not s.tagged and abs(s.samples / s.hz - (s.end - s.at) * 8 / f.rate) > f.samples / f.hz


def info_frame(header: bytes, frames: int, size: int) -> bytes:
    """The Info frame for a file of `frames` frames in `size` bytes whose
    first frame has this header: a frame like it, unpadded, without a CRC, its
    side information and sound all zero, which is silence to a player that
    does not know the tag.  `size` is the sound's bytes and this frame's, as
    LAME counts it."""
    h = bytes([header[0], header[1] | 1, header[2] & ~2 & 0xFF, header[3]])
    f = frame(h, 0)
    if f is None:
        raise ValueError(f"not a Layer III frame header: {header.hex()}")
    out = bytearray(f.size)
    out[:4] = h
    t = tag_at(f)
    # Flags 3: the frame count and the byte count follow, and no table.
    out[t:t + 16] = b"Info" + struct.pack(">III", 3, frames, size + f.size)
    return bytes(out)
