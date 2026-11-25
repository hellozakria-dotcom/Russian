# Русский: Zakria's Russian

A small installable web app (PWA) for learning Russian: daily lessons with pictures, voice and
grammar notes, plus Anki-style flashcards with spaced repetition. It works offline, on Android
and on desktop, and has no server or account.

**Open it:** https://hellozakria-dotcom.github.io/Russian/

- **Android:** open the link in Chrome → ⋮ menu → *Install app* (or *Add to Home screen*).
- **Windows / Mac / Linux:** open in Chrome or Edge → the install icon in the address bar.

## Features
- **Lessons**: words with pictures, pronunciation in English letters (stressed syllable in CAPS),
  Russian voice, conjugation and case tables, example sentences and the lesson video.
- **Cards**: spaced repetition (Again / Hard / Good / Easy), Russian → English, English → Russian
  or mixed, one deck per day or everything. Keyboard: space, 1–4, P.
- **Add**: your own words and sets (type `'` after the stressed vowel: `соба'ка`).
- **Backup**: progress and your words are stored on the device. *Save backup* / *Load backup*
  moves them between phone and computer (loading merges, nothing is lost).

## Project layout
```
index.html             the whole app (HTML + CSS + JS, no build step)
manifest.webmanifest   install info · icons/  app icons
sw.js                  offline cache (generated)
content/dayN.json      lesson sources  ← edit these
days/dayN.json         lesson data used by the app (generated)
audio/  pics/          generated mp3s and pictures · videos/dayN.mp4  lesson videos
tools/                 build.py, translit.py, voice.py, setup.sh
```

## Adding a new day
1. `bash tools/setup.sh` (once: Piper Russian voice + SVG renderer; needs Python 3 and ffmpeg).
2. Create `content/dayN.json` (copy an existing day). Mark stress with U+0301 after the vowel
   (`чита́ть`). Only these fields are needed; `pr`, `audio` and ids are filled in by the build:
   ```json
   {"id": 3, "title": "Day 3", "topic": "Food",
    "words": [{"kind": "noun", "g": "m", "ru": "хлеб", "en": "bread", "pic": "Bread"}],
    "sentences": [{"word": "d3w1", "ru": "Я ем хлеб.", "en": "I eat bread.", "pics": ["Bread"]}],
    "notes": [{"h": "Title", "lines": ["…"]}]}
   ```
   `pic` / `pics` are [Microsoft Fluent emoji](https://github.com/microsoft/fluentui-emoji/tree/main/assets)
   folder names ("Open book", "Cat"…); the build downloads and renders them.
   Optional: `table` (`cols` + `rows`) and `note` on a word; `mk` (`"Я ви́жу {кот|а́}"`, which highlights the
   ending), `g` and `case` on a sentence; `tables` on the day.
3. Optional video: `videos/dayN.mp4`.
4. `python3 tools/build.py` → commit → push. GitHub Pages updates, and installed apps pick up
   the new day the next time they are opened online.

Pictures: Microsoft Fluent Emoji (MIT). Voice: Piper `ru-irinia-medium`.
