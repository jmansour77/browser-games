# Analytically constructed linear algebra lookup GGUF

**Scope:** a finite lookup demonstration, not a general-purpose mathematical
language model. Every supported complete prompt is a tokenizer entry. Python
calculates the 690-case truth table during file generation and encodes its answers
in embedding/output weights. There is no training, fine-tuning, external dataset,
pretrained model, or inference-time Python calculator.

This does **not** fulfill a requirement for arbitrary numbers, dimensions, or
natural-language questions. That requires an explicitly constructed parser,
arithmetic circuit and output decoder inside the supported transformer graph.
GGUF is a storage format; converting weights does not supply those algorithms.
Such construction is not impossible in principle, but this small demonstration
does not implement it or claim arithmetic generalization.

## Files and generation

- `generate_model.py`: complete Python 3.9+ script, standard library only.
- `linear-algebra-lookup-F32.gguf`: weights, tokenizer and chat template together.

From this directory, with Python installed:

```powershell
python generate_model.py
```

No dependencies or conversion command are needed: the script writes GGUF v3
directly. Its output is deterministic. It also verifies the analytic next-token
logits for every supported input and every answer-to-EOS transition. This check
alone is not an external runtime test.

On the machine where this artifact was created, Python is available at
`C:\Users\Jaffar.Mansour\.venv\Scripts\python.exe`, but not on PATH. Use this
exact command from the project root to regenerate:

```powershell
& C:\Users\Jaffar.Mansour\.venv\Scripts\python.exe .\linear_algebra_wsp\generate_model.py
```

Architecture: standard `llama`, one block, one attention/KV head, embedding width
8, FFN width 8, context 512, float32. It has 17,448 stored scalar parameters,
1,061 vocabulary entries and occupies 111,680 bytes (109.06 KiB). This is a very
small supported configuration; no claim of a globally minimal architecture is made.

Attention and FFN matrices are zero, so the residual block passes embeddings
through. Each answer has a distinct 8-coordinate +/-1 code. A prompt's embedding
is its answer's code; output rows are eight times those codes. RMS normalization
scales all coordinates equally, so greedy decoding selects the matching answer.
Answer embeddings select EOS on the next step. Whole-prompt tokenization and
these weights implement a lookup, not compositional arithmetic.

## Load in LM Studio

Open LM Studio, then run:

```powershell
lms import .\linear-algebra-lookup-F32.gguf --copy --user-repo local/linear-algebra-lookup -y
lms load linear-algebra-lookup --identifier linear-algebra-lookup --gpu off --context-length 512 --parallel 1 -y
lms server start --port 1234
```

Skip `server start` if that port is already serving LM Studio. CPU execution is
the intended verification configuration. Select `linear-algebra-lookup` in a new
LM Studio chat. Use the model's embedded prompt template, temperature 0, and no
custom template or added suffix. The template renders only the last message's
content. Paste each exact prompt below with **no whitespace or extra prose**.

1. `vadd([1,-1],[0,1])` must return `[1,0]`.
2. `dot([1,-1],[-1,1])` must return `-2`.
3. `mmul([[1,1],[0,1]],[[1,0],[1,1]])` must return `[[2,1],[1,1]]`.

Verification uses exact response equality and requires normal EOS termination:

```powershell
python generate_model.py --verify samples
python generate_model.py --verify samples --chat
python generate_model.py --verify all
python generate_model.py --verify all --chat
```

The script makes actual HTTP requests to the named model on
`http://127.0.0.1:1234/v1`. Raw completions test the tokenizer and weights; chat
completions additionally test the embedded template. It exits nonzero on failure.
`--base-url` and `--model` override the endpoint and loaded model identifier.

## Observed verification (2026-11-06)

The delivered file was imported and successfully loaded in the installed LM
Studio with GPU offload disabled, context 512 and parallelism 1. Actual HTTP
inference returned:

- Raw `/v1/completions`: all three sample cases passed.
- `/v1/chat/completions`: all 690 supported cases passed, including EOS checks.
- LM Studio's selected runtime was `llama.cpp-win-x86_64-vulkan-avx2@2.13.0`;
  the model was explicitly loaded with `--gpu off`.

SHA256 of the tested GGUF:
`47749c1e325384c7187f21305e7b96c442239f7dde36328d2ceceacdd24823f4`.
These results cover the finite domain above, not out-of-domain generalization.

## Complete supported domain

- `vadd(a,b)` and `dot(a,b)`: each input is a two-element vector with entries
  from `{-1,0,1}`. 81 ordered pairs per operation.
- `madd(A,B)` and `mmul(A,B)`: each input is a 2x2 matrix with entries from
  `{0,1}`. 256 ordered pairs per operation.
- `transpose(A)`: each input is a 2x2 binary matrix. 16 cases.

Syntax uses compact JSON arrays, lowercase operation names and parentheses,
exactly as in the examples. Correctness is limited to these 690 whole inputs.
Unsupported input may produce `UNSUPPORTED`, an empty result, or an unrelated
answer. It is not a reliable input validator: matching a supported prompt as a
suffix can still return that prompt's answer. Do not interpret such behavior as
understanding a larger question.

## Primary implementation references

- [llama.cpp Llama tensor definitions and graph](https://github.com/ggml-org/llama.cpp/blob/master/src/models/llama.cpp)
- [llama.cpp tokenizer implementation](https://github.com/ggml-org/llama.cpp/blob/master/src/llama-vocab.cpp)
- [GGUF writer reference](https://github.com/ggml-org/llama.cpp/blob/master/gguf-py/gguf/gguf_writer.py)
- [LM Studio model import](https://lmstudio.ai/docs/cli/local-models/import)
- [LM Studio raw completions](https://lmstudio.ai/docs/developer/openai-compat/completions)
