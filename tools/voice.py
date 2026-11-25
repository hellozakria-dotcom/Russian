"""Russian speech with Piper (ru-irinia-medium). Stress marks (U+0301) in the text are enforced on the phonemes."""
import re, wave, json, numpy as np
from piper import PiperVoice

import os
V = PiperVoice.load(os.path.join(os.path.dirname(__file__), "voice", "ru-irinia-medium.onnx"))
SR = V.config.sample_rate
VOW_L = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
VOW_P = set("aɑoɵuyiɪeʌɐəɛæʉɨ")
ST = dict(а="a", о="o", е="e", ё="ɵ", и="i", у="u", ы="y", э="e", ю="u", я="a")
UN = dict(о="ʌ", а="ʌ", е="i", я="i")
log = []

def word_phon(w):
    """w: one word, maybe with combining acute. returns fixed phoneme list"""
    plain = w.replace("́", "")
    ph = [p for s in V.phonemize(plain) for p in s]
    letters = [c for c in plain if c in VOW_L]
    if len(letters) < 2: return ph
    if "́" in w:
        k = len([c for c in w[:w.index("́")] if c in VOW_L]) - 1
    elif "ё" in plain.lower():
        k = [c.lower() for c in letters].index("ё")
    else: return ph
    vidx = [i for i, p in enumerate(ph) if p in VOW_P]
    if len(vidx) != len(letters):
        log.append(("MISMATCH", w, "".join(ph))); return ph
    cur = [j for j, i in enumerate(vidx) if i > 0 and ph[i - 1] == "ˈ"]
    if cur == [k]: return ph
    log.append(("FIX", w, "".join(ph)))
    out = list(ph)
    for j in cur:  # reduce old stressed vowel
        l = letters[j].lower()
        if l in UN: out[vidx[j]] = UN[l]
    out[vidx[k]] = ST[letters[k].lower()]
    out = [p for p in out if p != "ˈ"]
    vidx = [i for i, p in enumerate(out) if p in VOW_P]
    out.insert(vidx[k], "ˈ")
    log[-1] += ("".join(out),)
    return out

def say(text):
    toks = re.findall(r"[\ẃ]+|[^\w\s]", text)
    ph = []
    for t in toks:
        if re.match(r"[\ẃ]+", t):
            if ph and ph[-1] not in (" ",): ph.append(" ")
            ph += word_phon(t)
        elif t in ".,!?—":
            ph += [" " if t == "—" else t]
    ids = V.phonemes_to_ids(ph)
    a = V.phoneme_ids_to_audio(ids)
    return np.asarray(a, dtype=np.float32).flatten()

def sil(s): return np.zeros(int(SR * s), dtype=np.float32)

