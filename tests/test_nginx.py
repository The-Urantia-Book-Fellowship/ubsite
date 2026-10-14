"""The two nginx server blocks, pi5's (deploy/ubsite.nginx) and the sigmaai.au
VPS's (deploy/ubsite-sigmaai.nginx), say the same thing but for the name and the
certificate.  Both hosts serve the same build, so a location, a limit or a
header added to one and not the other would make the two sites differ in a way
no test of the app can see (trap 19 was such a thing).

Comments and blank lines are dropped before comparing: each file explains its
own host.
"""

import pathlib
import re
import unittest

DEPLOY = pathlib.Path(__file__).resolve().parent.parent / "deploy"


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


if __name__ == "__main__":
    unittest.main()
