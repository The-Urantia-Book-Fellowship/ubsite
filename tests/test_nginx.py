"""The two nginx server blocks, pi5's (deploy/ubsite.nginx) and the sigmaai.au
VPS's (deploy/ubsite-sigmaai.nginx), say the same thing but for the name and the
certificate.  Both hosts serve the same build, so a location, a limit or a
header added to one and not the other would make the two sites differ in a way
no test of the app can see (trap 19 was such a thing).

Comments and blank lines are dropped before comparing: each file explains its
own host.

And the offline copy's chunks, which nginx keeps once the app has sent each
(2026-11-10): the location's pattern is the app's own RE_CHUNK, so nginx keeps
what the app serves as a chunk and nothing else, and the path it keeps them
under is one level below a directory the hosts have, since nginx makes the last
level alone (/var/cache/nginx, the first choice, is on neither).
"""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
sys.path.insert(0, str(ROOT))


def directives(name: str, host: str) -> list[str]:
    text = (DEPLOY / name).read_text()
    lines = (re.sub(r"\s*#.*$", "", line).strip() for line in text.splitlines())
    return [line.replace(host, "HOST") for line in lines if line]


class TestNginx(unittest.TestCase):
    def test_same_but_for_the_name(self):
        pi5 = directives("ubsite.nginx", "ubsite.ddns.net")
        vps = directives("ubsite-sigmaai.nginx", "ubsite.sigmaai.au")
        self.assertEqual(pi5, vps)

    def test_names_its_own_host(self):
        for name, host in (("ubsite.nginx", "ubsite.ddns.net"),
                           ("ubsite-sigmaai.nginx", "ubsite.sigmaai.au")):
            d = directives(name, host)
            self.assertIn("server_name HOST;", d, name)
            self.assertIn("ssl_certificate     /etc/letsencrypt/live/HOST/fullchain.pem;", d, name)
            self.assertFalse(any("default_server" in x for x in d), name)

    def test_keeps_the_chunks_and_nothing_else(self):
        from ubsite.app import RE_CHUNK
        d = directives("ubsite.nginx", "ubsite.ddns.net")
        opened = 'location ~ "^/offline/c/%s$" {' % RE_CHUNK.pattern
        self.assertIn(opened, d)
        block = d[d.index(opened) + 1:]
        block = block[:block.index("}")]
        self.assertIn("proxy_cache ubsite_chunks;", block)
        # The path alone: with the query in the key, ?1, ?2 ... are a copy each.
        self.assertIn("proxy_cache_key $uri;", block)
        # No other location may keep anything: a page kept by nginx would be
        # another build's, and uncounted.
        self.assertEqual(len(re.findall(r"\bproxy_cache\s", " ".join(d))), 1)
        path = [x for x in d if x.startswith("proxy_cache_path ")]
        self.assertEqual(len(path), 1)
        where = pathlib.PurePosixPath(path[0].split()[1])
        self.assertEqual(str(where.parent), "/var/cache", "nginx makes one level, and the hosts have /var/cache")
        self.assertIn("keys_zone=ubsite_chunks:", path[0])
        # What keeps it from growing: both limits, on the directive's two lines.
        whole = " ".join(d[d.index(path[0]):d.index(path[0]) + 2])
        self.assertRegex(whole, r"max_size=\d+m\b")
        self.assertRegex(whole, r"inactive=\d+d\b")
        self.assertTrue(whole.endswith(";"))


if __name__ == "__main__":
    unittest.main()
