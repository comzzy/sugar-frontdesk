# Sugar Nails · Front Desk

A booking front desk for **Sugar**, a nail tech in Lagos who can't answer customers while she's holding someone's hand and a brush.

Customers open the site on their phone and chat with the front desk, which talks like a Lagos front desk (English with a little Pidgin). It collects their name, phone number, services, style, colours, length, shape, allergies and preferred time, shows the total in naira, takes payment and puts them in Sugar's queue. Sugar keeps a PIN-protected queue page open on her phone or tablet. It shows who's next with the full order card, and she taps **Start** and **Done**.

The conversation is handled by **Qwen3-8B, LoRA fine-tuned on [Tinker](https://tinker-docs.thinkingmachines.ai/)** using a few hundred synthetic front-desk chats written in Sugar's voice. Every chat ends in a structured `<order>{…}</order>` block that the app parses.

| | |
|---|---|
| Customer site | `/` (hero, menu, styles & shades, booking chat, payment, live queue ticket) |
| Sugar's queue | `/queue` (PIN `2580` by default, set `QUEUE_PIN`) |
| Model | `Qwen/Qwen3-8B` + LoRA rank 32, renderer `qwen3_disable_thinking` |
| Checkpoint | `tinker://00631ae2-a716-5a02-882b-28a1cdeccbbe:train:0/sampler_weights/sugar-frontdesk-final` |

## Results (base Qwen3-8B vs Sugar's fine-tune)

Held-out synthetic chats (40 conversations, final booking turn + one mid-conversation turn each):

| metric | base Qwen3-8B | **fine-tuned** | rule-based fallback |
|---|---|---|---|
| valid `<order>` JSON | 72.5% | **100%** | 92.5% |
| field accuracy (9 fields) | 63.6% | **99.4%** | 86.4% |
| whole order exactly right | 22.5% | **95%** | 52.5% |
| total price correct | 35% | **92.5%** | 82.5% |
| asks for the right next detail | 60% | **95%** | 90% |
| offers the right quick-reply chips | 17.5% | **97.5%** | 92.5% |
| mean reply length (chars) | 89.7 | **50.0** | 48.4 |

Live rollouts on 12 **hand-written** messy chats (Pidgin, typos, several details in one message, corrections), where an oracle answers follow-up questions:

| metric | base | **fine-tuned** | rule-based |
|---|---|---|---|
| booking completed | 50% | **100%** | 100% |
| field accuracy | 41.7% | **99.1%** | 94.4% |
| whole order exactly right | 8.3% | **91.7%** | 50% |
| total price correct | 33.3% | **100%** | 83.3% |

Raw numbers: `training/results/eval_results.json`, `training/results/eval_live_results.json`. Transcripts: `training/results/eval_transcripts.jsonl`, `training/results/eval_live_transcripts.json`.

Training: 1,751 per-turn examples (1.87M tokens/epoch), 2 epochs, batch 32, 108 steps, LR 4.7e-4 with linear decay. Mean NLL went from 1.87 to 0.036. It took about 5 minutes on Tinker and cost roughly **$1.65** (3.74M training tokens × $0.44/M for Qwen3-8B), plus a few cents of sampling for evals.

## How it fits together

```
customer phone ──► public/index.html + static/app.js
                      │  POST /api/chat  (full chat history)
                      ▼
                 app/main.py (FastAPI)
                      ├─► app/llm.py ──► Tinker OpenAI-compatible /completions
                      │                  (Sugar's LoRA checkpoint, Qwen3 chat format)
                      ├─► app/engine.py  ScriptedEngine fallback if Tinker is slow/unavailable
                      ├─► normalise_order(): validate against the menu, recompute the price
                      ├─► /api/pay/*  Paystack (if PAYSTACK_SECRET_KEY) or labelled test payment
                      └─► app/db.py  SQLite queue  ◄── public/queue.html (Sugar, PIN) polls every 3s
```

* **The model drives the conversation.** The server never trusts its arithmetic: the order is validated against `app/menu.py` and the total is recomputed before payment. The model's own total is still logged for evaluation.
* **Graceful fallback.** If Tinker takes longer than `INFERENCE_TIMEOUT` (12s), errors, or returns a malformed order, that turn is answered by `ScriptedEngine`. This deterministic engine rebuilds the booking state from the customer's messages, so the chat never gets stuck. Without `TINKER_API_KEY`, the whole site runs on the fallback.
* **Payments.** If `PAYSTACK_SECRET_KEY` is set (use a `sk_test_…` key for test mode), "Pay" opens Paystack's hosted checkout and the callback verifies the amount before the booking joins the queue. With no key, the site shows a clearly labelled **test payment** sheet and no money moves. No keys are bundled.

## Run it locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export TINKER_API_KEY=...            # optional; without it the fallback engine answers
export QUEUE_PIN=2580                # Sugar's PIN
# export PAYSTACK_SECRET_KEY=sk_test_...   # optional, real Paystack test checkout
uvicorn main:app --app-dir app --port 8090
# customer site: http://localhost:8090   queue: http://localhost:8090/queue
```

## Reproduce the model

```bash
pip install -r requirements-train.txt
python training/gen_dataset.py      # 360 train + 40 eval synthetic chats -> training/data/*.jsonl
python training/train_sft.py        # LoRA SFT on Tinker -> training/results/checkpoint.json
python training/eval.py --model both
python training/eval_live.py
```

* `training/gen_dataset.py`: a customer simulator samples a true booking and chats in varied Nigerian English/Pidgin. It taps chips or types freely, packs several details into one message, sends bad phone numbers, asks prices and changes colours. Assistant turns are written from the ground truth in Sugar's voice, so every target order and total is correct.
* `training/train_sft.py`: uses the Tinker SDK and `tinker_cookbook` renderers. Each assistant turn becomes its own example (Qwen3's renderer strips history, so per-turn examples match inference exactly), with loss only on that turn.
* `training/eval.py` / `training/eval_live.py`: base vs fine-tuned (vs rules), sampled through Tinker's `SamplingClient` at temperature 0.

## Tests & screenshots

```bash
pip install playwright && playwright install chromium
python tests/e2e.py http://localhost:8090
```

This drives two full bookings, one tapping chips on desktop and one typed in Pidgin on mobile, through payment and into the queue, then presses Start and Done on Sugar's dashboard. Screenshots go to `screenshots/`.

## Deploying

* **Vercel**: `vercel.json` is included and FastAPI is auto-detected from `app/main.py`, with static assets in `public/`. Set `TINKER_API_KEY` (and optionally `QUEUE_PIN`, `PAYSTACK_SECRET_KEY`) in the project's environment variables. Note that Vercel functions are stateless, so the SQLite queue lives in `/tmp` and resets on cold starts. That's fine for a demo. For real use, point `DB_PATH` at a persistent disk (Render or Fly) or swap in Postgres.
* **Anywhere else**: `uvicorn main:app --app-dir app --host 0.0.0.0 --port $PORT`.

## Design notes

Everything visual is hand-built with CSS and inline SVG: the liquid polish swirls, the rotating 14-shade swatch wheel, the dripping polish bottle, the nail-style previews, the sparkles and the logo (`public/static/logo.svg`). There are **no photos and no AI-generated images**. Fonts are Lobster and DM Sans from Google Fonts (SIL Open Font License). Motion includes entrance and scroll reveals, bubbles, chat typing dots, chips animating in, a payment success check with polish-drop confetti, and FLIP-animated queue cards. All of it is turned off under `prefers-reduced-motion`.

The salon phone number, Instagram handle and address in the footer are placeholders for Sugar to replace.
