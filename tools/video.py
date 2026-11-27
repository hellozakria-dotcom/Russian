"""Make the voiced lesson video for a day: videos/dayN.mp4 (1080x1920, for phones).

Usage: python3 tools/video.py 3          (needs tools/setup.sh + ffmpeg; run tools/build.py first)
Scenes: title → for each word: word card, then its sentences (read twice) → grammar sentences →
notes → tables → "well done" with the running total.
"""
import glob, json, os, re, subprocess, sys, urllib.parse, urllib.request, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
from translit import word_tr, tr  # noqa: E402

N = int(sys.argv[1])
DAY = json.load(open(f"content/day{N}.json", encoding="utf-8"))
W, H = 1080, 1920
INK = (33, 30, 28); SOFT = (130, 122, 112); ACC = (178, 58, 46); PRON = (46, 98, 160)
CREAM = (246, 241, 231); PLATE = (255, 253, 248)
GCOL = {"m": (46, 98, 160), "f": (196, 64, 112), "n": (46, 140, 90), "pl": (120, 80, 170), "adj": (200, 120, 20),
        "verb": (85, 85, 85), "num": (46, 98, 160), "x": (60, 56, 52)}
GNAME = {"m": "masculine", "f": "feminine", "n": "neuter", "pl": "plural", "adj": "adjective", "verb": "verb", "num": "number", "x": "phrase"}
BGS = [(250, 236, 222), (236, 242, 230), (247, 234, 236), (230, 238, 246), (250, 243, 214), (238, 233, 247)]
WORK = f"tools/.cache/video{N}"; HIRES = "tools/.cache/hires"
os.makedirs(WORK, exist_ok=True); os.makedirs(HIRES, exist_ok=True)

_FONTS = {}
def F(weight, size):
    k = (weight, size)
    if k not in _FONTS:
        for f in (f"/usr/share/fonts/truetype/google-fonts/ofl/firasans/FiraSans-{weight}.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight in ("Bold", "SemiBold") else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "DejaVuSans.ttf", "arial.ttf"):
            try: _FONTS[k] = ImageFont.truetype(f, size); break
            except OSError: continue
    return _FONTS[k]

def hires(fn, size):
    """Sharp version of a picture: Fluent emoji re-rendered from SVG, number tiles redrawn; falls back to pics/."""
    out = f"{HIRES}/{size}_{fn}"
    if not os.path.exists(out):
        stem = fn[:-4]
        try:
            name = stem.replace("_", " "); name = name[0].upper() + name[1:]
            import cairosvg
            ok = False
            for sub in (f"{name}/Color/{stem}_color.svg", f"{name}/Default/Color/{stem}_color_default.svg"):
                try:
                    svg = urllib.request.urlopen("https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/" + urllib.parse.quote(sub), timeout=30).read()
                    cairosvg.svg2png(bytestring=svg, write_to=out, output_width=size, output_height=size); ok = True; break
                except Exception: continue
            if not ok: raise RuntimeError
        except Exception:
            Image.open(f"pics/{fn}").convert("RGBA").resize((size, size), Image.LANCZOS).save(out)
    return Image.open(out).convert("RGBA")

def picture(fn, size):
    if fn.startswith("num_") and re.fullmatch(r"num_[0-9a-z_]+\.png", fn) and not re.fullmatch(r"num_[0-9a-f]{8}\.png", fn):
        out = f"{HIRES}/{size}_{fn}"
        if not os.path.exists(out):
            text = fn[4:-4]
            S = size; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            cols = [(46, 98, 160), (196, 64, 112), (46, 140, 90), (120, 80, 170), (200, 120, 20), (178, 58, 46)]
            d.rounded_rectangle((S * .03, S * .03, S * .97, S * .97), int(S * .19), fill=cols[sum(map(ord, text)) % len(cols)])
            n = int(text) if text.isdigit() else None
            f = F("Bold", int(S * (.5 if len(text) <= 2 else .36)))
            w = d.textlength(text, font=f); bb = d.textbbox((0, 0), text, font=f)
            y = (S - (bb[3] - bb[1])) / 2 - bb[1] - (S * .083 if n and 1 <= n <= 10 else 0)
            d.text(((S - w) / 2, y), text, font=f, fill=PLATE)
            if n and 1 <= n <= 10:
                r, gap = S * .033, S * .092; x0 = (S - (n - 1) * gap) / 2
                for i in range(n): d.ellipse((x0 + i * gap - r, S * .79 - r, x0 + i * gap + r, S * .79 + r), fill=PLATE)
            im.save(out)
        return Image.open(out).convert("RGBA")
    return hires(fn, size)

def tw(d, t, f): return d.textlength(t, font=f)
plain = lambda t: re.sub(r"[{}|]", "", t)

def segs(token, gcol):
    m = re.fullmatch(r"(.*?)\{([^}]*)\}(.*)", token)
    if not m: base = [(token, INK, False)]
    else:
        pre, inner, post = m.groups()
        if "|" in inner: a, b = inner.split("|"); base = [(pre, INK, False), (a, INK, True), (b, gcol, True), (post, INK, False)]
        else: base = [(pre, INK, False), (inner, gcol, True), (post, INK, False)]
    out = []
    for t, c, u in base:
        i = 0
        for mm in re.finditer(r".́|ё", t):
            if mm.start() > i: out.append((t[i:mm.start()], c, u))
            out.append((mm.group(), ACC, u)); i = mm.end()
        if i < len(t): out.append((t[i:], c, u))
    return [s for s in out if s[0]]

def ru_text(d, y, text, font, gcol=INK, lh=None, maxw=W - 140):
    lh = lh or int(font.size * 1.25)
    lines, cur = [], []
    for t in text.split(" "):
        trial = " ".join(plain(x) for x in cur + [t])
        if cur and tw(d, trial, font) > maxw: lines.append(cur); cur = [t]
        else: cur.append(t)
    lines.append(cur)
    for ln in lines:
        x = (W - tw(d, " ".join(plain(t) for t in ln), font)) / 2
        for k, t in enumerate(ln):
            if k: x += tw(d, " ", font)
            for s, c, u in segs(t, gcol):
                d.text((x, y), s, font=font, fill=c); w = tw(d, s, font)
                if u: d.line((x, y + font.size * 1.12, x + w, y + font.size * 1.12), fill=gcol, width=5)
                x += w
        y += lh
    return y

def text(d, y, t, f, c, lh=None, maxw=W - 160, x0=None):
    lh = lh or int(f.size * 1.3); words, cur = t.split(), ""
    def put(line, y):
        x = x0 if x0 is not None else (W - tw(d, line, f)) / 2
        d.text((x, y), line, font=f, fill=c)
    for w_ in words:
        tt = (cur + " " + w_).strip()
        if cur and tw(d, tt, f) > maxw: put(cur, y); y += lh; cur = w_
        else: cur = tt
    put(cur, y); return y + lh

def chip(d, cx, y, label, col):
    label = label.replace("\u0301", "")
    f = F("SemiBold", 38); w = tw(d, label, f)
    d.rounded_rectangle((cx - w / 2 - 26, y, cx + w / 2 + 26, y + 66), 33, fill=col)
    d.text((cx - w / 2, y + 10), label, font=f, fill=(255, 255, 255))

def header(d, left, right):
    left, right = left.replace("\u0301", ""), right.replace("\u0301", "")
    d.text((70, 80), left, font=F("SemiBold", 40), fill=SOFT)
    d.text((W - 70 - tw(d, right, F("Regular", 38)), 82), right, font=F("Regular", 38), fill=SOFT)

def plate(im, pics, cy, sizes={1: 520, 2: 430, 3: 340}):
    n = len(pics); size = sizes.get(n, 300); gap = -40 if n > 1 else 0
    x = (W - (n * size + (n - 1) * gap)) // 2
    ImageDraw.Draw(im).rounded_rectangle((60, cy - size // 2 - 60, W - 60, cy + size // 2 + 60), 60, fill=PLATE)
    for i, p in enumerate(pics):
        img = picture(p, size); im.paste(img, (x + i * (size + gap), cy - size // 2), img)

def new(bg=CREAM):
    im = Image.new("RGB", (W, H), bg); return im, ImageDraw.Draw(im)

scenes = []
def add(im, lines, mind):
    name = f"{len(scenes):03d}"; im.save(f"{WORK}/{name}.png"); scenes.append((name, lines, mind))

# running total up to this day
tot_w = tot_s = 0
for p in glob.glob("content/day*.json"):
    dd = json.load(open(p, encoding="utf-8"))
    if dd["id"] <= N: tot_w += len(dd["words"]); tot_s += len(dd["sentences"])
words, sents = DAY["words"], DAY["sentences"]
total = len(sents); bg = BGS[N % len(BGS)]

im, d = new()
p0 = words[0].get("pic")
if p0: img = picture(p0, 380); im.paste(img, ((W - 380) // 2, 400), img)
ru_text(d, 860, f"День {N}", F("Bold", 160))
text(d, 1080, DAY.get("topic", ""), F("SemiBold", 60), INK, maxw=W - 200)
text(d, 1300, f"{len(words)} words · {total} sentences", F("Regular", 44), SOFT)
add(im, [f"День {N}."], 4)

k = 0
by_word = {}
for s in sents: by_word.setdefault(s.get("word"), []).append(s)
for i, w in enumerate(words, 1):
    g = w.get("g", "x"); col = GCOL.get(g, SOFT)
    im, d = new(bg); header(d, f"word {i} / {len(words)}", f"Day {N}")
    if w.get("pic"): img = picture(w["pic"], 440); im.paste(img, ((W - 440) // 2, 250), img)
    f = F("Bold", 150 if len(w["ru"]) < 9 else 112 if len(w["ru"]) < 16 else 84)
    y = ru_text(d, 760, "{" + w["ru"] + "}" if " " not in w["ru"] else w["ru"], f, col)
    y = text(d, y + 20, w.get("pr", ""), F("SemiBold", 60), PRON) + 10
    y = text(d, y, w["en"], F("Medium", 60), INK) + 20
    chip(d, W / 2, y, GNAME.get(g, g), col)
    if w.get("note"): text(d, y + 120, w["note"], F("Regular", 40), SOFT, maxw=W - 200)
    say = w.get("say") or ". ".join(x.strip() for x in w["ru"].split("/")) + "."
    add(im, [say, say], 4.5)
    for s in by_word.get(w.get("id"), []):
        k += 1
        im, d = new(bg); header(d, f"word {i} / {len(words)}", f"sentence {k} / {total}")
        plate(im, s["pics"], 640)
        y = ru_text(d, 1100, s.get("mk") or s["ru"], F("SemiBold", 84), GCOL.get(s.get("g"), INK)) + 20
        y = text(d, y, s.get("pr", tr(s["ru"])), F("Medium", 52), PRON) + 20
        text(d, y, s["en"], F("Regular", 48), SOFT)
        add(im, [s["ru"], s["ru"]], 5)
for s in by_word.get(None, []):
    k += 1; g = s.get("g", "x")
    im, d = new(bg); header(d, s.get("case", "grammar"), f"sentence {k} / {total}")
    plate(im, s["pics"], 560, {1: 460, 2: 400, 3: 320})
    if s.get("case"): chip(d, W / 2, 900, s["case"], GCOL.get(g, SOFT))
    y = ru_text(d, 1010, s.get("mk") or s["ru"], F("SemiBold", 82), GCOL.get(g, INK)) + 20
    y = text(d, y, s.get("pr", tr(s["ru"])), F("Medium", 50), PRON) + 20
    text(d, y, s["en"], F("Regular", 46), SOFT)
    add(im, [s["ru"], s["ru"]], 5.5)

for note in DAY.get("notes", []):
    im, d = new(); d.text((80, 140), note["h"], font=F("Bold", 64), fill=INK)
    y = 290
    for line in note["lines"]:
        d.ellipse((84, y + 26, 102, y + 44), fill=ACC)
        y0 = y
        # wrap with stress colouring: draw plain then overlay stressed letters via ru_text-like run
        f = F("Regular", 52); words_ = line.split(); cur = ""; ly = y
        lines_ = []
        for w_ in words_:
            tt = (cur + " " + w_).strip()
            if cur and tw(d, tt.replace("́", ""), f) > W - 220: lines_.append(cur); cur = w_
            else: cur = tt
        lines_.append(cur)
        for ln in lines_:
            x = 130
            for seg, c, _ in segs(ln, INK):
                d.text((x, ly), seg, font=f, fill=c); x += tw(d, seg, f)
            ly += 70
        y = ly + 34
    secs = min(16, 5 + sum(len(l) for l in note["lines"]) / 28)
    add(im, [], round(secs, 1))

for t in DAY.get("tables", []):
    im, d = new(); text(d, 120, t["title"].replace("́", ""), F("Bold", 70), INK)
    cols = t["cols"]; nc = len(cols); colw = (W - 140) / nc
    f = F("Medium", 50 if nc <= 2 else 44 if nc == 3 else 40); y = 280
    for j, c in enumerate(cols):
        d.text((70 + j * colw, y), c.replace("́", ""), font=F("SemiBold", f.size), fill=SOFT)
    y += 80
    rowh = min(230, int((H - 420 - y) / max(1, len(t["rows"]))))
    for r in t["rows"]:
        d.rounded_rectangle((50, y - 12, W - 50, y + rowh - 22), 26, fill=PLATE)
        for j, v in enumerate(r):
            x = 70 + j * colw
            for seg, c, _ in segs(v, INK if j else SOFT):
                d.text((x, y), seg, font=f, fill=c); x += tw(d, seg, f)
            if j and rowh >= 100:
                d.text((70 + j * colw, y + f.size + 8), tr(v), font=F("Regular", int(f.size * .7)), fill=PRON)
        y += rowh
    add(im, [r[1] for r in t["rows"] if len(r) > 1][:12], 8)

im, d = new(); img = picture("party_popper.png", 380); im.paste(img, ((W - 380) // 2, 420), img)
ru_text(d, 880, "Молоде́ц!", F("Bold", 150))
text(d, 1060, "ma-la-DYETS · Well done!", F("SemiBold", 52), PRON)
text(d, 1200, "Learned so far", F("Regular", 44), SOFT)
text(d, 1270, f"{tot_w} words · {tot_s} sentences", F("Bold", 64), INK)
add(im, ["Молоде́ц!"], 4)

if "--frames" in sys.argv: sys.exit()
import voice  # noqa: E402
lst = open(f"{WORK}/list.txt", "w"); alst = open(f"{WORK}/alist.txt", "w")
for name, lines, mind in scenes:
    parts = [voice.sil(0.6)]
    for j, line in enumerate(lines):
        parts += [voice.say(line), voice.sil(1.1 if j < len(lines) - 1 else 0.4)]
    a = np.concatenate(parts); dur = max(mind, round(len(a) / voice.SR + 0.8, 2))
    a = np.concatenate([a, voice.sil(dur - len(a) / voice.SR)]); a = np.clip(a / max(1e-6, float(np.abs(a).max())) * 0.9, -1, 1)
    with wave.open(f"{WORK}/{name}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(voice.SR); w.writeframes((a * 32767).astype(np.int16).tobytes())
    tmp, dst = f"{WORK}/{name}.tmp.mp4", f"{WORK}/{name}.mp4"
    vf = f"format=yuv420p,loop=-1:1,trim=duration={dur},fade=t=in:st=0:d=0.3,fade=t=out:st={dur - 0.3}:d=0.3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", f"{WORK}/{name}.png", "-vf", vf, "-r", "30",
                    "-c:v", "libx264", "-crf", "21", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], check=True)
    os.replace(tmp, dst); lst.write(f"file '{name}.mp4'\n"); alst.write(f"file '{name}.wav'\n")
lst.close(); alst.close()
run = lambda *a: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)
run("-f", "concat", "-safe", "0", "-i", f"{WORK}/list.txt", "-c", "copy", f"{WORK}/silent.mp4")
run("-f", "concat", "-safe", "0", "-i", f"{WORK}/alist.txt", "-c", "pcm_s16le", f"{WORK}/voice.wav")
os.makedirs("videos", exist_ok=True)
run("-i", f"{WORK}/silent.mp4", "-i", f"{WORK}/voice.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
    "-shortest", "-movflags", "+faststart", f"videos/day{N}.mp4")
print(f"videos/day{N}.mp4 ready. Run tools/build.py again so the lesson links it.")
