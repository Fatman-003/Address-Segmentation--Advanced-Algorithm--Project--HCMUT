# Contract — Address Segmentation (v0.1 / DRAFT)

> **All members must read this file before coding.** This repository is a skeleton: only `src/main.py` implements I/O and orchestration; the three teammate folders are deliberately empty. The local CLI/JSONL format below is **provisional**, not confirmed as the lecturer's judge protocol.

## 1. Requirements and constraints

- Business input: **one raw OCR address string**, plus instructor-provided reference database.
- Business output: **exactly** `street`, `ward`, `province`.
- A non-null output must equal a **canonical value in the corresponding input database** (including spelling and prefix), NOT the normalized OCR string.
- Missing/unrecognized value: Python `None` internally; temporary local JSONL represents it as JSON `null`. Official representation must be confirmed.
- No ML / AI inference; no internet at evaluation time.
- Maximum latency **≤ 0.1 s/request** and mean **≤ 0.01 s/request**. Whether index initialization is timed is unknown.
- Do not assume the database has street→ward→province relationships until actual files prove it.

## 2. Team folder ownership

| Owner | Folder / file | Responsibility |
| --- | --- | --- |
| Repo + I/O owner | `src/main.py`, `contract.md`, `README.md` | Input, output, CLI, module orchestration; no algorithms |
| Member 2 | `src/address_segmentation/` | Input normalization, tokenize, tentative street/ward/province segmentation |
| Member 3 | `src/database/` | Read reference files, construct Trie/other indexes **once at startup** |
| Member 4 | `src/searching/` | Match segments against index; resolve ambiguity; output canonical values or `None` |

A teammate may add internal Python modules freely inside **their** folder, but must keep the public entry functions specified below. No implementation changes in another member's folder without agreement. If a function signature changes, update this file AND `src/main.py` in the same reviewed PR.

## 3. Execution workflow

```text
STARTUP (once per process, if judge supports persistent process)
  --database-dir  -> src.database.builder.build_index(database_dir) -> index

EACH REQUEST
  UTF-8 text -> src/main.py reads raw address str
  -> src.address_segmentation.segmenter.segment_address(raw_address)
  -> src.searching.searcher.search_address(segmented, index)
  -> src/main.py validates + writes street/ward/province
```

**Segmentation is tentative.** When commas/prefixes are missing or words stick together, Searching must be allowed to infer or adjust boundaries using the index. Trie/index building is **not** performed for each request.

## 4. Required public functions (exact names and locations)

### A. `src/database/builder.py` (database/index owner)

```python
from pathlib import Path

def build_index(database_dir: Path) -> object:
    """Load the reference database and return a read-only search index.

    Run once before all address requests. Index type is implementation-specific;
    share its concrete shape with the searching owner.
    """
```

- `database_dir` points to the provided reference files. Exact filenames/schema are **TBD** until the lecturer provides them.
- The index must retain canonical strings and category (street/ward/province).
- If aliases collide, they may correspond to multiple canonical entries; do not silently discard conflicts.
- No hard-coded sample outputs or reliance on the development database being identical to the judging database.

### B. `src/address_segmentation/segmenter.py` (segmentation owner)

```python
def segment_address(raw_address: str) -> dict:
    """Propose labeled spans; do NOT decide canonical names here."""
```

Required dictionary schema:

```python
{
    "raw_address": "53 Nguyen Thi Minh Khai P Ben Thanh TP HCM",
    "spans": [
        {"field": "street", "text": "Nguyen Thi Minh Khai"},
        {"field": "ward", "text": "Ben Thanh"},
        {"field": "province", "text": "TP HCM"},
    ],
}
```

- `field` must be one of `street`, `ward`, `province`, `unknown`.
- For uncertain segmentations, return **multiple candidate spans**, including overlaps if appropriate; or emit a span with `field="unknown"`. An empty `spans` list is valid; searching may use `raw_address` to recover.
- Do not permanently remove house numbers (`3/2` can be a street), alter original input, or claim a guess is already a canonical value.
- Rules for `P.`, `Ph.`, `TP.`, `D.`, `Đ.` and punctuation belong here, not in `main.py`.

### C. `src/searching/searcher.py` (searching owner)

```python
def search_address(segmented: dict, index: object) -> dict[str, str | None]:
    """Look up and resolve canonical output using segmentation + index."""
```

Returns **exactly**:

```python
{"street": "Nguyễn Thị Minh Khai",
 "ward": "Phường Bến Thành",
 "province": "Thành phố Hồ Chí Minh"}
```

- Values must be canonical database strings or `None`. Never return a normalized search key.
- Search may refine segmentation boundaries, handle abbreviations/compact forms, or return `None` when uncertain.
- The searching owner and indexing owner jointly decide index internals; the entry-point contract above stays stable.

### D. `src/main.py` (your part)

```python
read_addresses(stream) -> Iterator[str]
run_pipeline(addresses, database_dir, output_stream) -> None
validate_output(result) -> dict[str, str | None]
write_result(stream, result) -> None
```

- Reads raw UTF-8 strings, preserves content except input line terminator.
- Calls `build_index` **once**, then for each address calls `segment_address` → `search_address` → `write_result`.
- Validates that result contains exactly three fields and each is `str | None`.
- Does not perform normalization, Trie building, searching, ranking, or correction.
- Until teammate modules are implemented, actual execution must fail clearly, **never fabricate all-null results**.

## 5. Provisional local input/output contract

Input file: UTF-8 plain text, **one address per line** (empty lines represent empty address requests). Alternatively use `--address` for a single request or stdin for streaming lines.

Output: UTF-8 JSON Lines, one object per request. Example assuming corresponding canonical database entries exist:

```json
{"street": "Nguyễn Thị Minh Khai", "ward": "Phường Bến Thành", "province": "Thành phố Hồ Chí Minh"}
```

Unmatched example:

```json
{"street": null, "ward": "Phường Bến Thành", "province": "Thành phố Hồ Chí Minh"}
```

