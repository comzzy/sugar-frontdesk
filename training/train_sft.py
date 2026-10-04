"""LoRA fine-tune Qwen3-8B on Sugar's front-desk conversations with Tinker.

Each assistant turn becomes its own training example (the Qwen3 renderer strips
thinking from history, so per-turn examples match inference exactly), with loss only
on that assistant message.

Usage:  TINKER_API_KEY=... python training/train_sft.py
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import tinker
from tinker import types
from tinker_cookbook import renderers
from tinker_cookbook.hyperparam_utils import get_lr
from tinker_cookbook.supervised.data import conversation_to_datum
from tinker_cookbook.tokenizer_utils import get_tokenizer

BASE_MODEL = "Qwen/Qwen3-8B"
RENDERER = "qwen3_disable_thinking"   # fast, direct answers (no chain-of-thought)
LORA_RANK = 32
BATCH_SIZE = 32
EPOCHS = 2
KEEP_PROB = 0.5                         # subsample ordinary turns to keep cost modest
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def build_examples(rows, rng):
    """One (prefix -> assistant message) example per kept assistant turn."""
    examples = []
    for r in rows:
        msgs = r["messages"]
        for i, m in enumerate(msgs):
            if m["role"] != "assistant" or i < 2 or msgs[i - 1]["role"] != "user":
                continue
            important = "<order>" in m["content"] or "No wahala" in m["content"] or "Good question" in m["content"] or "missing" in m["content"] or "no complete" in m["content"]
            if important or rng.random() < KEEP_PROB:
                examples.append(msgs[: i + 1])
    return examples


def main():
    t0 = time.time()
    rng = random.Random(0)
    rows = [json.loads(l) for l in open(HERE / "data/train.jsonl")]
    convs = build_examples(rows, rng)
    tokenizer = get_tokenizer(BASE_MODEL)
    renderer = renderers.get_renderer(RENDERER, tokenizer)
    data = [conversation_to_datum(c, renderer, max_length=2048,
                                  train_on_what=renderers.TrainOnWhat.LAST_ASSISTANT_MESSAGE) for c in convs]
    n_tokens = sum(d.model_input.length for d in data)
    print(f"{len(data)} examples, {n_tokens:,} tokens per epoch")

    lr = get_lr(BASE_MODEL)
    print("learning rate", lr)
    service = tinker.ServiceClient()
    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=LORA_RANK)
    steps_per_epoch = len(data) // BATCH_SIZE
    total_steps = steps_per_epoch * EPOCHS
    log = []
    step = 0
    for epoch in range(EPOCHS):
        rng.shuffle(data)
        for b in range(steps_per_epoch):
            batch = data[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
            frac = step / total_steps
            cur_lr = lr * (1 - frac)  # linear decay
            fb = tc.forward_backward(batch, loss_fn="cross_entropy")
            op = tc.optim_step(types.AdamParams(learning_rate=cur_lr))
            fbr = fb.result()
            op.result()
            # mean per-token NLL over weighted tokens
            try:
                num = sum(float((o["logprobs"].to_torch() * d.loss_fn_inputs["weights"].to_torch()).sum())
                      for o, d in zip(fbr.loss_fn_outputs, batch))
                den = sum(float(d.loss_fn_inputs["weights"].to_torch().sum()) for d in batch)
                nll = -num / max(den, 1e-9)
            except Exception as e:  # never kill a paid run over logging
                nll = float("nan"); print("loss log error", e)
            log.append({"step": step, "epoch": epoch, "lr": cur_lr, "nll": nll, "t": round(time.time() - t0, 1)})
            print(f"step {step}/{total_steps} epoch {epoch} nll {nll:.4f} lr {cur_lr:.2e}", flush=True)
            step += 1
    ckpt = tc.save_weights_for_sampler(name="sugar-frontdesk-final").result()
    state = tc.save_state(name="sugar-frontdesk-final-state").result()
    info = {
        "base_model": BASE_MODEL, "renderer": RENDERER, "lora_rank": LORA_RANK, "batch_size": BATCH_SIZE,
        "epochs": EPOCHS, "examples": len(data), "tokens_per_epoch": n_tokens, "learning_rate": lr,
        "steps": total_steps, "sampler_path": ckpt.path, "state_path": state.path,
        "train_seconds": round(time.time() - t0, 1),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "train_log.json").write_text(json.dumps(log, indent=1))
    (RESULTS / "checkpoint.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
