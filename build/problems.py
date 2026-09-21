"""One problem type, one report, one exit status.

The three source projects all share a philosophy: a parser that cannot account
for its input stops, rather than quietly dropping what it did not understand.
This module is how that philosophy is expressed here.

Severities:
  hard   -- never demotable.  An unknown macro, an unparseable citation, a span
            outside its paragraph, a source line nothing claimed.  These mean
            the extractor does not understand the input, and any output built on
            top of that misunderstanding is worthless.
  fatal  -- stops the build, but MAY be demoted by a dated, reasoned entry in
            verify/exceptions.toml.  Divergences between the two editions live
            here: each one is a decision somebody made, on the record.
  warn   -- recorded in the report, does not stop the build.
"""

from __future__ import annotations

import collections
import dataclasses
import sys

HARD, FATAL, WARN = "hard", "fatal", "warn"
_RANK = {HARD: 0, FATAL: 1, WARN: 2}


@dataclasses.dataclass(frozen=True, slots=True)
class Problem:
    severity: str
    code: str          # stable kebab-case slug, greppable
    where: str         # "tex/p041.tex:36" or "41:4.3"
    message: str

    def __str__(self) -> str:
        return f"{self.severity:5} {self.code:28} {self.where:24} {self.message}"


class Report:
    def __init__(self, exceptions: dict[str, str] | None = None) -> None:
        self.problems: list[Problem] = []
        self.exceptions = exceptions or {}
        self.demoted: list[tuple[Problem, str]] = []

    def add(self, severity: str, code: str, where: str, message: str) -> None:
        p = Problem(severity, code, where, message)
        if severity == FATAL:
            key = f"{code}@{where}"
            if key in self.exceptions:
                self.demoted.append((p, self.exceptions[key]))
                return
        self.problems.append(p)

    def hard(self, code, where, msg):  self.add(HARD, code, where, msg)
    def fatal(self, code, where, msg): self.add(FATAL, code, where, msg)
    def warn(self, code, where, msg):  self.add(WARN, code, where, msg)

    @property
    def blocking(self) -> list[Problem]:
        return [p for p in self.problems if p.severity in (HARD, FATAL)]

    def summary(self) -> str:
        by = collections.Counter(p.code for p in self.problems)
        if not by and not self.demoted:
            return "no problems"
        out = []
        for code, n in by.most_common():
            sev = next(p.severity for p in self.problems if p.code == code)
            out.append(f"  {sev:5} {code:28} {n}")
        if self.demoted:
            out.append(f"  demoted by exceptions.toml: {len(self.demoted)}")
        return "\n".join(out)

    def emit(self, limit: int = 40) -> int:
        """Print and return a process exit status."""
        self.problems.sort(key=lambda p: (_RANK[p.severity], p.code, p.where))
        for p in self.problems[:limit]:
            print(p, file=sys.stderr)
        if len(self.problems) > limit:
            print(f"... and {len(self.problems) - limit} more", file=sys.stderr)
        if self.problems or self.demoted:
            print("\n" + self.summary(), file=sys.stderr)
        n = len(self.blocking)
        if n:
            print(f"\nBUILD FAILED: {n} blocking problem(s)", file=sys.stderr)
            return 1
        return 0
