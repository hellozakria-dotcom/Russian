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
    for sp in (t.get("speakers") or {}).values():
        if sp.get("pic"): sp["pic"] = pic(sp["pic"])
    json.dump(t, open(f"texts/t{t['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
    tindex.append(dict(id=t["id"], kind=t.get("kind", "story"), file=f"texts/t{t['id']}.json", title=t["title"], en=t.get("en", ""), level=t.get("level", ""),
                       after=t.get("after", 0), pic=t.get("pic"), words=len(gloss), sentences=len(t["sentences"])))
json.dump(dict(texts=tindex), open("texts/index.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- lexicon: one entry per dictionary word (lemma), with usage examples from all lessons and texts ----
WR = re.compile(r"[А-Яа-яЁё́]+(?:-[А-Яа-яЁё́]+)*")
toks = lambda s: [norm(x) for x in WR.findall(plain(s))]
lex = {}            # key -> entry
form2lemma = {}     # norm form -> lemma key
override = json.load(open("content/lexicon.json", encoding="utf-8")) if os.path.exists("content/lexicon.json") else {}
def lemma_entry(lem, en=None, src=None, card=None, pos=None):
    k = norm(lem)
    e = lex.setdefault(k, {"l": lem, "en": None, "src": src, "cards": [], "pos": pos})
    if en and not e["en"]: e["en"] = en
    if card and card not in e["cards"]: e["cards"].append(card)
    if pos and not e.get("pos"): e["pos"] = pos
    form2lemma.setdefault(k, k)
    return k
def lesson_lemmas(w):
    if w.get("lemmas"): return w["lemmas"]
    return [x.strip().strip("…?!.").strip() for x in w["ru"].split("/") if x.strip()]
days_all = [json.load(open(f"days/day{x['id']}.json", encoding="utf-8")) for x in index]
for d in days_all:
    for w in d["words"]:
        ls = lesson_lemmas(w)
        keys = [lemma_entry(l, w["en"], d["title"], w["id"], w.get("g")) for l in ls]
        w["lemmas"] = ls
        tb = w.get("table")
        if tb:
            for r in tb["rows"]:
                for j, cell in enumerate(r[1:], 1):
                    k = keys[min(j - 1, len(keys) - 1)] if len(keys) > 1 else keys[0]
                    for part in re.split(r" · |/", cell):
                        part = re.sub(r"[()*]|\bо\b|\bоб\b", " ", part).strip()
                        ws = WR.findall(part)
                        for x in ws:
                            if len(ws) == 1 or norm(x)[:3] == k[:3]: form2lemma.setdefault(norm(x), k)
    json.dump(d, open(f"days/day{d['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
texts_all = [json.load(open(f"texts/t{x['id']}.json", encoding="utf-8")) for x in tindex]
for t in texts_all:
    for f, g in t["gloss"].items():
        k = lemma_entry(g["lemma"], g["en"] if norm(g["w"]) == norm(g["lemma"]) else None, t["title"])
        form2lemma[f] = k
        g["k"] = k
    json.dump(t, open(f"texts/t{t['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
for k, o in override.items():
    kk = lemma_entry(o.get("l", k), None)
    if o.get("en"): lex[kk]["en"] = o["en"]
# corpus of example sentences
corpus = []
for d in days_all:
    for s in d["sentences"]: corpus.append({"ru": s["ru"], "en": s["en"], "src": d["title"]})
for t in texts_all:
    for s in t["sentences"]: corpus.append({"ru": s["ru"], "en": s["en"], "src": t["title"].replace("́", "")})
for k, o in override.items():
    for ex in o.get("ex", []): corpus.append({"ru": ex["ru"], "en": ex["en"], "src": "examples", "lemma": norm(o.get("l", k))})
    for f in o.get("forms", []): form2lemma.setdefault(norm(f), norm(o.get("l", k)))
seen = set(); dedup = []
for c in corpus:
    if norm(c["ru"]) in seen:
        if c.get("lemma"):
            for x in dedup:
                if norm(x["ru"]) == norm(c["ru"]): x["lemma"] = c["lemma"]
        continue
    seen.add(norm(c["ru"])); dedup.append(c)
corpus = dedup
phrases = [k for k in lex if " " in k]
for i, c in enumerate(corpus):
    found = set(form2lemma[t] for t in toks(c["ru"]) if t in form2lemma)
    flat = " ".join(toks(c["ru"]))
    found |= {k for k in phrases if (" " + k + " ") in (" " + flat + " ")}
    if c.get("lemma") in lex: found.add(c.pop("lemma"))
    c.pop("lemma", None)
    for k in found: lex[k].setdefault("ex", []).append(i)
    c["audio"] = audio(c["ru"])
weak = [e["l"] for k, e in lex.items() if len(e.get("ex", [])) < 2 and not re.fullmatch(r"[А-ЯЁ].*", e["l"].replace("́", "")[:1] or "x")]
no_en = [e["l"] for e in lex.values() if not e["en"]]
for e in lex.values():
    e["ex"] = e.get("ex", [])[:8]
    if not e["en"]: e["en"] = ""
json.dump({"lemmas": lex, "forms": form2lemma, "corpus": corpus}, open("days/lexicon.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"Lexicon: {len(lex)} dictionary words, {len(corpus)} example sentences")
if no_en: print("  needs an English meaning in content/lexicon.json:", ", ".join(sorted(no_en)))
if weak: print("  fewer than 2 usage examples (add some in content/lexicon.json):", ", ".join(sorted(weak)))

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
