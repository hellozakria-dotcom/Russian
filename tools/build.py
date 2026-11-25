"""Build the app data from content/day*.json.

For every lesson in content/:
  * fills in missing pronunciation ("pr") for words and sentences,
  * turns picture names into files: a value like "Open book" is a Microsoft Fluent emoji name;
    its SVG is downloaded and rendered to pics/open_book.png (240 px),
  * makes an mp3 for every word and sentence (Piper Russian voice), named by a hash of the text,
  * writes days/dayN.json and days/index.json,
  * regenerates sw.js (offline cache list + new version, so installed apps update).

Usage:  python3 tools/build.py            (all days)
        python3 tools/build.py --no-audio (skip voice, e.g. when Piper is not installed)
"""
import glob, hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from translit import word_tr, tr  # noqa: E402

NO_AUDIO = "--no-audio" in sys.argv
os.chdir(ROOT)
for d in ("days", "audio", "pics"): os.makedirs(d, exist_ok=True)
plain = lambda t: re.sub(r"[{}|]", "", t)
FLUENT = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/"


def font(size):
    from PIL import ImageFont
    for f in ("/usr/share/fonts/truetype/google-fonts/ofl/firasans/FiraSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: continue
    return ImageFont.load_default()


TILE_COLORS = [(46, 98, 160), (196, 64, 112), (46, 140, 90), (120, 80, 170), (200, 120, 20), (178, 58, 46)]
def tile(text):
    """A picture for a number or short text: 'num:21' -> big 21 on a coloured tile, with dots for 1-10."""
    from PIL import Image, ImageDraw
    fn = "num_" + re.sub(r"[^0-9a-z]+", "_", text.lower()) + ".png"
    out = os.path.join("pics", fn)
    if os.path.exists(out): return fn
    S = 480; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    col = TILE_COLORS[sum(map(ord, text)) % len(TILE_COLORS)]
    d.rounded_rectangle((16, 16, S - 16, S - 16), 90, fill=col)
    n = int(text) if text.isdigit() else None
    f = font(240 if len(text) <= 2 else 170)
    w = d.textlength(text, font=f); bb = d.textbbox((0, 0), text, font=f)
    y = (S - (bb[3] - bb[1])) / 2 - bb[1] - (40 if n and 1 <= n <= 10 else 0)
    d.text(((S - w) / 2, y), text, font=f, fill=(255, 253, 248))
    if n and 1 <= n <= 10:  # dots to count
        r, gap = 16, 44; tot = (n - 1) * gap; x0 = (S - tot) / 2
        for i in range(n): d.ellipse((x0 + i * gap - r, 380 - r, x0 + i * gap + r, 380 + r), fill=(255, 253, 248))
    im.resize((240, 240)).save(out)
    print("  tile:", fn)
    return fn


def pic(name):
    """'Open book' -> 'open_book.png' (Fluent emoji, downloaded + rendered if needed);
    'num:21' -> generated number tile; 'x.png' -> unchanged."""
    if name.endswith(".png"):
        return name
    if name.startswith("num:"):
        return tile(name[4:])
    fn = name.replace(" ", "_").lower() + ".png"
    out = os.path.join("pics", fn)
    if os.path.exists(out):
        return fn
    import cairosvg
    slug = name.lower().replace(" ", "_")
    for sub in (f"{name}/Color/{slug}_color.svg", f"{name}/Default/Color/{slug}_color_default.svg"):
        try:
            svg = urllib.request.urlopen(FLUENT + urllib.parse.quote(sub), timeout=30).read()
            cairosvg.svg2png(bytestring=svg, write_to=out, output_width=240, output_height=240)
            print("  picture:", fn)
            return fn
        except Exception:
            continue
    raise SystemExit(f"Picture not found in Fluent emoji: {name!r} (check the folder name on github.com/microsoft/fluentui-emoji/tree/main/assets)")


_voice = None
def audio(text):
    fn = hashlib.md5(text.encode()).hexdigest()[:10] + ".mp3"
    out = os.path.join("audio", fn)
    if os.path.exists(out) or NO_AUDIO:
        return fn if os.path.exists(out) else None
    global _voice
    if _voice is None:
        import voice as _voice_mod
        _voice = _voice_mod
    import numpy as np
    a = np.concatenate([_voice.sil(0.15), _voice.say(text), _voice.sil(0.2)])
    a = np.clip(a / max(1e-6, float(abs(a).max())) * 0.9, -1, 1)
    with wave.open("/tmp/_ru.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(_voice.SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/_ru.wav", "-c:a", "libmp3lame", "-b:a", "48k", out], check=True)
    print("  audio:", text)
    return fn


index = []
for path in sorted(glob.glob("content/day*.json"), key=lambda p: int(re.findall(r"\d+", p)[-1])):
    d = json.load(open(path, encoding="utf-8"))
    n = d["id"]
    print(f"Day {n}: {d['title']}")
    for i, w in enumerate(d["words"], 1):
        w.setdefault("id", f"d{n}w{i}")
        if not w.get("pr"):
            w["pr"] = " / ".join(word_tr(x.strip()) for x in w["ru"].split("/"))
        if w.get("pic"): w["pic"] = pic(w["pic"])
        w["audio"] = audio(w.get("say") or (". ".join(x.strip() for x in w["ru"].split("/")) + "."))
    for i, s in enumerate(d["sentences"], 1):
        s.setdefault("id", f"d{n}s{i}")
        if s.get("mk"): s["ru"] = plain(s["mk"])
        if not s.get("pr"): s["pr"] = tr(s["ru"])
        s["pics"] = [pic(p) for p in s.get("pics", [])]
        s["audio"] = audio(s["ru"])
    if os.path.exists(f"videos/day{n}.mp4"): d["video"] = f"videos/day{n}.mp4"
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # keep filled-in values in the source
    json.dump(d, open(f"days/day{n}.json", "w", encoding="utf-8"), ensure_ascii=False)
    index.append(dict(id=n, file=f"days/day{n}.json", title=d["title"], topic=d.get("topic", "")))
json.dump(dict(days=index), open("days/index.json", "w", encoding="utf-8"), ensure_ascii=False)
if os.path.exists("content/plan.json"):
    json.dump(json.load(open("content/plan.json", encoding="utf-8")), open("days/plan.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- graded reading texts ----
os.makedirs("texts", exist_ok=True)
norm = lambda w: w.lower().replace("\u0301", "").replace("ё", "е")
WORD_RE = re.compile(r"[А-Яа-яЁё\u0301]+(?:-[А-Яа-яЁё\u0301]+)*")
tindex = []
for path in sorted(glob.glob("content/texts/t*.json"), key=lambda p: int(re.findall(r"\d+", p)[-1])):
    t = json.load(open(path, encoding="utf-8"))
    print(f"Text {t['id']}: {t['title']}")
    gloss = {norm(k): v for k, v in t["gloss"].items()}
    missing = set()
    for s in t["sentences"]:
        s["audio"] = audio(s["ru"])
        for tok in WORD_RE.findall(s["ru"]):
            if norm(tok) not in gloss: missing.add(tok)
    if missing: raise SystemExit(f"  words without a gloss in {path}: {sorted(missing)}")
    for g in gloss.values():
        g["pr"] = g.get("pr") or word_tr(g["w"])
        g["audio"] = audio(g["w"])
    t["gloss"] = gloss
    if t.get("pic"): t["pic"] = pic(t["pic"])
    json.dump(t, open(f"texts/t{t['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
    tindex.append(dict(id=t["id"], file=f"texts/t{t['id']}.json", title=t["title"], en=t.get("en", ""), level=t.get("level", ""),
                       after=t.get("after", 0), pic=t.get("pic"), words=len(gloss), sentences=len(t["sentences"])))
json.dump(dict(texts=tindex), open("texts/index.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- service worker: precache everything except videos ----
files = ["./", "index.html", "manifest.webmanifest"] + sorted(
    glob.glob("days/*.json") + glob.glob("texts/*.json") + glob.glob("audio/*.mp3") + glob.glob("pics/*.png") + glob.glob("icons/*.png"))
h = hashlib.md5()
for f in files[1:]:
    h.update(f.encode()); h.update(open(f, "rb").read())
version = h.hexdigest()[:10]
sw = open("tools/sw.template.js", encoding="utf-8").read()
sw = sw.replace("__VERSION__", version).replace("__FILES__", json.dumps(files, indent=0))
open("sw.js", "w", encoding="utf-8").write(sw)
words = sum(len(json.load(open(f"days/day{x['id']}.json"))["words"]) for x in index)
sents = sum(len(json.load(open(f"days/day{x['id']}.json"))["sentences"]) for x in index)
print(f"Done: {len(index)} days, {words} words, {sents} sentences, cache version {version}")
