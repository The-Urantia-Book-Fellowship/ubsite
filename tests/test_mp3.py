"""A recording a player would take for shorter than it is (2026-11-12).

1,358 of Григорий Войнер's files have no Xing/Info frame and frames that are
never padded, so that a player dividing their bytes by the bit rate they name
takes 2,180.8 s for 2,170.6 and plays, asked for a place, 0.47% past it.
build/mp3.py counts the frames and makes the Info frame such a file is sent
with; these hold it to files made by hand, a frame at a time, and the route
that sends one (ubsite/app.py `_with_head`) to the digest the list gives, whole
and by range, where the recordings are on this machine.
"""

import hashlib
import sqlite3
import struct
import unittest

from test_appendix_pages import DB
from test_offline import call
from build import config, mp3

MONO64 = bytes.fromhex("fffb50c0")       # MPEG-1 Layer III, 64 kbit/s, 44.1 kHz, mono, unpadded: 208 bytes
STEREO128 = bytes.fromhex("fffb9040")    # 128 kbit/s joint stereo: 417 bytes unpadded


def id3(n: int) -> bytes:
    """An ID3v2 tag of n bytes of padding."""
    return b"ID3\x03\x00\x00" + bytes([n >> 21 & 127, n >> 14 & 127, n >> 7 & 127, n & 127]) + bytes(n)


def frames(header: bytes, n: int, padded: bool = False) -> bytes:
    """n frames of silence; padded as the bit rate asks, where `padded`."""
    f = mp3.frame(header, 0)
    out, owed = b"", 0.0
    exact = 144 * f.rate / f.hz
    for _ in range(n):
        pad = 0
        if padded:
            owed += exact - f.size
            if owed >= 1:
                pad, owed = 1, owed - 1
        out += bytes([header[0], header[1], header[2] | pad << 1, header[3]]) + bytes(f.size - 4 + pad)
    return out


class Frames(unittest.TestCase):
    def test_a_header_is_read(self):
        f = mp3.frame(MONO64, 0)
        self.assertEqual((f.size, f.rate, f.samples, f.hz, f.mono, f.lsf), (208, 64000, 1152, 44100, True, False))
        self.assertEqual(mp3.frame(STEREO128, 0).size, 417)
        self.assertEqual((mp3.tag_at(f), mp3.tag_at(mp3.frame(STEREO128, 0))), (21, 36))
        for bad in (b"\x00\x00\x00\x00", b"TAG\x00", b"\xff\xfb\xf0\xc0", b"\xff\xfb\x00\xc0", b"\xff\xf3\x50\xc0"[:2] + b"\x5c\xc0"):
            self.assertIsNone(mp3.frame(bad, 0), bad.hex())

    def test_the_frames_are_counted_past_what_is_no_frame(self):
        # As 1,343 of his are made: an ID3v2 tag, a 128-byte "TAG" block out
        # of its place, then the sound.
        b = id3(6114) + b"TAG" + bytes(125) + frames(MONO64, 500)
        s = mp3.scan(b)
        self.assertEqual((s.head, s.at, s.end, s.frames, s.samples, s.hz), (6124, 6252, len(b), 500, 576000, 44100))
        self.assertEqual((s.header, s.tagged, s.sizes, s.junk), (MONO64, False, 1, 0))
        # A tag at the end is not sound, nor is one between two takes, which is counted.
        self.assertEqual(mp3.scan(b + b"TAG" + bytes(125)).frames, 500)
        joined = mp3.scan(frames(MONO64, 10) + bytes(37) + frames(MONO64, 10))
        self.assertEqual((joined.frames, joined.junk), (20, 37))
        with self.assertRaises(ValueError):
            mp3.scan(id3(10) + bytes(400))

    def test_only_a_file_a_player_would_misjudge_needs_the_frame(self):
        bare = mp3.scan(frames(MONO64, 2000))                  # 52.2 s at 63.7 kbit/s, taken for 52.0
        self.assertTrue(mp3.misjudged(bare))
        self.assertAlmostEqual(bare.samples / bare.hz - (bare.end - bare.at) * 8 / 64000, 0.245, places=3)
        self.assertFalse(mp3.misjudged(mp3.scan(frames(MONO64, 2000, padded=True))))
        self.assertEqual(mp3.scan(frames(MONO64, 2000, padded=True)).sizes, 2)
        # 64 kbit/s at 48 kHz is 192 bytes to the frame, exactly: nothing to pad.
        self.assertFalse(mp3.misjudged(mp3.scan(frames(bytes.fromhex("fffb54c0"), 2000))))
        # Too short to be out by a frame.
        self.assertFalse(mp3.misjudged(mp3.scan(frames(MONO64, 100))))


class Info(unittest.TestCase):
    def test_the_frame_is_one_of_the_file_s_own_kind_and_says_its_length(self):
        sound = frames(MONO64, 2000)
        head = mp3.info_frame(MONO64, 2000, len(sound))
        self.assertEqual(len(head), 208)
        self.assertEqual(head[:4], bytes.fromhex("fffb50c0"))
        self.assertEqual(head[4:21], bytes(17))                # no side information: silence
        self.assertEqual(head[21:25], b"Info")
        self.assertEqual(struct.unpack(">III", head[25:37]), (3, 2000, len(sound) + 208))
        self.assertEqual(head[37:], bytes(208 - 37))
        # A padded first frame, or one with a CRC, gives the same frame.
        self.assertEqual(mp3.info_frame(bytes.fromhex("fffa52c0"), 2000, len(sound)), head)
        self.assertEqual(len(mp3.info_frame(STEREO128, 10, 4170)), 417)
        self.assertEqual(mp3.info_frame(STEREO128, 10, 4170)[36:40], b"Info")
        with self.assertRaises(ValueError):
            mp3.info_frame(b"TAG\x00", 1, 1)

    def test_put_after_the_tag_it_is_the_file_s_length_frame(self):
        tag, block, sound = id3(22), b"TAG" + bytes(125), frames(MONO64, 2000)
        s = mp3.scan(tag + block + sound)
        sent = (tag + block + sound)[:s.head] + mp3.info_frame(s.header, s.frames, s.end - s.at) + block + sound
        t = mp3.scan(sent)
        # The same sound, its frames counted without the Info frame, which now
        # stands where the tag ends; and nothing more to put right.
        self.assertEqual((t.tagged, t.frames, t.samples, t.head, t.end - t.at), (True, 2000, s.samples, s.head, s.end - s.at + 208 + 128))
        self.assertFalse(mp3.misjudged(t))
        self.assertEqual(sent[s.head + 21:s.head + 25], b"Info")


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Stored(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def test_each_stored_frame_says_the_length_listed(self):
        rows = self.con.execute("SELECT f.name, f.bytes, f.duration_ms, f.head_at, f.head FROM audio_file f"
                                " WHERE f.head IS NOT NULL").fetchall()
        self.assertEqual(len(rows), 1356)
        for r in rows:
            head = bytes(r["head"])
            f = mp3.frame(head, 0)
            self.assertEqual(len(head), f.size, r["name"])
            t = mp3.tag_at(f)
            self.assertEqual(head[t:t + 4], b"Info", r["name"])
            flags, n, size = struct.unpack(">III", head[t + 4:t + 16])
            self.assertEqual(flags, 3)
            self.assertEqual(round(n * f.samples * 1000 / f.hz), r["duration_ms"], r["name"])
            # The sound and this frame, in a file that holds a tag or two besides.
            self.assertLessEqual(size - f.size, r["bytes"] - r["head_at"], r["name"])
            self.assertLess(r["bytes"] - (size - f.size), 70000, r["name"])

    def test_merritt_horn_s_files_are_sent_as_they_are(self):
        self.assertEqual(self.con.execute(
            "SELECT COUNT(*) FROM audio_file f JOIN audio_source s ON s.id = f.source_id"
            " WHERE s.key <> 'voyner' AND (f.head IS NOT NULL OR f.sent_sha256 IS NOT NULL)").fetchone()[0], 0)

    @unittest.skipUnless(config.audio().get("voyner", {}).get("present"), "the recording is not on this machine")
    def test_a_file_is_sent_with_its_frame_whole_and_by_range(self):
        r = self.con.execute("SELECT f.name, f.bytes, f.head_at, f.head, f.sent_sha256 FROM audio_file f"
                             " JOIN audio_source s ON s.id = f.source_id WHERE s.key = 'voyner'"
                             " AND f.head IS NOT NULL AND f.name = '03-00.mp3'").fetchone()
        at, n = r["head_at"], len(bytes(r["head"]))
        url = "/audio/voyner/" + r["name"]
        status, h, whole = call(url)
        self.assertEqual((status, len(whole), int(h["content-length"])), (200, r["bytes"] + n, r["bytes"] + n))
        self.assertEqual(hashlib.sha256(whole).hexdigest(), r["sent_sha256"])
        self.assertEqual(whole[at:at + n], bytes(r["head"]))
        master = (config.audio()["voyner"]["path"] / r["name"]).read_bytes()
        self.assertEqual(whole[:at] + whole[at + n:], master)       # the file itself, untouched
        self.assertEqual((h["accept-ranges"], h["etag"], h["content-type"]),
                         ("bytes", f'"{r["sent_sha256"][:32]}"', "audio/mpeg"))
        self.assertEqual(h["cache-control"], "public, max-age=31536000, immutable")
        size = len(whole)
        # Each seam of the three pieces, both ends, and one in the middle.
        for lo, hi in ((0, 0), (0, 99), (at - 3, at + 2), (at, at + n - 1), (at + n - 2, at + n + 70000),
                       (size - 5, size - 1), (size // 2, size // 2 + 200000), (at + 1, size + 999)):
            status, h, part = call(url, headers={"range": f"bytes={lo}-{hi}"})
            end = min(hi, size - 1)
            self.assertEqual((status, part), (206, whole[lo:end + 1]), (lo, hi))
            self.assertEqual((h["content-range"], h["content-length"]), (f"bytes {lo}-{end}/{size}", str(end - lo + 1)))
        status, h, part = call(url, headers={"range": f"bytes={size - 10}-"})
        self.assertEqual((status, part), (206, whole[-10:]))
        status, h, part = call(url, headers={"range": "bytes=-300"})
        self.assertEqual((status, part, h["content-range"]), (206, whole[-300:], f"bytes {size - 300}-{size - 1}/{size}"))
        status, h, _ = call(url, headers={"range": f"bytes={size}-"})
        self.assertEqual((status, h["content-range"]), (416, f"bytes */{size}"))
        # A range of another version of the file is answered with the whole.
        status, h, part = call(url, headers={"range": "bytes=0-9", "if-range": '"another"'})
        self.assertEqual((status, len(part)), (200, size))
        status, h, part = call(url, headers={"range": "bytes=0-9", "if-range": h["etag"]})
        self.assertEqual((status, part), (206, whole[:10]))
        # Several ranges at once, which no player asks: the whole, as allowed.
        self.assertEqual(call(url, headers={"range": "bytes=0-9,20-29"})[0], 200)


if __name__ == "__main__":
    unittest.main()
