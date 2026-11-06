#!/usr/bin/env python3
"""Build a finite lookup model, NOT a general-purpose algebra language model.

Python 3.9+, standard library only. No training, randomness or pretrained assets.
Entire supported prompts are atomic tokenizer entries. Python computes the finite
truth table at BUILD time; embedding/output weights store it. At inference time
LM Studio runs only the GGUF. The single Llama block is an identity residual.

  python generate_model.py
  python generate_model.py --verify samples
  python generate_model.py --verify all

Verification requires the generated GGUF loaded as 'linear-algebra-lookup' in
LM Studio and its local server on port 1234. No verification is claimed merely
by generating a file. Unsupported prompts have no correctness guarantee.
"""

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import urllib.request


DIM = 8
FFN = 8
EPS = 1e-5
MODEL_ID = "linear-algebra-lookup"
DEFAULT_OUT = Path(__file__).resolve().with_name("linear-algebra-lookup-F32.gguf")
SAMPLES = [
    ("vadd([1,-1],[0,1])", "[1,0]"),
    ("dot([1,-1],[-1,1])", "-2"),
    ("mmul([[1,1],[0,1]],[[1,0],[1,1]])", "[[2,1],[1,1]]"),
]


def compact(value):
    return json.dumps(value, separators=(",", ":"))


def cases():
    """Exhaustively enumerate a specified domain, not an external dataset."""
    vectors = list(itertools.product((-1, 0, 1), repeat=2))
    for a, b in itertools.product(vectors, repeat=2):
        args = compact(a) + "," + compact(b)
        yield "vadd(" + args + ")", compact([a[i] + b[i] for i in range(2)])
        yield "dot(" + args + ")", str(sum(a[i] * b[i] for i in range(2)))
    matrices = [[[a, b], [c, d]] for a, b, c, d in itertools.product((0, 1), repeat=4)]
    for a, b in itertools.product(matrices, repeat=2):
        args = compact(a) + "," + compact(b)
        yield "madd(" + args + ")", compact(
            [[a[i][j] + b[i][j] for j in range(2)] for i in range(2)])
        yield "mmul(" + args + ")", compact(
            [[sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)] for i in range(2)])
    for a in matrices:
        yield "transpose(" + compact(a) + ")", compact(
            [[a[j][i] for j in range(2)] for i in range(2)])


def code(index):
    """Distinct +/-1 vertices: a vector's dot product is maximal with itself."""
    if not 0 <= index < 2 ** DIM:
        raise ValueError("Output vocabulary exceeds the binary code capacity")
    return [1.0 if (index >> bit) & 1 else -1.0 for bit in range(DIM)]


def construct():
    table = dict(cases())
    assert len(table) == 690
    for prompt, answer in SAMPLES:
        assert table[prompt] == answer
    answers = sorted(set(table.values())) + ["UNSUPPORTED"]
    # IDs: unk=0, bos=1, eos=2, all byte fallbacks, prompts, then answers.
    tokens = ["<unk>", "<s>", "</s>"] + [f"<0x{i:02X}>" for i in range(256)]
    types = [2, 3, 3] + [6] * 256  # GGUF UNKNOWN, CONTROL, BYTE
    tokens += list(table)
    types += [4] * len(table)  # USER_DEFINED: whole exact prompt is one token
    tokens += answers
    types += [1] * len(answers)  # NORMAL: outputs are visible text
    assert len(tokens) == len(set(tokens))
    ids = {token: i for i, token in enumerate(tokens)}
    targets = ["</s>"] + answers
    codes = {target: code(i) for i, target in enumerate(targets)}
    embeddings = [codes["UNSUPPORTED"][:] for _ in tokens]
    output = [[0.0] * DIM for _ in tokens]
    for target in targets:
        # Logit margin >=16/sqrt(1+EPS); use greedy decoding nevertheless.
        output[ids[target]] = [8.0 * x for x in codes[target]]
        embeddings[ids[target]] = codes["</s>"][:]
    for prompt, answer in table.items():
        embeddings[ids[prompt]] = codes[answer][:]

    # Check constructed next-token logits exhaustively, including EOS.
    # This does not test the external runtime or tokenizer; --verify does that.
    for source, target in list(table.items()) + [(a, "</s>") for a in answers]:
        h = embeddings[ids[source]]
        logits = [sum(x * y for x, y in zip(h, row)) / math.sqrt(1 + EPS)
                  for row in output]
        assert max(range(len(logits)), key=logits.__getitem__) == ids[target]

    # Shapes are GGML dimension order: input/contiguous dimension first.
    tensors = [
        ("token_embd.weight", (DIM, len(tokens)), sum(embeddings, [])),
        ("output.weight", (DIM, len(tokens)), sum(output, [])),
        ("output_norm.weight", (DIM,), [1.0] * DIM),
        ("blk.0.attn_norm.weight", (DIM,), [1.0] * DIM),
        ("blk.0.ffn_norm.weight", (DIM,), [1.0] * DIM),
    ]
    for name in ("attn_q", "attn_k", "attn_v", "attn_output"):
        tensors.append((f"blk.0.{name}.weight", (DIM, DIM), [0.0] * (DIM * DIM)))
    for name, shape in (("ffn_gate", (DIM, FFN)), ("ffn_up", (DIM, FFN)),
                        ("ffn_down", (FFN, DIM))):
        tensors.append((f"blk.0.{name}.weight", shape, [0.0] * (DIM * FFN)))
    return tokens, types, tensors


def string(value):
    data = value.encode("utf-8")
    return struct.pack("<Q", len(data)) + data


def encode(kind, value):
    # GGUF value types used here: uint32=4, int32=5, float32=6,
    # bool=7, string=8, array=9. No third-party GGUF writer needed.
    if kind == 8:
        return string(value)
    if kind == 9:
        subtype, items = value
        return struct.pack("<IQ", subtype, len(items)) + b"".join(
            encode(subtype, item) for item in items)
    return struct.pack({4: "<I", 5: "<i", 6: "<f", 7: "<?"}[kind], value)


def write_model(path):
    tokens, types, tensors = construct()
    metadata = [
        ("general.architecture", 8, "llama"),
        ("general.name", 8, "Linear algebra finite lookup (690 exact inputs)"),
        ("general.description", 8, "Analytically constructed finite lookup; no training. "
         "Whole-prompt tokens; identity transformer; no arithmetic generalization."),
        ("general.file_type", 4, 0),  # ALL_F32
        ("general.alignment", 4, 32),
        ("llama.context_length", 4, 512),
        ("llama.embedding_length", 4, DIM),
        ("llama.block_count", 4, 1),
        ("llama.feed_forward_length", 4, FFN),
        ("llama.attention.head_count", 4, 1),
        ("llama.attention.head_count_kv", 4, 1),
        ("llama.rope.dimension_count", 4, DIM),
        ("llama.rope.freq_base", 6, 10000.0),
        ("llama.attention.layer_norm_rms_epsilon", 6, EPS),
        ("tokenizer.ggml.model", 8, "llama"),
        ("tokenizer.ggml.tokens", 9, (8, tokens)),
        ("tokenizer.ggml.scores", 9, (6, [0.0] * len(tokens))),
        ("tokenizer.ggml.token_type", 9, (5, types)),
        ("tokenizer.ggml.unknown_token_id", 4, 0),
        ("tokenizer.ggml.bos_token_id", 4, 1),
        ("tokenizer.ggml.eos_token_id", 4, 2),
        ("tokenizer.ggml.add_bos_token", 7, True),
        ("tokenizer.ggml.add_eos_token", 7, False),
        ("tokenizer.ggml.add_space_prefix", 7, False),
        # Deliberately only the last message, no system text or role markers.
        ("tokenizer.chat_template", 8, "{{ messages[-1]['content'] }}"),
    ]
    header = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(metadata))
    header += b"".join(string(key) + struct.pack("<I", kind) + encode(kind, value)
                       for key, kind, value in metadata)
    payload = bytearray()
    params = 0
    for name, shape, values in tensors:
        assert math.prod(shape) == len(values)
        payload.extend(b"\0" * (-len(payload) % 32))
        header += string(name) + struct.pack("<I", len(shape))
        header += struct.pack("<" + "Q" * len(shape), *shape)
        header += struct.pack("<IQ", 0, len(payload))  # GGML F32=0
        payload.extend(struct.pack("<" + "f" * len(values), *values))
        params += len(values)
    header += b"\0" * (-len(header) % 32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload)
    print(f"Wrote {path}\n{params:,} stored parameters; {path.stat().st_size:,} bytes; "
          f"{len(tokens)} tokens.\nSHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}")
    print("Analytic logit checks passed. Actual LM Studio inference is NOT tested by this step.")


def verify(base_url, model, exhaustive, chat):
    selected = list(cases()) if exhaustive else SAMPLES
    endpoint = "/chat/completions" if chat else "/completions"
    failures = []
    for i, (prompt, expected) in enumerate(selected, 1):
        body = {"model": model, "temperature": 0, "max_tokens": 4, "stream": False}
        if chat:
            body["messages"] = [{"role": "user", "content": prompt}]
        else:
            body["prompt"] = prompt
        request = urllib.request.Request(base_url.rstrip("/") + endpoint,
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
        choice = result["choices"][0]
        actual = choice["message"]["content"] if chat else choice["text"]
        # Exact comparison, including whitespace; require EOS, not truncation.
        ok = actual == expected and choice.get("finish_reason") == "stop"
        if not ok:
            failures.append({"prompt": prompt, "expected": expected, "actual": actual,
                             "finish_reason": choice.get("finish_reason")})
        if not exhaustive or not ok:
            print(f"{'PASS' if ok else 'FAIL'} {prompt} -> {actual!r}; expected {expected!r}", flush=True)
        elif i % 100 == 0:
            print(f"Verified {i}/{len(selected)}", flush=True)
    print(f"LM Studio {endpoint}: {len(selected) - len(failures)}/{len(selected)} passed.")
    if failures:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", choices=("samples", "all"))
    parser.add_argument("--chat", action="store_true", help="Verify chat template instead of raw completions")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default=MODEL_ID)
    args = parser.parse_args()
    if args.verify:
        verify(args.base_url, args.model, args.verify == "all", args.chat)
    else:
        write_model(args.output)


if __name__ == "__main__":
    main()
