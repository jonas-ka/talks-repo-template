# `make check` compiles every example under PDF/UA-1 (what the CI runs).
EXAMPLES := $(wildcard examples/*.typ)
PDFS := $(EXAMPLES:examples/%.typ=build/%.pdf)

check: $(PDFS)
	@echo "all examples compiled"

build/%.pdf: examples/%.typ $(wildcard themes/*.typ) $(wildcard notes/*.typ)
	@mkdir -p build
	typst compile --root . --pdf-standard ua-1 $< $@

# `make logbook`: the log-book tests, the example book through the checker, and its PDF and HTML
# view in build/ (needs uv, pandoc and typst).
logbook:
	uv run --project logbook --extra test --extra epics --extra migrate pytest -q logbook/tests
	uv run --project logbook logbook --root examples/logbook check
	uv run --project logbook logbook --root examples/logbook build --pdf build/example-logbook.pdf --html build/example-logbook-site --single build/example-logbook.html

clean:
	rm -rf build

.PHONY: check clean logbook
