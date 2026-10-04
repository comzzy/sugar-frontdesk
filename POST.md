---
title: I fine-tuned an open model to be the front desk at my friend's nail studio
published: true
tags: devchallenge, weekendchallenge, hf26challenge, ai
---

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)*

## What I Built

### Meet Sugar

Sugar is my friend. She does nails in GRA, Port Harcourt: gel, acrylic, Gel-X, BIAB, French tips, chrome, little hand-painted flowers. She's good at it, so she's busy.

I've watched the same thing happen at her station many times. She has a client's hand in one hand and a brush in the other. Her phone keeps lighting up: *"Hi dear, are you free today? How much is acrylic?"* Someone walks in and asks how long the wait is. She can't stop to reply, she can't write down who came first, and she can't ask the next person if they want coffin or almond, nude or wine, or whether they're allergic to anything.

So people wait, some leave, and the order of who's next lives in her head.

She doesn't need salon software. She needs a front desk: someone to greet people, write down exactly what they want, tell them the price, take payment and give her a clean list of who's next. So I built one.

### What it does

Two screens.

**The customer site.** Customers open it on their phone, from a link Sugar shares or a QR code she can print for her station. The front desk greets them and asks for their name and number, then the service, style, colours, length, shape, allergies and a time. They can tap the options or type the way they talk, in English or Pidgin. They see the full order and the total in naira, pay, and get a ticket that updates on its own: *"You're #2 · 1 person ahead of you."*

**Sugar's queue.** A PIN-protected page on her phone or tablet. It shows who's in the chair, who's next, and each person's order: services, style, colour swatches, length, shape, any allergy note (highlighted), the price and whether they've paid. She taps **Start** when someone sits down and **Done** when they leave. New bookings chime and slide in by themselves.

The front desk is Qwen3-8B, an open-weight model I fine-tuned with LoRA on Tinker. It talks like Sugar's front desk, knows her menu and prices, and ends every booking with a structured order the app can check.

### What Sugar Said

I sent Sugar the link on WhatsApp. Her first reply:

> Wow let me take a look at it

Then she opened the chat on her phone and started booking herself: "Hi can I book a section here?", then "I'm sugar". The fine-tuned model answered in Pidgin, "Welcome o! Wetin be your name?", and carried on to ask for her number. A couple of minutes later she sent me a screenshot with this:

> Wow this is so cool. Thank you so much fren for this amazing gift 😍

![Sugar trying the booking chat on her phone, with her reply](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/sugar-reaction.jpg)

## Demo

{% embed https://www.youtube.com/watch?v=ZyzuW1q0ZAE %}

*Narrated walkthrough on desktop (87 s): a booking, payment, the queue ticket, then Sugar tapping Start and Done. The waits for each reply are cut short. If the embed doesn't load, here's the MP4: https://github.com/comzzy/sugar-frontdesk/releases/download/demo-video-v1/demo-desktop.mp4*

![A full booking on a phone: chat, order summary, payment, queue ticket, then Sugar's queue](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/demo.gif)

*A real booking on the live site at phone width, answered by the fine-tuned model. The waits for each reply (about 5 seconds) are sped up in the GIF.*

- **Live site:** https://sugar-nails-nine.vercel.app (Sugar's queue is at `/queue`, demo PIN `2580`)
- **Code:** https://github.com/comzzy/sugar-frontdesk

Payments are simulated in the demo until Sugar's Paystack account is connected.

| Customer: landing | Customer: booking chat | Customer: paid |
|---|---|---|
| ![Sugar Nails landing page on mobile](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-01-hero.png) | ![Booking summary in the chat](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-04-chat-order.png) | ![Ticket showing the customer's place in the queue](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/mobile-06-paid-ticket.png) |

![Desktop landing page](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/desktop-01-hero.png)

![Sugar's queue with a client in the chair and the next one waiting](https://raw.githubusercontent.com/comzzy/sugar-frontdesk/main/screenshots/desktop-09-queue-started.png)

Here's a real chat from the live site, answered by the fine-tuned model. The customer typed in Pidgin and put four details in one message:

> **Customer:** Hello, I wan book
> **Front desk:** Welcome o! Wetin be your name?
> **Customer:** call me Blessing
> **Front desk:** Welcome Blessing! What number can we reach you on?
> **Customer:** 0813 555 2041
> **Front desk:** Perfect. Which service do you want? Pick as many as you like.
> **Customer:** abeg I wan do gel x, long coffin, french tip
> **Front desk:** Okay o! Which colours are we using?
> **Customer:** nude and milky white
> **Front desk:** Before I forget, any allergies or special notes for Sugar?
> **Customer:** no allergies o
> **Front desk:** Last one: what time works for you?
> **Customer:** by 4pm today
> **Front desk:** All set, Blessing. Please check: *(order card: Gel-X Extensions ₦20,000 · Classic French tips +₦3,000 · Long length +₦2,000 · Coffin · Nude, Milky white · Total **₦25,000**)* Tap Pay to lock your spot in Sugar's queue. 💅

It read "gel x" as Gel-X Extensions, didn't ask again for the length, shape or style, and moved on to the next thing it didn't know.

## Code

{% embed https://github.com/comzzy/sugar-frontdesk %}

## How I Built It

### 1. Sugar's menu

Everything starts from one file, `app/menu.py`. It has services with naira prices (gel polish ₦8,000, acrylic full set ₦18,000, Gel-X ₦20,000 and so on), style add-ons (French +₦3,000, chrome +₦3,500, 3D flowers +₦5,000…), length surcharges that only apply to extensions, shapes and 14 shades. The system prompt, the dataset, the evaluator and the website all read from it, so if a price changes I change it once.

### 2. A dataset in Sugar's voice

I don't have Sugar's real chats to train on yet (more on why that matters below), so I wrote a customer simulator. For each conversation, it picks a true booking (who, what, which style, colours, length, shape, notes, time) and then plays a customer who:

- sometimes taps the quick-reply chips and sometimes types *"I go do acrylik and pedi abeg"*
- packs several details into one message (*"acrylic, long coffin, chrome"*)
- sends a phone number with missing digits
- asks *"how much be gel-x?"* in the middle of booking
- changes their mind after the summary (*"abeg change the colour to wine"*)

The front-desk replies are written from the true booking, in a warm Port Harcourt voice ("No wahala!", "E go fine well well!", "Okay o!"), so every target order and total is correct. Every booking ends like this:

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

I made 360 training conversations and 40 held-out ones, about 19 messages each.

### 3. LoRA fine-tuning on Tinker

With [Tinker](https://tinker-docs.thinkingmachines.ai/) I write the training loop on my own machine and it runs on their GPUs. I used Qwen3-8B with the `qwen3_disable_thinking` renderer from `tinker-cookbook`. No chain-of-thought means quicker replies, which matters in a chat on a phone.

One detail mattered. Qwen3's chat renderer doesn't have the "extension property" (it rewrites history), so training on every reply in one sequence would teach the model a context it never sees when it's actually running. The cookbook warns about this. So each front-desk reply became its own example, with loss only on that reply:

```python
from tinker_cookbook import renderers
from tinker_cookbook.supervised.data import conversation_to_datum

renderer = renderers.get_renderer("qwen3_disable_thinking", tokenizer)
data = [conversation_to_datum(conv_prefix, renderer, max_length=2048,
                              train_on_what=renderers.TrainOnWhat.LAST_ASSISTANT_MESSAGE)
        for conv_prefix in per_turn_examples]   # 1,751 examples
```

The training loop is the standard Tinker one: `forward_backward` with cross-entropy, then `optim_step`, using the cookbook's recommended LoRA learning rate with a linear decay:

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

Mean per-token loss went from 1.87 to 0.036 in 108 steps. The run took under 5 minutes and cost about $1.65 (3.7M training tokens at $0.44 per million for Qwen3-8B).

### 4. Serving it

The site calls the checkpoint through Tinker's OpenAI-compatible endpoint. I build the prompt in exactly the Qwen3 format the LoRA was trained on and send it to `/completions`. It only needs `httpx`, so it runs in a small serverless function:

```python
r = await client.post(f"{OAI_BASE}/completions",
    headers={"Authorization": f"Bearer {TINKER_API_KEY}"},
    json={"model": "tinker://…/sampler_weights/sugar-frontdesk-final",
          "prompt": render_prompt(history),   # <|im_start|>… <think>\n\n</think>\n\n
          "max_tokens": 400, "temperature": 0.3, "stop": ["<|im_end|>"]})
```

There are two safety nets:

- **The server doesn't trust the model's maths.** The `<order>` JSON is checked against the menu and the total is recalculated before payment. The model's own total is logged so I can measure it.
- **The chat doesn't get stuck.** If Tinker takes over 12 seconds, errors, or returns a broken order, a small rule-based engine answers that turn instead. It rebuilds the booking from what the customer has said. The chat looks the same; it's just worse at messy messages.

### 5. The site

FastAPI on the back end, with SQLite when it runs locally and Vercel Blob storage for the live queue. The front end is hand-written HTML, CSS and JS with no framework. I wanted it to feel like Sugar's salon, not a template: blush and cream with deep plum, glossy liquid polish swirls, a script display font, silver-bevel pill buttons and circular frames. All the artwork is CSS or inline SVG I drew myself: a 14-shade swatch wheel made of almond nails that slowly turns, a polish bottle with a drip that falls and refills, nail previews for each style. There are no photos and no generated images. Things move throughout: the title comes in letter by letter, sections reveal on scroll, chat bubbles and typing dots animate, chips pop in, there's a check mark and polish-drop confetti when you pay, and queue cards slide to their new spots. All of it switches off for `prefers-reduced-motion`.

### Did fine-tuning actually help? Before vs after

I compared base Qwen3-8B (same system prompt, menu and format instructions) with the fine-tune, and included the rule-based fallback for reference.

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

**Hand-written messy chats** (12 conversations I typed myself, full of Pidgin, typos, corrections and several details per message, played out live, with a simple script answering whatever the model asks next):

| | base | **fine-tune** | rule-based |
|---|---|---|---|
| Booking completed | 50% | **100%** | 100% |
| Field accuracy | 41.7% | **99.1%** | 94.4% |
| Whole order exactly right | 8.3% | **91.7%** | 50% |
| Total price correct | 33.3% | **100%** | 83.3% |

The base model's mistakes are telling. Given *"abeg I wan do acrylic, long coffin, chrome. wine colour"*, base Qwen3 replied *"Amarachi, got it! You're booking Acrylic Full. 🎨 What's your preferred time? [chips: Morning | Afternoon | Evening]"*. It skipped the allergy question, invented its own chips, then kept asking the customer to "confirm the time" in **bold markdown** and never produced an order the app could read. The fine-tune kept all four details, asked about allergies, then the time, and finished with a correct ₦23,500 order. The rules engine gets close on field accuracy but only gets the whole order right half the time, because people don't type the way regexes expect.

The fine-tune isn't perfect. On three held-out bookings it got the total wrong: once it picked the wrong add-on, once the wrong length, and once it made a plain arithmetic slip (₦28,500 instead of ₦18,500). That's why the server recalculates the price.

All numbers and full transcripts are in [`training/results/`](https://github.com/comzzy/sugar-frontdesk/tree/main/training/results).

### What's next

- Retrain on Sugar's real (anonymised) chats after the first few weeks
- Plug in her Paystack account so the "Pay" button takes real deposits
- Send a WhatsApp or SMS ping when a customer is next
- Let customers upload a picture of the design they want, with a vision model reading it into the order

## Why Does Open Innovation Matter?

**Sugar owns her front desk.** The LoRA adapter is a file. Tinker lets me download the weights and the base model is open, so she isn't renting from a closed API that could change its behaviour or prices next month. The cookbook can export it as a standard PEFT adapter or a merged Hugging Face model, so it can run on vLLM anywhere, with or without Tinker.

**Her customers' details stay hers.** The front desk handles names, phone numbers, allergies and payment. With an open model, the chats can stay on infrastructure she picks, and nobody's data ends up training someone else's model.

**It's cheap enough for a one-woman business.** Training cost about $1.65, roughly ₦2,200, which is less than one gel polish appointment on her menu. On the live site, each reply takes about 5 to 6 seconds.

I measured the running cost by replaying 5 held-out bookings (45 replies) through the deployed checkpoint and reading the token counts Tinker returned: about 1,000 prompt tokens and 62 output tokens per reply. At Tinker's published Qwen3-8B prices ($0.195 per million prompt tokens, $0.60 per million output tokens, from [the Tinker models page](https://tinker-docs.thinkingmachines.ai/tinker/models/)), that's **$0.00023 per reply, about ₦0.31**, and **$0.0021 per full booking, about ₦2.80**, at the CBN rate of ₦1,329.60 to the dollar (2 October 2026). That assumes no prompt caching, which would only make it cheaper. The raw counts are in `training/results/inference_cost.json`.

**It can learn her way of talking.** This matters most to me. With a closed model I could only write a long prompt and hope. With an open one, I can fine-tune on Sugar's real chats once she's used it for a few weeks: her actual phrases, the styles her customers really ask for, her new prices. Same script, new dataset, a few dollars. Prompting got the base model to 22.5% exact orders. Training got it to 95%.

## Prize Categories

**Best Use of Tinker.** Tinker is the core of this project, not an add-on. I used the Tinker SDK and `tinker-cookbook` to LoRA fine-tune Qwen3-8B on 1,751 per-turn examples in under 5 minutes for about $1.65. I sampled base and fine-tuned models through Tinker's `SamplingClient` for the before/after evaluation, and the live site serves the fine-tuned checkpoint through Tinker's OpenAI-compatible endpoint, at about ₦0.31 per reply. The fine-tune took exact orders from 22.5% to 95% on held-out chats and completed every one of my hand-written messy Pidgin chats.

Thanks for reading. If you know someone whose hands are always full, they might need a front desk too.
