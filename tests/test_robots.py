"""/robots.txt refuses Reflectionbot everything and every other crawler nothing.

Read as a crawler reads it, by the standard library's parser, through the app
as ASGI, as test_appendix_pages does.
"""

import unittest
import urllib.robotparser

from test_appendix_pages import get


class Robots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status, cls.headers, body = get("/robots.txt")
        cls.rp = urllib.robotparser.RobotFileParser()
        cls.rp.parse(body.splitlines())

    def test_it_is_plain_text(self):
        self.assertEqual(self.status, 200)
        self.assertTrue(self.headers["content-type"].startswith("text/plain"))

    def test_reflectionbot_may_read_nothing(self):
        # By its token, as a crawler matches itself (RFC 9309, and reflection.ai/bot);
        # the parser would read a whole user-agent string by its first word, "Mozilla".
        for path in ("/", "/101:4", "/101:4.2", "/i/adjuster", "/i/jesus/read", "/search?q=love"):
            self.assertFalse(self.rp.can_fetch("Reflectionbot", path), path)

    def test_every_other_crawler_may_read_everything(self):
        for ua in ("Googlebot", "bingbot", "OAI-SearchBot", "DuckDuckBot", "Applebot"):
            for path in ("/", "/101:4.2", "/i/adjuster", "/i/jesus/read/theme", "/appendix/A"):
                self.assertTrue(self.rp.can_fetch(ua, path), (ua, path))


if __name__ == "__main__":
    unittest.main()
