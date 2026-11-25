"""Russian -> English-letter pronunciation. Stressed syllable in CAPS.
Mark stress in the input with a combining acute (U+0301) after the vowel, e.g. "чита́ть".
"""
# ---------- pronunciation in English letters, stressed syllable in CAPS ----------
VOW = "аеёиоуыэюя"
SPECIAL = {"что": "shto", "сего́дня": "si-VOD-nya", "пожа́луйста": "pa-ZHA-lus-ta",
           "вчера́": "fchi-RA", "в": "v", "с": "s", "мне": "mnye", "нет": "nyet", "где": "gdye",
           "друг": "druk", "кого́": "ka-VO", "чего́": "chi-VO", "краси́вый": "kra-SI-vih", "о": "a", "не": "ni", "по": "pa", "у": "u", "волейбо́л": "va-lei-BOL", "э́то": "E-ta", "пью": "pyu", "без": "byez"}
CON = dict(б="b", в="v", г="g", д="d", ж="zh", з="z", й="y", к="k", л="l", м="m", н="n", п="p", р="r",
           с="s", т="t", ф="f", х="kh", ц="ts", ч="ch", ш="sh", щ="shch", ъ="", ь="'")
DEVOICE = dict(б="п", в="ф", г="к", д="т", ж="ш", з="с")
HARD = set("шжц")

def word_tr(w):
    raw = w.lower()
    if raw in SPECIAL: return SPECIAL[raw]
    if "-" in raw: return "-".join(word_tr(p) for p in raw.split("-"))
    stress = None
    if "́" in raw: stress = raw.index("́") - 1
    s = raw.replace("́", "")
    if stress is None and "ё" in s: stress = s.index("ё")
    vpos = [i for i, c in enumerate(s) if c in VOW]
    if stress is None and len(vpos) == 1: stress = vpos[0]
    if s.startswith("сд"): s = "зд" + s[2:]
    if len(s) > 4 and s[-3:] in ("ого", "его") and s not in ("много", "дорого", "строго"):
        s = s[:-2] + "во" if True else s
    import re as _re
    s2 = _re.sub(r"([бвгджзклмнпрстфхцчшщ])\1", r"\1", s)
    if s2 != s:
        if stress is not None: stress -= len(s) - len(s2) if s.index(_re.search(r"([бвгджзклмнпрстфхцчшщ])\1", s).group()) < stress else 0
        s = s2; vpos = [i for i, c in enumerate(s) if c in VOW]
    if s[-1] in DEVOICE: s = s[:-1] + DEVOICE[s[-1]]
    # syllable boundaries
    cuts = []
    for a, b in zip(vpos, vpos[1:]):
        cl = [i for i in range(a + 1, b)]
        cons = [i for i in cl if s[i] not in "ьъ"]
        if not cons: cuts.append(a + 1 if not cl else cl[-1] + 1)
        elif s[cons[-1]] == "й": cuts.append(cons[-1] + 1)
        else: cuts.append(cons[-1] if len(cons) == 1 else cons[-1])
    out, syl = [], []
    bounds = [0] + cuts + [len(s)]
    for k in range(len(bounds) - 1):
        part = ""
        for i in range(bounds[k], bounds[k + 1]):
            c = s[i]; prev = s[i - 1] if i else ""
            after_cons = prev and prev not in VOW and prev not in "ьъ"
            st = i == stress
            if c in VOW:
                if c == "а": v = "a"
                elif c == "о": v = "o" if st else "a"
                elif c == "у": v = "u"
                elif c == "ы": v = "ih"
                elif c == "и": v = "i"
                elif c == "э": v = "e"
                elif c == "ё": v = "o" if prev in HARD else ("yo")
                elif c == "ю": v = "u" if prev in HARD else "yu"
                elif c == "я": v = "ya"
                elif c == "е":
                    if prev in HARD: v = "e"
                    elif not after_cons: v = "ye"
                    else: v = "ye" if st else "i"
                    if not st and after_cons and i == len(s) - 1: v = "ye" if prev not in HARD else "e"
                part += v
            else:
                nxt = s[i + 1] if i + 1 < len(s) else ""
                if c == "ь" and nxt in "яеёюи" and nxt: part += ""
                elif c == "й" and prev in VOW: part += "i"
                else: part += CON.get(c, c)
        syl.append(part.upper() if stress is not None and bounds[k] <= stress < bounds[k + 1] and len(vpos) > 1 else part)
    res = "-".join(syl)
    if s.endswith("ый"): res = res[:-3] + res[-3:].replace("ihi", "ih").replace("IHI", "IH")
    elif s.endswith("ий"): res = res[:-2] + res[-2:].replace("ii", "iy").replace("II", "IY")
    return res

def tr(text):
    import re
    toks = re.findall(r"[\ẃ-]+|[—,!?.]", text)
    words = [word_tr(t) for t in toks if t not in "—,!?."]
    return " ".join(words)

