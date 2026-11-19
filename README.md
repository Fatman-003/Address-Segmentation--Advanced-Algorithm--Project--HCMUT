# Address Segmentation — minimal Python team repository

**Status:** Repository skeleton. Segmentation, database index and searching folders are intentionally empty until teammates implement them. Only `src/main.py` handles I/O and orchestration.

## Tree

```text
src/
  __init__.py
  main.py                       # owned by repo/I-O member
  address_segmentation/         # EMPTY: teammate 2
    .gitkeep
  database/                     # EMPTY: teammate 3
    .gitkeep
  searching/                    # EMPTY: teammate 4
    .gitkeep
contract.md                     # shared API specification
tests/test_main_io.py           # only I/O unit tests
data/.gitkeep                   # instructor reference files go here
examples/addresses.txt         # demo raw addresses
```

## Local commands

```bash
python -m src.main --help
python -m src.main --input examples/addresses.txt --database-dir data --output results.jsonl
```

The last command **will not run yet**: it fails with a clear "module not ready" error until teammates implement the agreed entry points. No fake address results are generated.

Requirements: Python 3.10+ and standard library only for the skeleton. No internet access needed.

## Collaboration

| Owner | Scope | Suggested branch |
| --- | --- | --- |
| You | `src/main.py`, contract, I/O and integration | `feature/main-io-contract` |
| Teammate 2 | `src/address_segmentation/` | `feature/address-segmentation` |
| Teammate 3 | `src/database/` | `feature/database-trie` |
| Teammate 4 | `src/searching/` | `feature/searching` |

Read [contract.md](contract.md) before coding. Each member may freely add files inside their folder but must keep the agreed public entry point. Algorithm code must not be implemented in `src/main.py`.

> **Note:** The supplied assignment calls for Street/Ward/Province outputs and strict speed limits. Actual reference database schema and judge I/O have not been confirmed, so the CLI protocol here is provisional.
