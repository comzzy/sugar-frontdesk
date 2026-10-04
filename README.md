# Sugar Nails front desk

Sugar does nails in GRA, Port Harcourt. On a busy afternoon she's at her station with a client's hand in hers, a brush in the other, and her phone buzzing nonstop. "How much is acrylic?" "You get space by 4?" "Abeg send your account number." She can't put down a half-painted nail to reply, so messages pile up and some of those people book somewhere else.

The shop has the same problem. Walk-ins sit down and nobody is sure who came first. Somebody who arrived after them gets called before them, and Sugar ends up refereeing when she should be working.

This is a small website that does the front-desk part for her.

**Taking the booking.** A customer opens the site on their phone and chats with the front desk. It talks the way a Port Harcourt receptionist would: plain English with a bit of Pidgin, one question at a time. It asks for name, phone number, services, style, colours, length, shape, allergies and preferred time. They can tap options or just type "abeg I wan do gel x, long coffin, french tip", and it handles both. At the end it shows the full order and the total in naira.

**Payment up front.** The customer pays before joining the queue, so there are no "I'll transfer later" bookings and no chasing people. It uses Paystack checkout when a key is set. Without a key it shows a clearly labelled test payment and no money moves.

**Knowing who's next.** Sugar keeps `/queue` open on her phone or a tablet, behind a PIN. It shows who's in the chair, who's next and everyone after that, and each card has the full order: services, style, colours, length, shape, notes, price and whether they've paid. When she starts a client she taps **Start**, and when she finishes she taps **Done**. The page updates on its own and chimes when a new paid booking comes in. Each customer also gets a ticket showing their place in line, so nobody has to guess.

There's also a **Clear test bookings** button on the queue page (PIN-protected, and it asks first). It's for wiping practice bookings before going live.

## The model

The chat runs on Qwen3-8B, which I fine-tuned with LoRA on [Tinker](https://tinker-docs.thinkingmachines.ai/) using a few hundred practice chats written in Sugar's voice. Every booking ends with an `<order>{…}</order>` JSON block that the app reads.

- Base model: `Qwen/Qwen3-8B`, LoRA rank 32, renderer `qwen3_disable_thinking`
- Checkpoint: `tinker://00631ae2-a716-5a02-882b-28a1cdeccbbe:train:0/sampler_weights/sugar-frontdesk-final`

The server never takes the model's word on money. Every order is checked against the menu in `app/menu.py` and the total is recalculated before payment. If Tinker takes longer than 12 seconds, fails, or returns a broken order, a rule-based engine (`app/engine.py`) answers that turn instead. It rebuilds the booking from what the customer has said so far, so the chat never gets stuck. Without `TINKER_API_KEY`, the whole site runs on that engine.

The studio address lives in `menu.ADDRESS` and the system prompt. The model was trained before the address was corrected. A small guard in `engine.py` rewrites any wrong city in a reply, and if someone asks "where una dey?" it answers with GRA, Port Harcourt directly. That fix didn't need retraining.

### Training

- `training/gen_dataset.py` writes 360 training chats and 40 held-out ones. A simulated customer picks a real booking, then chats about it in different ways: tapping chips, typing in Pidgin, cramming three details into one message, giving a bad phone number, asking prices, changing their mind about colours. The front-desk replies are written from the true booking, so every target order and total is correct.
- `training/train_sft.py` uses the Tinker SDK and `tinker_cookbook` renderers. Each front-desk turn becomes its own example, with loss only on that turn.
- That came to 1,751 examples (1.87M tokens per epoch), 2 epochs, batch 32, 108 steps, learning rate 4.7e-4 with linear decay. Mean NLL went from 1.87 to 0.036. It took about 5 minutes and roughly **$1.65** (3.74M training tokens at $0.44/M), plus a few cents of sampling for the evals.
- Running it is cheap too. I replayed 5 held-out bookings (45 replies) through the live checkpoint: about 1,000 prompt tokens and 62 output tokens per reply. At Tinker's Qwen3-8B prices ($0.195/M prompt, $0.60/M output) that's about $0.00023 per reply and $0.0021 per booking, roughly ₦0.31 and ₦2.80 at ₦1,329.60/$ (CBN, 2 Oct 2026). Raw counts are in `training/results/inference_cost.json`.

### Did it help?

On the 40 held-out chats (the final booking turn plus one mid-chat turn each):

| | base Qwen3-8B | fine-tuned | rule-based |
|---|---|---|---|
| valid order JSON | 72.5% | **100%** | 92.5% |
| field accuracy (9 fields) | 63.6% | **99.4%** | 86.4% |
| whole order exactly right | 22.5% | **95%** | 52.5% |
| total price correct | 35% | **92.5%** | 82.5% |
| asks for the right next detail | 60% | **95%** | 90% |
| offers the right quick replies | 17.5% | **97.5%** | 92.5% |
| average reply length (chars) | 89.7 | **50.0** | 48.4 |

On 12 messy chats I wrote by hand (typos, Pidgin, corrections mid-chat), played out live with a script answering the model's questions:

| | base | fine-tuned | rule-based |
|---|---|---|---|
| booking completed | 50% | **100%** | 100% |
| field accuracy | 41.7% | **99.1%** | 94.4% |
| whole order exactly right | 8.3% | **91.7%** | 50% |
| total price correct | 33.3% | **100%** | 83.3% |

Raw numbers are in `training/results/eval_results.json` and `eval_live_results.json`, and transcripts are in `eval_transcripts.jsonl` and `eval_live_transcripts.json`.

## Running it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export TINKER_API_KEY=...                # optional; without it the rule-based engine answers
export QUEUE_PIN=2580                    # Sugar's PIN
# export PAYSTACK_SECRET_KEY=sk_test_... # optional, real Paystack test checkout
uvicorn main:app --app-dir app --port 8090
```

The customer site is at http://localhost:8090 and the queue is at http://localhost:8090/queue.

To rebuild the model:

```bash
pip install -r requirements-train.txt
python training/gen_dataset.py
python training/train_sft.py
python training/eval.py --model both
python training/eval_live.py
```

To run the end-to-end test (two full bookings, one tapping options on desktop and one typed in Pidgin on mobile, through payment, into the queue, then Start and Done), with screenshots saved to `screenshots/`:

```bash
pip install playwright && playwright install chromium
python tests/e2e.py http://localhost:8090
```

`python tests/record_demo.py <url>` records one booking at phone width and builds `screenshots/demo.gif` (needs ffmpeg). It makes one test booking, so delete it afterwards with `DELETE /api/queue/<id>` and the `X-Pin` header. Sugar can use the same call to remove a single booking.

## Deploying

It's live on Vercel at https://sugar-nails-nine.vercel.app. Vercel picks up FastAPI from `app/main.py` and serves `public/` as static files. Serverless functions don't share a disk, so when `BLOB_READ_WRITE_TOKEN` is set (from a private Vercel Blob store), each booking is saved as its own blob and every instance sees the same queue. Locally it uses SQLite. Set `TINKER_API_KEY`, and optionally `QUEUE_PIN` and `PAYSTACK_SECRET_KEY`, in the project's environment variables.

It runs anywhere else with `uvicorn main:app --app-dir app --host 0.0.0.0 --port $PORT`.

## Credits and notes

All the artwork is hand-made CSS and inline SVG: the polish swirls, the shade wheel, the dripping bottle, the nail previews and the logo. There are no photos and no generated images. Fonts are Lobster and DM Sans (SIL Open Font License). Animations switch off when the device asks for reduced motion.

The phone number and Instagram handle in the footer are placeholders for Sugar to swap in.
