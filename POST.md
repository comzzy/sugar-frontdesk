---
title: I fine-tuned an open model to be the front desk at my friend's nail studio
published: false
tags: hf26challenge, devchallenge, ai, opensource
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/devteam/join-the-hacktoberfest-weekend-challenge-build-for-a-friend-2450-in-prizes-across-17-winners-1aj5)*

## Meet Sugar

Sugar does nails in Lagos. Gel, acrylic, Gel-X, BIAB, French tips, chrome, little hand-painted flowers, all of it. She's good, so she's busy.

She has one problem, and I've watched it happen many times: **her hands are always full.** She has a client's hand in one hand and a brush in the other when the next customer walks in, or her phone lights up with *"Hi dear, are you free today? How much is acrylic?"* She can't stop to answer. She can't write down who came first. She can't ask whether you want coffin or almond, nude or wine, or whether you're allergic to anything. So people wait, people leave, and the order of who's next lives in her head.

She doesn't need a big salon software suite. She needs a **front desk**: someone who greets people, takes down exactly what they want, tells them the price, collects payment and hands her a clean list of who's next.

So I built her one.

## What I Built

**Sugar Nails · Front Desk** has two screens:

1. **The customer site** (on the customer's phone, from a link or a QR code at her station). A chat with the front desk greets you, takes your name and number, then asks what you want: the service, the style or design, colours, length, shape, allergies or notes, and what time. You can tap the options or just type how you talk, in English or Pidgin. You see the full order and the total in naira, pay, and get a live ticket: *"You're #2 · 1 person ahead of you."*
2. **Sugar's queue** (PIN-protected, on her phone or tablet). This shows who's in the chair, who's next and everyone's order card: services, style, colour swatches, length, shape, a highlighted allergy note, the price and whether they've paid. She taps **Start** when a client sits down and **Done** when they leave. New bookings chime and slide in on their own.

The front desk is an **open-weight model (Qwen3-8B) that I fine-tuned with LoRA on Tinker** to speak in Sugar's voice, know her menu and prices, and end every booking with a structured order the app can trust.

## Demo

🔗 **Live site:** https://sugar-nails-nine.vercel.app (Sugar's queue: `/queue`, demo PIN `2580`)
💻 **Code:** https://github.com/comzzy/sugar-frontdesk

Payments run in **test mode**, so no real money moves. With a Paystack key, the same button opens Paystack's checkout.

| Customer: landing | Customer: booking chat | Customer: paid |
|---|---|---|
| ![Sugar Nails landing page on mobile](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-01-hero.png) | ![Booking summary in the chat](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-04-chat-order.png) | ![Ticket showing the customer's place in the queue](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-06-paid-ticket.png) |

![Desktop landing page](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/desktop-01-hero.png)

![Sugar's queue with a client in the chair and the next one waiting](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/desktop-09-queue-started.png)

This is a real chat from the fine-tuned model. The customer typed in Pidgin and packed four details into one message:

> **Front desk:** Thank you Blessing! What would you like done today?
> **Customer:** abeg I wan do gel x, long coffin, french tip
> **Front desk:** Okay o! Which colours are we using?
> **Customer:** nude and milky white
> **Front desk:** Before I forget, any allergies or special notes for Sugar?
> **Customer:** no allergies o
> **Front desk:** When should we expect you?
> **Customer:** by 4pm today
> **Front desk:** Perfect, Blessing! Here's your booking: Gel-X Extensions ₦20,000 · Classic French tips +₦3,000 · Long length +₦2,000 · Coffin · Nude, Milky white · Total **₦25,000**

It understood "gel x" as Gel-X Extensions, didn't re-ask for the length, shape or style it had already been given, and went straight to the next thing it didn't know.

## How I Built It

### 1. Sugar's menu

Everything starts from one file, `app/menu.py`: services with naira prices (gel polish ₦8,000, acrylic full set ₦18,000, Gel-X ₦20,000 and so on), style add-ons (French +₦3,000, chrome +₦3,500, 3D flowers +₦5,000…), length surcharges that only apply to extensions, shapes and 14 shades. The system prompt, the dataset, the evaluator and the website all read from it, so a price change happens in one place.

### 2. A dataset in Sugar's voice

I couldn't train on Sugar's real chats yet. That's part of the point, more on that below. So I wrote a **customer simulator**. For each conversation, it picks a true booking (who, what, which style, colours, length, shape, notes, time) and then plays a customer who:

- sometimes taps the quick-reply chips and sometimes types *"I go do acrylik and pedi abeg"*
- packs several details into one message (*"acrylic, long coffin, chrome"*)
- sends a phone number with missing digits
- asks *"how much be gel-x?"* in the middle of booking
- changes their mind after the summary (*"abeg change the colour to wine"*)

The front-desk side is written **from the ground truth**, in a warm Lagos voice ("No wahala!", "E go fine well well!", "Okay o!"), so every target order and total is correct by construction. Every booking ends like this:

```text
Perfect, Chioma! Here's your booking:
• Acrylic Full Set: ₦18,000
• Chrome / glazed: +₦3,500
• Long length: +₦2,000
...
Total: ₦23,500
<order>{"name": "Chioma", "phone": "08031234567", "services": ["acrylic_full"], "style": "chrome",
 "colours": ["Baby pink", "Silver"], "length": "long", "shape": "Almond", "notes": "None",
 "time": "Today, evening", "total": 23500}</order>
```

360 training conversations and 40 held-out ones, about 19 messages each.

### 3. LoRA fine-tuning on Tinker

[Tinker](https://tinker-docs.thinkingmachines.ai/) let me write the training loop on my own machine while it ran on their GPUs. I used **Qwen3-8B** with the `qwen3_disable_thinking` renderer from `tinker-cookbook`. That keeps replies quick, with no chain-of-thought, which matters for a chat on a phone.

One detail mattered: Qwen3's chat renderer doesn't have the "extension property" (it rewrites history), so training on every assistant message in one sequence would teach the model a context it never sees at inference. The cookbook warns you about this. So **every assistant turn becomes its own example**, with loss only on that turn:

```python
from tinker_cookbook import renderers
from tinker_cookbook.supervised.data import conversation_to_datum

renderer = renderers.get_renderer("qwen3_disable_thinking", tokenizer)
data = [conversation_to_datum(conv_prefix, renderer, max_length=2048,
                              train_on_what=renderers.TrainOnWhat.LAST_ASSISTANT_MESSAGE)
        for conv_prefix in per_turn_examples]   # 1,751 examples
```

The training loop is the plain Tinker one: `forward_backward` with cross-entropy, then `optim_step`, with the cookbook's recommended LoRA learning rate and a linear decay:

```python
service = tinker.ServiceClient()
tc = service.create_lora_training_client(base_model="Qwen/Qwen3-8B", rank=32)

for step, batch in enumerate(batches):                       # 2 epochs x 54 batches of 32
    fb = tc.forward_backward(batch, loss_fn="cross_entropy")
    op = tc.optim_step(types.AdamParams(learning_rate=lr * (1 - step / total_steps)))
    fb.result(); op.result()

ckpt = tc.save_weights_for_sampler(name="sugar-frontdesk-final").result()
# tinker://00631ae2-...:train:0/sampler_weights/sugar-frontdesk-final
```

Mean per-token loss went from **1.87 to 0.036** in 108 steps. The whole run took **under 5 minutes** and cost about **$1.65** (3.7M training tokens at $0.44 per million for Qwen3-8B).

### 4. Serving it

The website calls the checkpoint through **Tinker's OpenAI-compatible endpoint**. I render the prompt in exactly the Qwen3 format the LoRA was trained on and send it to `/completions`. It only needs `httpx`, so it runs fine in a small serverless function:

```python
r = await client.post(f"{OAI_BASE}/completions",
    headers={"Authorization": f"Bearer {TINKER_API_KEY}"},
    json={"model": "tinker://…/sampler_weights/sugar-frontdesk-final",
          "prompt": render_prompt(history),   # <|im_start|>… <think>\n\n</think>\n\n
          "max_tokens": 400, "temperature": 0.3, "stop": ["<|im_end|>"]})
```

Two safety nets:

- **The server never trusts the model's arithmetic.** The `<order>` JSON is checked against the menu and the total is recomputed before payment. The model's own total is logged so I can measure it.
- **It never gets stuck.** If Tinker is slow (over 12 seconds), errors, or returns a broken order, that turn is answered by a small rule-based engine that rebuilds the booking from the customer's messages. Customers see the same chat, just with less understanding of messy messages.

### 5. The site

FastAPI and SQLite on the back end. The front end is hand-written HTML, CSS and JS with no framework. I wanted it to feel like Sugar's salon, not a template: blush and cream with deep plum, glossy liquid polish swirls, a script display font, silver-bevel pill buttons and circular frames. All the artwork is CSS or inline SVG I drew myself: a 14-shade swatch wheel made of almond nails that slowly turns, a polish bottle with a drip that falls and refills, nail previews for each style. There are no photos and no generated images. It's animated end to end (letter-by-letter title, scroll reveals, chat bubbles, typing dots, chips popping in, a check mark and polish-drop confetti when you pay, and queue cards that slide to their new spots with FLIP animation), and all of it switches off for `prefers-reduced-motion`.

## Did fine-tuning actually help? Before vs after

I evaluated base Qwen3-8B (same system prompt, same menu, same format instructions) against the fine-tune. I also included the rule-based fallback as a reference point.

**Held-out conversations** (40 chats: the final booking turn plus one random turn mid-conversation):

| | base Qwen3-8B | **Sugar's fine-tune** | rule-based fallback |
|---|---|---|---|
| Valid `<order>` JSON | 72.5% | **100%** | 92.5% |
| Field accuracy (9 fields) | 63.6% | **99.4%** | 86.4% |
| Whole order exactly right | 22.5% | **95%** | 52.5% |
| Total price correct | 35% | **92.5%** | 82.5% |
| Asks for the right next detail | 60% | **95%** | 90% |
| Offers the right quick-reply chips | 17.5% | **97.5%** | 92.5% |
| Mean reply length | 90 chars | **50 chars** | 48 chars |

**Hand-written messy chats** (12 conversations I typed myself, full of Pidgin, typos, corrections and several details per message, played out live, with a simple oracle answering whatever the assistant asks next):

| | base | **fine-tune** | rule-based |
|---|---|---|---|
| Booking completed | 50% | **100%** | 100% |
| Field accuracy | 41.7% | **99.1%** | 94.4% |
| Whole order exactly right | 8.3% | **91.7%** | 50% |
| Total price correct | 33.3% | **100%** | 83.3% |

What the base model did wrong is telling. Given *"abeg I wan do acrylic, long coffin, chrome. wine colour"*, base Qwen3 replied *"Amarachi, got it! You're booking Acrylic Full. 🎨 What's your preferred time? [chips: Morning | Afternoon | Evening]"*. It skipped the allergy question, invented its own chips, then kept asking the customer to "confirm the time" in **bold markdown** and never produced an order the app could read. The fine-tune kept all four details, asked about allergies, then the time, and finished with a correct ₦23,500 order. The rules engine gets close on field accuracy but only gets the *whole* order right half the time, because real people don't type like regexes expect.

The fine-tune isn't perfect. On three held-out bookings it got the total wrong, twice because it picked the wrong add-on and once with a plain arithmetic slip. That's exactly why the server recomputes the price.

All numbers and full transcripts are in [`training/results/`](https://github.com/comzzy/sugar-frontdesk/tree/main/training/results).

## Why Open Innovation Matters Here

**Sugar owns her front desk.** The LoRA adapter is a file. Tinker lets me download the weights, and the base model is open, so she isn't renting a personality from a closed API that can change its behaviour or its prices next month. The cookbook can export it as a standard PEFT adapter or a merged Hugging Face model, so it can run on vLLM anywhere, with or without Tinker.

**Her customers' details stay hers.** The front desk handles names, phone numbers, allergies and payment. With an open model, the chats can stay on infrastructure she chooses. Nobody's data becomes training material for someone else's model.

**It's cheap enough for a one-woman business.** Training cost less than a gel refill. An 8B model with thinking turned off answers in a few seconds, and each message costs well under a naira. A small model that knows one job well beats a giant general model here.

**It can learn *her* way of talking.** This is the big one. A closed model would only let me write a long prompt and hope. With an open model, I can **fine-tune on Sugar's real chats** once she's used it for a few weeks: her actual phrases, the styles her customers really ask for, her new prices. It's the same script, a new dataset and a few dollars. Prompting got the base model to 22.5% exact orders. Training got it to 95%.

## What Sugar Said

> *[Placeholder: Sugar's reaction after trying it at her station. Add her words and maybe a photo of the QR code on her table here.]*

## What's Next

- Retrain on Sugar's real (anonymised) chats after the first few weeks
- Plug in her Paystack account so the "Pay" button takes real deposits
- Send a WhatsApp or SMS ping when a customer is next
- Let customers upload a picture of the design they want, with a vision model reading it into the order

Thanks for reading! If you know a busy person whose hands are always full, maybe they need a front desk too. 💅
