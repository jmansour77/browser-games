# Deterministic table demo — no model or new GGUF

The no-training constraints do not give us a justified way to construct useful
free-form bilingual table QA from scratch. A compatible architecture, converter
and GGUF container do not supply parsing or language behavior. This implementation
therefore uses deterministic parsing and decimal arithmetic, with no neural
parameters, embeddings, training, pretrained weights, or model downloads.
The earlier `linear_algebra_wsp` demonstration is separate and is not used here.

No identifiable NCSI table sample was available in this repository. **All supplied
tables are synthetic demonstration only, not official Oman statistics.** The schema
is a proposed annual wide-table contract, not a verified NCSI publication template.
Generalization tests establish this contract only. Real NCSI samples are needed to
validate or adapt a reusable schema before claiming publication coverage.

## Run (Python 3.9+, no installs or third-party packages)

From the repository root, use the installed interpreter:

```powershell
$tablePython = 'C:\Users\Jaffar.Mansour\.venv\Scripts\python.exe'
& $tablePython .\ncsi_table_demo\table_demo.py --test
& $tablePython .\ncsi_table_demo\table_demo.py --input .\ncsi_table_demo\heldout.json --query .\ncsi_table_demo\lookup.json
& $tablePython .\ncsi_table_demo\table_demo.py --input .\ncsi_table_demo\heldout.json --query .\ncsi_table_demo\difference.json
& $tablePython .\ncsi_table_demo\table_demo.py --input .\ncsi_table_demo\heldout_changed.json --query .\ncsi_table_demo\difference.json
& $tablePython .\ncsi_table_demo\table_demo.py --input .\ncsi_table_demo\heldout.json --output .\ncsi_table_demo\normalized.json
```

On another machine replace `& $tablePython` with `python`. The checked-in fixtures
are ready to use; `--make-demo` is only for creating them in a fresh directory and
refuses overwrites. There is no LM Studio execution for this task and no LM Studio
test prompt: the commands above are deterministic-demo tests.

## Supported input contract

Read `example.json` and `heldout.json` for complete examples. Input is one UTF-8
JSON object with `metadata`, `headers` and `rows`. No CSV, XLSX, DOCX, PDF, website,
OCR, or merged-cell extraction is implemented. The unrelated DOCX in this repository
is not an NCSI sample and was not parsed.

- Metadata requires `document_id`, `table_id`, language-keyed `title`, `units`,
  `measure`, `evidence_kind`, `notes` (list) and `source` (object). Bilingual
  descriptions, titles, notes and any extra metadata are preserved verbatim.
- Headers are exactly the ordered dimensions in `schema.json`, then `Role`, then
  one or more distinct ASCII four-digit years. The supplied dimensions are `Area`
  and `Category`; the parser never restricts their members to fixture labels.
- Every row has exactly the header width, explicit nonempty dimension labels,
  a role `detail` or `total`, and plain decimal **strings** for all annual cells.
  Decimal strings preserve exact values without binary floating-point rounding.
- There is one measure and one unit per table. No implicit carry-forward, unit
  conversion, scale inference, fuzzy matching, missing-value imputation or label
  translation. Whitespace-padded labels, footnoted numbers, thousands separators,
  formulas and missing markers require review rather than guessed conversions.
- `total` means the sum of every detail row over `Area`, within the same Category
  and period. There must be at most one total in each such group. Other subtotal
  hierarchies require a different explicit schema. No total is inferred from a
  member named "All"; totals are identified by the structural role column.
- `source` can preserve URI, page and sheet. Optional `start_row` and `start_column`
  are positive one-based coordinates of the header's first cell. Page/sheet/cell
  values supplied by a caller are preserved, not independently authenticated.
  A declared grid origin computes each source cell; without one it is not invented.

Normalization produces long observations with period, dimensions, measure, unit,
decimal value, role and provenance. Provenance includes the actual JSON pointer,
header pointer, input-file SHA256, document/table IDs, supplied source and optional
source cell coordinates. Dimension-label coordinates are retained separately;
metadata remains under `metadata` and its original metadata keys retain identity.
Candidate code lists are distinct source labels, explicitly **not official codes**.

`validated_structure` means all implemented structural/numeric/total checks passed,
not that the source is authoritative or semantically verified. Confidence is
uncalibrated (`score: null`), with its basis stated. Invalid tables have issues and
`needs_review`; queries are blocked. Normalization exits 2 for review and testing
exits 1 for a failed assertion. Malformed inputs may be rejected with a review
message instead of a normalized artifact.

## Explicit query grammar

Queries are JSON, not natural-language prompts. All selectors require every
dimension plus `period`, matched exactly and case-sensitively:

```json
{"op":"lookup","select":{"Area":"East","Category":"B","period":"2031"}}
```

```json
{"op":"difference","left":{"Area":"East","Category":"B","period":"2031"},"right":{"Area":"East","Category":"B","period":"2030"}}
```

`difference` returns left minus right; `compare` uses the same selectors and returns
`greater`, `equal` or `less`. Selectors can differ by period or dimensions within
one table. Answers include the exact contributing observations, source coordinates,
notes, title and other metadata. Ambiguous, incomplete or absent matches fail.
Unicode text is preserved, but Arabic query interpretation/matching aliases and
free-form English questions are **not supported or tested**.

## Evaluation and mutation demonstration

The same `schema.json` and parser process both example and held-out tables. The
held-out document ID is `synthetic-heldout`, table ID `unseen-B`, periods 2030/2031,
dimension members East/West and category B; none are parser constants. Example
IDs, periods 2020/2021, North/South and category A are distinct. Fixtures and
expected test values occur only in the fixture/test functions, never in parsing
or answering logic.

Expected held-out lookup: `11.25`; period difference: `1.00`. The changed fixture
differs in exactly one source cell (`/rows/0/4`, supplied sheet Demo row 2 column 5):
`11.25` becomes `14.25`. Its normalized observation and lookup become `14.25`,
and the difference becomes `4.00`; its input hash also changes. This held-out table
has no totals. Separately the tests check example totals and ensure a changed
detail with an unchanged declared total is flagged for review.

Embedded tests cover exact held-out lookup, arithmetic and source mutation,
comparison, valid/invalid totals, shuffled headers, ragged rows, duplicate keys,
missing dimensions, invalid numbers, invalid coordinates, missing units,
incomplete selectors and unmatched selectors. They do not establish coverage of
any real publication, neural inference, document extraction or Arabic semantics.

Actual execution on 2026-11-06: all five test methods passed (including seven
review-gate subcases). Separate CLI executions against the saved fixtures produced
`normalized.json`, `answer_lookup.json` (11.25), `answer_difference.json` (1.00)
and `answer_changed.json` (4.00). Those answer artifacts retain the contributing
source-cell pointers, original metadata and source-file hashes. The mutation test
also verified the changed normalized value 14.25 and changed hash.

## References checked

- [llama.cpp model formats and conversion](https://github.com/ggml-org/llama.cpp/blob/master/docs/models.md): GGUF is required for local models; conversion scripts transform model formats.
- [Maintained HF converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_hf_to_gguf.py): supported architecture dispatch, config and tensor conversion; not a behavior generator.
- [LM Studio import](https://lmstudio.ai/docs/app/advanced/import-model): compatible local GGUF files can be imported with `lms import`.
- [Hugging Face causal LM from scratch](https://huggingface.co/learn/llm-course/en/chapter7/6): initialization is followed by training, which is forbidden here.
- [Supplied OpenReview paper](https://openreview.net/forum?id=plH8gW7tPQ): both forum and PDF access encountered browser verification. Its contents were not independently verified and are not used as evidence for this implementation.

No new GGUF, checkpoint, conversion command or LM Studio test is supplied because
no justified neural table-processing model was built.
