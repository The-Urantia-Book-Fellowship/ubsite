# ubsite -- LaTeX from three sibling repos -> one queryable database -> a site.
#
# The sources are MASTERS.  Nothing here writes to them; `make paranoid` proves it.

PY      := .venv/bin/python
DB      := var/ub.db

.PHONY: all venv lock sources vendor-check vendor-sync data check test paranoid serve serve-bg stop ports clean help

help:
	@sed -n 's/^## //p' Makefile

## venv          create .venv on the pinned Python and sync requirements.txt
venv:
	@uv venv --python $$(cat .python-version)
	@uv pip sync requirements.txt
	@$(PY) -c "import fastapi, uvicorn, jinja2, fontTools; print('venv ready')"

## lock          recompile requirements.txt from requirements.in
lock:
	@uv pip compile requirements.in -o requirements.txt

## sources       show the three source repos and the revisions in use
sources:
	@$(PY) -m build sources

## vendor-check  re-hash the vendored copies against upstream (fails with a diff)
vendor-check:
	@$(PY) -m build vendor-check

## vendor-sync   adopt upstream changes into vendor/ -- a reviewed commit, not a build step
vendor-sync:
	@$(PY) -m build vendor-sync

## data          build var/ub.db from the three sources
data: vendor-check
	@$(PY) -m build data

## check         run every gate against the built database
check:
	@$(PY) -m build check

## test          unit tests, including the never-write-to-a-master guard
test:
	@$(PY) -m pytest -q tests 2>/dev/null || $(PY) -m unittest discover -s tests -q

## paranoid      prove the three source trees were not modified by a build
paranoid:
	@$(PY) -m build paranoid

## clean         remove the derived database (it rebuilds in a couple of minutes)
clean:
	@rm -f $(DB) $(DB).tmp
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

PORT := 8130
PIDFILE := var/serve.pid

## serve         run the reader at http://127.0.0.1:$(PORT), in the foreground
serve: stop
	@$(PY) -m uvicorn ubsite.app:app \
		--host 127.0.0.1 --port $(PORT) --reload

## serve-bg      same, in the background, recording its pid
serve-bg: stop
	@mkdir -p var
	@nohup $(PY) -m uvicorn ubsite.app:app \
		--host 127.0.0.1 --port $(PORT) > var/serve.log 2>&1 & echo $$! > $(PIDFILE)
	@sleep 2; echo "serving on http://127.0.0.1:$(PORT)  (pid $$(cat $(PIDFILE)))"

## stop          stop the server this project started, and only that one
# By pid, never by pattern: `pkill -f "uvicorn ubsite.app"` matches the very
# shell running it, so it kills itself and leaves the server orphaned -- which
# is how four of them ended up listening at once.
stop:
	@if [ -f $(PIDFILE) ]; then \
		kill $$(cat $(PIDFILE)) 2>/dev/null || true; rm -f $(PIDFILE); \
	fi
	@exit 0

## ports         show anything this project has left listening
ports:
	@ss -ltnp 2>/dev/null | grep -E "127.0.0.1:$(PORT)" || echo "nothing on $(PORT)"
