# Contributing

Keep OpenLoop local-first and testable offline.

1. Rule extractor must work with no API key.
2. Schema changes go through `ALTER TABLE ... ADD COLUMN` so existing DBs keep working.
3. Add a test for every new command path that mutates state.
4. `pytest -q` should stay green without network.
