"""Turn the frames from record_desktop.py into a narrated, subtitled MP4.

Narration: Kokoro-82M (ONNX), voice af_heart, run locally. Each scene's video is cut to
fit its own narration (freezing the last frame if the voice runs longer), so the voice and
picture can't drift apart. Model wait times are compressed to ~0.6 s.
Usage: /workspace/tts/venv/bin/python tests/edit_desktop.py
"""
import json, subprocess, wave
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

SRC = Path("/tmp/sugar-desk"); W = SRC / "work"; W.mkdir(exist_ok=True)
OUT = Path(__file__).resolve().parent.parent / "screenshots" / "demo-desktop.mp4"
FPS, SR = 30, 24000
frames = json.loads((SRC / "frames.json").read_text())
T0 = frames[0][0]
M = {k: (v - T0) for k, v in json.loads((SRC / "marks.json").read_text()).items() if isinstance(v, float)}
BLUR_STATS = "[v]split[a][b];[b]crop=1080:52:100:130,boxblur=luma_radius=12:luma_power=4:chroma_radius=10:chroma_power=4[bb];[a][bb]overlay=100:130[v]"


def run(*a): subprocess.run(a, check=True)


# ---------- 1. constant-frame-rate master from the screencast frames
master = W / "master.mp4"
if not master.exists():
    lines = []
    for i, (ts, p) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else ts + 0.5
        lines += [f"file '{p}'", f"duration {max(nxt - ts, 0.001):.4f}"]
    lines.append(f"file '{frames[-1][1]}'")
    (W / "frames.txt").write_text("\n".join(lines))
    run("ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(W / "frames.txt"),
        "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-crf", "12", "-preset", "fast", str(master))


def wait(k):   # compress the model's thinking time for turn k
    return [(M[f"t{k}_sent"] + 0.35, M[f"t{k}_reply"] - 0.1, "wait")]


def turn(k):
    return [(M[f"t{k}_type"], M[f"t{k}_sent"] + 0.35, 1)] + wait(k) + [(M[f"t{k}_reply"] - 0.1, M[f"t{k}_end"], 1)]


# ---------- 2. scenes: (pieces, narration sentences as (spoken, subtitle), blur?)
S = [
    ([(0.3, M["menu"], 1)], [
        ("This is the booking site for Sugar Nails. Sugar does nails in G.R.A., Port Harcourt.",
         "This is the booking site for Sugar Nails. Sugar does nails in GRA, Port Harcourt."),
        ("When she's in the middle of a set, she can't stop to answer her phone. So customers book here.",
         "When she's in the middle of a set, she can't stop to answer her phone. So customers book here.")], False),
    ([(M["menu"], M["chat"], 1)], [
        ("Her menu and prices are in naira, and you can look through the styles and colours first.",
         "Her menu and prices are in naira, and you can look through the styles and colours first.")], False),
    ([(M["chat"], M["t0_type"], 1)] + turn(0) + turn(1), [
        ("The front desk asks for a name and a phone number.", "The front desk asks for a name and a phone number."),
        ("The wait for each reply is cut short in this video.", "The wait for each reply is cut short in this video.")], False),
    (turn(2), [
        ("You can type the way you talk. Ada writes in pidgin, and gives the service, length, shape and style in one message.",
         "You can type the way you talk. Ada writes in Pidgin, and gives the service, length, shape and style in one message.")], False),
    (turn(3) + turn(4) + turn(5), [
        ("So it only asks for what's still missing: colours, allergies, and a time.",
         "So it only asks for what's still missing: colours, allergies and a time.")], False),
    ([(M["summary"], M["sheet"], 1)], [
        ("Then it shows the whole order and the total. Here, twenty-five thousand naira.",
         "Then it shows the whole order and the total. Here, ₦25,000.")], False),
    ([(M["sheet"], M["ticket"], 1)], [
        ("She pays before she joins the queue, so Sugar never has to chase a transfer.",
         "She pays before she joins the queue, so Sugar never has to chase a transfer.")], False),
    ([(M["ticket"], M["ticket_end"], 1)], [
        ("Ada gets a ticket with her place in line.", "Ada gets a ticket with her place in line.")], False),
    ([(M["dash"], M["start"], 1)], [
        ("On Sugar's side, the queue page shows who's next, with every detail of the order.",
         "On Sugar's side, the queue page shows who's next, with every detail of the order.")], True),
    ([(M["start"], M["done"], 1)], [
        ("When Ada sits down, Sugar taps Start.", "When Ada sits down, Sugar taps Start.")], True),
    ([(M["done"], M["end"], 1)], [
        ("When she's done, Sugar taps Done.", "When she's done, Sugar taps Done.")], True),
    ([(2.0, M["menu"] - 0.2, 1)], [
        ("The replies come from an open model that was fine-tuned on Tinker to know Sugar's menu and talk like her front desk.",
         "The replies come from an open model that was fine-tuned on Tinker to know Sugar's menu and talk like her front desk.")], False),
]

# ---------- 3. narration audio (one clip per sentence)
k = Kokoro("/workspace/tts/kokoro-v1.0.onnx", "/workspace/tts/voices-v1.0.bin")
LEAD, GAP, TAIL = 0.35, 0.3, 0.5
audio, subs, scene_files, t_abs = [], [], [], 0.0
for si, (pieces, sents, blur) in enumerate(S):
    clips = []
    for spoken, _ in sents:
        a, sr = k.create(spoken, voice="af_heart", speed=0.98, lang="en-us"); assert sr == SR
        clips.append(a.astype(np.float32))
    narr = LEAD + sum(len(c) / SR for c in clips) + GAP * (len(clips) - 1) + TAIL
    # video pieces -> durations
    vid = sum(0.6 if sp == "wait" else (b - a) / sp for a, b, sp in pieces)
    if si and vid > narr + 2.5:   # long silent stretch: play this scene a little faster
        fixed = sum(0.6 for *_, sp in pieces if sp == "wait")
        k_ = (vid - fixed) / (narr + 2.5 - fixed)
        pieces = [(a, b, sp if sp == "wait" else sp * k_) for a, b, sp in pieces]
        vid = sum(0.6 if sp == "wait" else (b - a) / sp for a, b, sp in pieces)
    dur = round(max(vid, narr) * FPS) / FPS
    # build scene video
    parts, labels = [], []
    for i, (a, b, sp) in enumerate(pieces):
        f = (b - a) / 0.6 if sp == "wait" else sp
        parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{f:.4f}[p{i}]"); labels.append(f"[p{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(pieces)}:v=1:a=0,fps={FPS}[v]"
    if blur: fc += ";" + BLUR_STATS
    fc += f";[v]tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setpts=PTS-STARTPTS[out]"
    sf_ = W / f"scene{si:02d}.mp4"
    run("ffmpeg", "-loglevel", "error", "-y", "-i", str(master), "-filter_complex", fc, "-map", "[out]",
        "-r", str(FPS), "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", str(sf_))
    scene_files.append(sf_)
    # scene audio, exactly dur long
    buf = np.zeros(int(round(dur * SR)), dtype=np.float32); pos = LEAD
    for c, (_, sub) in zip(clips, sents):
        i0 = int(pos * SR); buf[i0:i0 + len(c)] = c[: len(buf) - i0]
        subs.append((t_abs + pos, t_abs + pos + len(c) / SR, sub)); pos += len(c) / SR + GAP
    audio.append(buf); t_abs += dur
    print(f"scene {si}: video {vid:.1f}s narration {narr:.1f}s -> {dur:.2f}s")

sf.write(W / "narration.wav", np.concatenate(audio), SR)
(W / "scenes.txt").write_text("\n".join(f"file '{p}'" for p in scene_files))
run("ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(W / "scenes.txt"), "-c", "copy", str(W / "video.mp4"))


# ---------- 4. subtitles (ASS: small font, semi-transparent box)
def ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60); return f"{int(h)}:{int(m):02d}:{s:05.2f}"
ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1280", "PlayResY: 800", "WrapStyle: 0", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
       "Style: Default,Inter,24,&H00FFFFFF,&H00FFFFFF,&H6A1E0A14,&H6A1E0A14,0,0,0,0,100,100,0,0,3,7,0,2,160,160,26,1",
       "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for a, b, text in subs:
    ass.append(f"Dialogue: 0,{ts(a)},{ts(b + 0.15)},Default,,0,0,0,,{text}")
(W / "subs.ass").write_text("\n".join(ass), encoding="utf-8")
run("ffmpeg", "-loglevel", "error", "-y", "-i", str(W / "video.mp4"), "-i", str(W / "narration.wav"),
    "-vf", f"ass={W / 'subs.ass'}", "-c:v", "libx264", "-crf", "21", "-preset", "slow", "-pix_fmt", "yuv420p",
    "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", str(OUT))
(W / "subs.json").write_text(json.dumps(subs))
print("total", round(t_abs, 2), "->", OUT, round(OUT.stat().st_size / 1e6, 2), "MB")
