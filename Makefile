# ubsite -- LaTeX from three sibling repos -> one queryable database -> a site.
#
# The sources are MASTERS.  Nothing here writes to them; `make paranoid` proves it.

PY      := .venv/bin/python
DB      := var/ub.db
# The ML environments: on the NVMe home, never on /Audio, never in requirements.txt.
ML      := $(HOME)/Software/ml
ALIGN   := $(ML)/venv-align/bin/python
NV      := $(ML)/venv-align/lib/python3.12/site-packages/nvidia
# GPU 0 is the 2080 Ti, 1 the 3090, in PCI order -- as nvidia-smi numbers them.
CUDA    := CUDA_DEVICE_ORDER=PCI_BUS_ID HF_HOME=$(ML)/hf \
           LD_LIBRARY_PATH=$(NV)/cublas/lib:$(NV)/cudnn/lib

.PHONY: align-venv align-transcribe align-repair align align-spotcheck tts-venv tts-bakeoff tts-bakeoff-chatterbox tts-bakeoff-higgs tts-bakeoff-higgs3 tts tts-assemble tts-hear all venv lock sources vendor-check vendor-sync srt-snapshot data check epub test paranoid serve serve-bg stop ports geoip clean help

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

## align-venv    create the aligner's venv in $(ML) (faster-whisper, CUDA libraries)
align-venv:
	@UV_CACHE_DIR=$(ML)/uv-cache uv venv -q $(ML)/venv-align --python $$(cat .python-version)
	@UV_CACHE_DIR=$(ML)/uv-cache uv pip install -q --python $(ML)/venv-align -r tools/align/requirements.in

## align-transcribe  Whisper over Merritt Horn's reading on the 3090 -> var/align/mh/ (resumable)
# The 3090 only.  The 2080 Ti drives the display: at batch 16 it ran out of
# memory, and at 8 it sat at 88 C (its max operating temperature is 89) with
# the fans flat out, throttled to 735 MHz -- adding a quarter to the speed.
# The script still takes several GPUs at once if ever wanted (O_EXCL locks).
align-transcribe:
	@$(ALIGN) -m tools.align.transcribe --clean-locks
	@$(CUDA) CUDA_VISIBLE_DEVICES=1 $(ALIGN) -m tools.align.transcribe 2>&1 | tee var/align/gpu1.log
	@ls var/align/mh/*.json | wc -l

## align-repair  re-hear, unbatched, every unit the aligner found mostly unheard; then `make align`
align-repair:
	@$(CUDA) CUDA_VISIBLE_DEVICES=1 $(ALIGN) -m tools.align.transcribe --repair

## align         cut Merritt Horn's reading at the paragraph -> data/audio/mh.tsv (seconds)
align:
	@$(PY) -m tools.align.align

## align-spotcheck  hear the first seconds of 300 random paragraphs: does each start where mh.tsv says?
align-spotcheck:
	@$(CUDA) CUDA_VISIBLE_DEVICES=1 $(ALIGN) -m tools.align.spotcheck

## tts-venv      create the synthetic voice's venv in $(ML) (Kokoro, torch)
tts-venv:
	@UV_CACHE_DIR=$(ML)/uv-cache uv venv -q $(ML)/venv-tts --python $$(cat .python-version)
	@UV_CACHE_DIR=$(ML)/uv-cache uv pip install -q --python $(ML)/venv-tts -r tools/tts/requirements.in

## tts-bakeoff   the same hard passages in each candidate voice, beside Merritt Horn -> var/tts/bakeoff/
tts-bakeoff:
	@CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HOME=$(ML)/hf \
		$(ML)/venv-tts/bin/python -m tools.tts.bakeoff

## tts-bakeoff-chatterbox  the same passages in Chatterbox's stock voice (its own venv)
tts-bakeoff-chatterbox:
	@CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HOME=$(ML)/hf \
		$(ML)/venv-chatterbox/bin/python -m tools.tts.bakeoff_chatterbox

## tts-bakeoff-higgs  0:0.1 in Higgs Audio v2's voices (its own venv; repo in $(ML)/src)
tts-bakeoff-higgs:
	@CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HOME=$(ML)/hf \
		$(ML)/venv-higgs/bin/python -m tools.tts.bakeoff_higgs

## tts-bakeoff-higgs3  0:0.1 in Higgs TTS 3, cloned from synthetic references (vLLM-Omni venv)
tts-bakeoff-higgs3:
	@CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HOME=$(ML)/hf \
		$(ML)/venv-vllm/bin/python -m tools.tts.bakeoff_higgs3

## tts           the whole book in the AI voice: make what is missing (3090, resumable), then assemble
tts:
	@CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HOME=$(ML)/hf \
		$(ML)/venv-vllm/bin/python -m tools.tts.book $(ARGS) 2>&1 | tee -a var/tts/book.log

## tts-assemble  one MP3 per section from what has been made -> var/audio/ai/, data/audio/ai*.tsv (no GPU)
tts-assemble:
	@$(ML)/venv-vllm/bin/python -m tools.tts.book --assemble $(ARGS)

## tts-hear      Whisper listens back to the listening test's clips: did each voice say the words?
tts-hear:
	@$(CUDA) CUDA_VISIBLE_DEVICES=1 $(ALIGN) -m tools.tts.hear

## sources       show the three source repos and the revisions in use
sources:
	@$(PY) -m build sources

## vendor-check  re-hash the vendored copies against upstream (fails with a diff)
vendor-check:
	@$(PY) -m build vendor-check

## vendor-sync   adopt upstream changes into vendor/ -- a reviewed commit, not a build step
vendor-sync:
	@$(PY) -m build vendor-sync

## srt-snapshot  fetch the SRT Committee's page into data/srt/ -- review the diff, then commit
srt-snapshot:
	@$(PY) -m tools.srt.snapshot

## data          build var/ub.db from the three sources
data: vendor-check
	@$(PY) -m build data

## check         run every gate against the built database
check:
	@$(PY) -m build check

## epub          the whole site as an EPUB -> var/epub/the-urantia-book.epub, then every gate
# epubcheck (W3C) is the last gate.  It needs Java -- apt's openjdk-26-jre-headless --
# and the jar from github.com/w3c/epubcheck/releases, unpacked into ~/Software.
EPUBCHECK ?= $(HOME)/Software/epubcheck/epubcheck-5.4.0/epubcheck.jar
epub:
	@$(PY) -m epub build
	@EPUBCHECK=$(EPUBCHECK) $(PY) -m epub check

## test          unit tests, including the never-write-to-a-master guard
test:
	@# UB_VISITS=off: pages rendered by the tests are not visits.  test_visits turns it on.
	@UB_VISITS=off $(PY) -m pytest -q tests 2>/dev/null || UB_VISITS=off $(PY) -m unittest discover -s tests -q

## paranoid      prove the three source trees were not modified by a build
paranoid:
	@$(PY) -m build paranoid

## geoip         fetch DB-IP's City Lite (CC BY 4.0) -> var/geoip/, for the visit counter
# Published monthly; early in a month the new one may not be up yet, so last
# month's is the fallback.  Into a temp name, then mv: a running server keeps
# its mmap of the old file.  deploy.sh ships it.
GEOIP := var/geoip/dbip-city-lite.mmdb
geoip:
	@mkdir -p var/geoip
	@for m in $$(date -u +%Y-%m) $$(date -u -d "$$(date -u +%Y-%m-15) -1 month" +%Y-%m); do \
		url=https://download.db-ip.com/free/dbip-city-lite-$$m.mmdb.gz; \
		if curl -fsS "$$url" | gunzip > $(GEOIP).tmp 2>/dev/null && [ -s $(GEOIP).tmp ]; then \
			mv $(GEOIP).tmp $(GEOIP); echo "$(GEOIP): $$m ($$(du -h $(GEOIP) | cut -f1))"; exit 0; fi; \
	done; rm -f $(GEOIP).tmp; echo "geoip: no DB-IP City Lite for this month or the last" >&2; exit 1

## clean         remove the derived database (it rebuilds in a couple of minutes)
clean:
	@rm -f $(DB) $(DB).tmp
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

PORT := 8130
# HOST=0.0.0.0 to reach it from another device on the network (a phone).
HOST := 127.0.0.1
PIDFILE := var/serve.pid

## serve         run the reader at http://$(HOST):$(PORT), in the foreground
serve: stop
	@$(PY) -m uvicorn ubsite.app:app \
		--host $(HOST) --port $(PORT) --reload

## serve-bg      same, in the background, recording its pid
serve-bg: stop
	@mkdir -p var
	@nohup $(PY) -m uvicorn ubsite.app:app \
		--host $(HOST) --port $(PORT) > var/serve.log 2>&1 & echo $$! > $(PIDFILE)
	@sleep 2; echo "serving on http://$(HOST):$(PORT)  (pid $$(cat $(PIDFILE)))"

## stop          stop the server this project started, and only that one
# By pid, never by pattern: `pkill -f "uvicorn ubsite.app"` matches the very
# shell running it, so it kills itself and leaves the server orphaned -- which
# is how four of them ended up listening at once.
stop:
	@if [ -f $(PIDFILE) ]; then kill $$(cat $(PIDFILE)) 2>/dev/null || true; fi
	@rm -f $(PIDFILE)
	@# Verify the port actually freed.  Killing the recorded pid and deleting the
	@# pidfile is not enough: if the pid was stale the process survives AND the only
	@# record of it is gone.  So fall back to whoever holds the port.
	@for i in 1 2 3 4 5; do \
		ss -ltn 2>/dev/null | grep -q "127.0.0.1:$(PORT)" || exit 0; sleep 1; done; \
	held=$$(ss -ltnp 2>/dev/null | grep -oE "127.0.0.1:$(PORT).*pid=[0-9]+" \
		| grep -oE "pid=[0-9]+" | cut -d= -f2 | sort -u); \
	if [ -n "$$held" ]; then \
		echo "stop: pidfile was stale; $(PORT) still held by $$held -- killing"; \
		kill $$held 2>/dev/null || true; \
	fi
	@exit 0

## ports         show anything this project has left listening
ports:
	@ss -ltnp 2>/dev/null | grep -E "127.0.0.1:$(PORT)" || echo "nothing on $(PORT)"
