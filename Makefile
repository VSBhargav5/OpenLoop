test:
	pytest -q

install:
	pip install -e ".[dev]"

ingest-demo:
	python -m openloop ingest examples/messy_chat.txt -t demo --rules --me Bhargav --date 2026-08-25

digest:
	python -m openloop digest -f md
