.PHONY: test stress bench cov all

test:            ## fast suite (stress excluded)
	python3 -m pytest -q

cov:             ## coverage, fails under 95%
	python3 -m pytest -q --cov=oip --cov-report=term-missing

stress:          ## long-running volume/concurrency tests
	python3 -m pytest -m stress -q

bench:           ## benchmarks + regression check vs baseline.json
	python3 benchmarks/bench_identity.py

bench-record:    ## overwrite the baseline (deliberate act)
	python3 benchmarks/bench_identity.py --write-baseline

all: cov bench
