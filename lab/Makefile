# `make check` compiles every example under PDF/UA-1 (what the CI runs).
EXAMPLES := $(wildcard examples/*.typ)
PDFS := $(EXAMPLES:examples/%.typ=build/%.pdf)

check: $(PDFS)
	@echo "all examples compiled"

build/%.pdf: examples/%.typ $(wildcard themes/*.typ) $(wildcard notes/*.typ)
	@mkdir -p build
	typst compile --root . --pdf-standard ua-1 $< $@

clean:
	rm -rf build

.PHONY: check clean
