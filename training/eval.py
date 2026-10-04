"""Before/after evaluation: base Qwen3-8B vs Sugar's fine-tuned LoRA (plus the rule-based fallback).

On 40 held-out synthetic conversations:
  * FINAL turn  - give everything up to the customer's last detail, ask for the booking summary.
      json_valid      : an <order>{...}</order> block that parses as JSON
      field_acc       : mean accuracy over name, phone, services, style, colours, length, shape, notes, time
      exact_order     : every field correct
      price_correct   : model's total == menu price of the *true* order
  * MID turn    - one random earlier turn per conversation.
      right_question  : asks for the correct next detail
      tone            : warm Port Harcourt voice (Pidgin/warm markers), short (< 320 chars), single question
      chips           : offers valid quick-reply chips when the next detail has fixed choices

Usage: python training/eval.py [--model base|tuned|both] [--n 40]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

import tinker
from tinker import types
from tinker_cookbook import renderers
from tinker_cookbook.tokenizer_utils import get_tokenizer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "app"))
from engine import ScriptedEngine, parse_reply  # noqa: E402
from menu import compute_total  # noqa: E402

BASE_MODEL = "Qwen/Qwen3-8B"
FIELDS = ["name", "phone", "services", "style", "colours", "length", "shape", "notes", "time"]
SLOT_PATTERNS = {
    "name": r"\bname\b|call you", "phone": r"number|phone", "services": r"service|what are we doing|what would you like|done today",
    "style": r"style|design", "colours": r"colou?r", "length": r"length|how long", "shape": r"shape",
    "notes": r"allerg|notes|should know", "time": r"time|when",
}
GENERIC = re.compile(r"how can i (help|assist)|i'?d be (happy|glad)|certainly!|as an ai|feel free to|let me know if|\*\*|^#", re.I | re.M)
WARM = re.compile(r"\b(o|abeg|wahala|sharp sharp|my dear|love|dear|well well|dey|wetin|na)\b|💅|💖|😊", re.I)


def norm(v):
    if isinstance(v, list):
        return sorted(str(x).strip().lower() for x in v)
    s = str(v or "").strip().lower()
    return re.sub(r"\D", "", s)[-10:] if re.fullmatch(r"[+\d\s-]{8,}", s) else s


def score_order(order, gold):
    if not isinstance(order, dict):
        return {"field_acc": 0.0, "exact": 0, "price": 0, "fields": {f: 0 for f in FIELDS}}
    fields = {f: int(norm(order.get(f)) == norm(gold.get(f))) for f in FIELDS}
    true_total = compute_total(gold["services"], gold["style"], gold["length"])
    try:
        price = int(int(order.get("total")) == true_total)
    except (TypeError, ValueError):
        price = 0
    return {"field_acc": sum(fields.values()) / len(FIELDS), "exact": int(all(fields.values())), "price": price, "fields": fields}


def expected_slot(next_assistant: str):
    for slot in ["phone", "services", "style", "colours", "length", "shape", "notes", "time", "name"]:
        if re.search(SLOT_PATTERNS[slot], next_assistant.split("\n")[0], re.I):
            return slot
    return None


def build_cases(rows, rng):
    cases = []
    for r in rows:
        msgs = r["messages"]
        a_idx = [i for i, m in enumerate(msgs) if m["role"] == "assistant" and i >= 2]
        # last booking summary (after any "change the colour" request) must match the final goal
        final = [i for i in a_idx if "<order>" in msgs[i]["content"]][-1]
        mids = [i for i in a_idx if i < final and "[" in msgs[i]["content"] and "Good question" not in msgs[i]["content"] and "no complete" not in msgs[i]["content"] and "missing" not in msgs[i]["content"]]
        mid = rng.choice(mids)
        cases.append({"id": r["id"], "kind": "final", "prefix": msgs[:final], "gold": r["goal"], "ref": msgs[final]["content"]})
        cases.append({"id": r["id"], "kind": "mid", "prefix": msgs[:mid], "gold": r["goal"], "ref": msgs[mid]["content"],
                      "slot": expected_slot(msgs[mid]["content"])})
    return cases


def score_mid(text, case):
    p = parse_reply(text)
    first = p["text"]
    slot = case["slot"]
    right = int(bool(slot) and bool(re.search(SLOT_PATTERNS[slot], first, re.I)) and "<order>" not in text)
    # "on voice": short, one question at a time, no generic-chatbot phrasing or markdown
    tone = int(len(first) < 220 and first.count("?") <= 1 and not GENERIC.search(text))
    warm = int(bool(WARM.search(first)))
    ref_chips = parse_reply(case["ref"])["chips"]
    chips = int(bool(p["chips"]) and len(set(p["chips"]) & set(ref_chips)) >= max(1, len(ref_chips) // 2)) if ref_chips else 1
    return {"right_question": right, "tone": tone, "warm": warm, "chips": chips, "chars": len(first)}


async def run_model(label, sampler, renderer, tokenizer, cases):
    params = types.SamplingParams(max_tokens=400, temperature=0.0, stop=renderer.get_stop_sequences())
    sem = asyncio.Semaphore(16)

    async def one(c):
        async with sem:
            prompt = renderer.build_generation_prompt(c["prefix"])
            t = time.time()
            res = await sampler.sample_async(prompt=prompt, num_samples=1, sampling_params=params)
            msg, _ = renderer.parse_response(res.sequences[0].tokens)
            content = msg["content"] if isinstance(msg["content"], str) else renderers.get_text_content(msg)
            return content, time.time() - t
    outs = await asyncio.gather(*[one(c) for c in cases])
    return [o[0] for o in outs], [o[1] for o in outs]


def aggregate(label, cases, outputs, latencies=None):
    fin = [(c, o) for c, o in zip(cases, outputs) if c["kind"] == "final"]
    mid = [(c, o) for c, o in zip(cases, outputs) if c["kind"] == "mid"]
    fs = []
    for c, o in fin:
        p = parse_reply(o)
        s = score_order(p["order"], c["gold"])
        s["json_valid"] = int(p["order"] is not None)
        fs.append(s)
    ms = [score_mid(o, c) for c, o in mid]
    mean = lambda xs: round(sum(xs) / max(len(xs), 1), 3)
    agg = {
        "model": label,
        "json_valid": mean([s["json_valid"] for s in fs]),
        "field_accuracy": mean([s["field_acc"] for s in fs]),
        "exact_order": mean([s["exact"] for s in fs]),
        "price_correct": mean([s["price"] for s in fs]),
        "per_field": {f: mean([s["fields"][f] for s in fs]) for f in FIELDS},
        "right_question": mean([s["right_question"] for s in ms]),
        "on_voice": mean([s["tone"] for s in ms]),
        "warm_marker_rate": mean([s["warm"] for s in ms]),
        "mean_reply_chars": round(mean([s["chars"] for s in ms]), 1),
        "chips": mean([s["chips"] for s in ms]),
    }
    if latencies:
        agg["mean_latency_s"] = round(sum(latencies) / len(latencies), 2)
    return agg


def run_rules(cases):
    eng = ScriptedEngine()
    outs = []
    for c in cases:
        users = [m["content"] for m in c["prefix"] if m["role"] == "user"]
        outs.append(eng.respond(users))
    return outs


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="both")
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(HERE / "data/eval.jsonl")][: args.n]
    cases = build_cases(rows, random.Random(1))
    tokenizer = get_tokenizer(BASE_MODEL)
    renderer = renderers.get_renderer("qwen3_disable_thinking", tokenizer)
    service = tinker.ServiceClient()
    results, transcripts = {}, {}
    rpath = HERE / "results/eval_results.json"
    if rpath.exists():
        results = json.loads(rpath.read_text()).get("results", {})
    targets = []
    if args.model in ("base", "both"):
        targets.append(("base", service.create_sampling_client(base_model=BASE_MODEL)))
    if args.model in ("tuned", "both"):
        ck = json.loads((HERE / "results/checkpoint.json").read_text())
        targets.append(("fine_tuned", service.create_sampling_client(model_path=ck["sampler_path"])))
    for label, sampler in targets:
        outs, lats = await run_model(label, sampler, renderer, tokenizer, cases)
        results[label] = aggregate(label, cases, outs, lats)
        transcripts[label] = outs
        print(json.dumps(results[label], indent=1))
    rule_outs = run_rules(cases)
    results["rule_based_fallback"] = aggregate("rule_based_fallback", cases, rule_outs)
    transcripts["rule_based_fallback"] = rule_outs
    print(json.dumps(results["rule_based_fallback"], indent=1))
    rpath.write_text(json.dumps({"n_conversations": len(rows), "results": results}, indent=1))
    # transcripts
    tpath = HERE / "results/eval_transcripts.jsonl"
    old = {}
    if tpath.exists():
        for l in open(tpath):
            d = json.loads(l)
            old[(d["id"], d["kind"])] = d
    for i, c in enumerate(cases):
        d = old.get((c["id"], c["kind"]), {"id": c["id"], "kind": c["kind"],
                                           "last_user": c["prefix"][-1]["content"], "reference": c["ref"]})
        for label, outs in transcripts.items():
            d[label] = outs[i]
        old[(c["id"], c["kind"])] = d
    with open(tpath, "w") as f:
        for d in old.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
