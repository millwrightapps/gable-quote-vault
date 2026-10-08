# Regulation Quote Vault

A free, local toolkit for building a catalog of **verified, timestamped quotes** from the Regulation Podcast (and F\*\*kface). It finds candidate moments by transcribing YouTube episodes with Whisper, on your own Mac. You listen to each one, credit the right speaker, and approve it into a JSON feed that apps and sites can read.

It was built for [Gable](https://millwrightapps.github.io/gable/), a weather app with a Regulation mode, and anyone in the community is welcome to use it for their own projects.

> Fan project. Not affiliated with or endorsed by the Regulation Podcast or its hosts. Please credit the show wherever you use quotes.

## How it works

```
YouTube playlist ──► download one episode's audio ──► Whisper (on your Mac) ──► timed transcript
                                                                                    │
       published/catalog.json ◄── Approve & publish ◄── you listen and credit ◄── candidate quotes (drafts/)
```

- **Timed to YouTube.** Whisper transcribes the YouTube upload itself, so every timestamp jumps to the right moment in the video. Podcast-feed audio has different ads and would drift.
- **Nothing automatic gets published.** Candidates arrive as drafts with no speaker. Only a person who has listened can approve one.
- **No cloud, no keys, no cost.** Transcription runs locally with [whisper.cpp](https://github.com/ggml-org/whisper.cpp). Audio is deleted right after each episode is transcribed. Transcripts stay on your Mac in `transcripts/` and are never committed.
- **GitHub is the database.** Drafts, approvals and the published feed are files in your copy of this repository. The dashboard saves changes with your own GitHub login.

## Requirements

- A Mac with Apple Silicon (M1 or newer). Intel Macs work, but transcription is much slower.
- About 2 GB of free disk space: the Whisper model is 550 MB, and one episode's audio is held briefly.
- [Homebrew](https://brew.sh), Python 3.10 or newer, and the [GitHub CLI](https://cli.github.com) (`brew install gh`).
- A GitHub account.

The launcher installs everything else the first time: yt-dlp, whisper.cpp, ffmpeg and the Whisper model.

## Set up your own vault

1. **Make your copy.** On GitHub, click **Fork** to create your own copy of this repository.
2. **Clone it** to your Mac and sign in to GitHub:
   ```sh
   git clone https://github.com/YOUR-NAME/YOUR-VAULT.git
   cd YOUR-VAULT
   gh auth login
   ```
3. **Open the dashboard.** Double-click **Open Quote Review.command**, then open **http://127.0.0.1:8765**. The first launch takes a few minutes while it installs tools and downloads the model. Keep the window open while you review.

The dashboard works out which repository to save to from your clone's `origin` remote, so there's nothing to configure.

### Start fresh (optional)

Your copy starts with this vault's approved quotes and drafts. To begin empty, delete the files in `quotes/` and `drafts/`, then run `python3 scripts/build_catalog.py` and commit. Keep `quarantine/`, which stops rejected wording from being collected again.

## Collect candidates

In the dashboard, click **Transcribe next episode** (about 5 minutes on an M-series Mac) or **Transcribe 5** (about 25 minutes). Progress shows at the bottom, and you can keep reviewing while it runs. **Stop after this episode** ends the run cleanly. Each finished episode is saved to GitHub as it completes, so stopping never loses work.

It works through the official Regulation Podcast YouTube playlist, oldest first, and skips episodes it has already transcribed (tracked in `inbox/whisper_processed.json`). Each episode yields up to 10 candidates after filtering:

- **Skipped:** the first two minutes, ad reads (including the lines just before a sponsor is named), show intros, fragments and incomplete sentences, and anything already in the vault (approved, drafted or removed).
- **Scored:** concrete, self-contained lines rank higher, with a boost for running bits from the [Regulation Lore dictionary](https://www.regulationlore.com.au/dictionary).
- **Unnumbered videos** (supplementals, specials) are skipped. Add quotes from them by hand.

From the command line instead:

```sh
.venv/bin/python scripts/whisper_youtube.py --batch 5        # next 5 episodes → drafts/
.venv/bin/python scripts/whisper_youtube.py --video VIDEO_ID # just transcribe one video into transcripts/
```

If YouTube starts asking this Mac to confirm it's not a bot, or rate-limits it, collection pauses for 30 minutes and picks up where it left off.

## Review and publish

Select a candidate, then:

1. **Play the 35-second preview.** It starts at the candidate's YouTube timestamp.
2. **Fix the exact words, and credit the speaker by listening.** For a two-person exchange, add the second speaker and keep the speaker labels in the text. Split anything with more than two speakers into separate quotes.
3. **Check the show, episode and start time,** and add weather or mood tags such as `rain`, `cloudy` or `chaos`. `random` fits anywhere.
4. **Tick the confirmation,** then **Approve & publish.**

Approving moves the draft to `quotes/`, increases the catalog revision and regenerates `published/catalog.json` in a single GitHub commit. **Remove quote** moves a draft to `quarantine/` so its wording is never collected again. **Add quote** saves your own find as a draft.

Speaker suggestions only appear when the exact same quote and episode already have a human-reviewed credit. The percentage measures text agreement, not voice recognition. Otherwise it shows "unknown". Nothing here identifies voices.

### Review from your phone

Double-click **Open Phone Quote Review.command**. It prints an address and a pairing code. Open the address on a phone on the same trusted Wi-Fi and enter the code. GitHub credentials stay on the Mac. This uses plain HTTP on your local network, so use it only on Wi-Fi you trust. Nothing is exposed to the internet.

## Attribution policy

- **Never associate Geoff Ramsey with drinking alcohol.** Remove such quotes rather than crediting someone else. Validation blocks the obvious words, but it can't catch every implication, so a person has to judge.
- **Never guess a speaker** from the topic or wording. If you can't tell by listening, leave it.
- Retired IDs (listed in `catalog.json` under `retiredIds`) can never be republished. `reg_047` is permanently retired.

## Use the feed

`published/catalog.json` is the whole public catalog. Read it from `https://raw.githubusercontent.com/YOUR-NAME/YOUR-VAULT/main/published/catalog.json`.

```json
{
  "schemaVersion": 1,
  "revision": 26,
  "retiredIds": ["reg_047"],
  "quotes": [
    {
      "id": "manual_35e543d57b4245a70bdc",
      "quote": "…",
      "speaker": "GAVIN_FREE",
      "show": "FF",
      "episode": 206,
      "episodeTitle": "The Last Episode of F**kface // Firing Squad [206]",
      "timestamp": "13:54",
      "timestampSeconds": 834,
      "youtubeVideoId": "ccBukHBOrb0",
      "listenUrl": "https://www.youtube.com/watch?v=ccBukHBOrb0&t=834s",
      "weatherTags": ["chaos"],
      "review": { "status": "verified", "reviewer": "…", "checkedAt": "2026-10-02" }
    }
  ]
}
```

- **Speakers:** `ANDREW_PANTON`, `GAVIN_FREE`, `GEOFF_RAMSEY`, `ERIC_BAUDOUR` and `NICK_SCHWARTZ`. A quote may also have a `secondarySpeaker`.
- **Shows:** `RP` (Regulation Podcast) or `FF` (F\*\*kface).
- **Revisions:** a higher `revision` replaces the whole catalog, including removals. Drop any IDs in `retiredIds`.
- **Size:** keep the feed under 5 MB. Split it into pages before it gets that big.

## Repository layout

| Path | What it holds |
|---|---|
| `drafts/` | Candidates waiting for review (unverified) |
| `quotes/` | Approved quotes, one file each |
| `quarantine/` | Removed or rejected candidates (blocks repeats) |
| `published/catalog.json` | The generated public feed |
| `catalog.json` | Revision number and retired IDs |
| `inbox/` | Collection progress, the lore dictionary list, and F\*\*kface archive recordings (episodes 1–56) |
| `scripts/` | Dashboard server, Whisper collector, filters, validation and tests |
| `dashboard/` | The review page |
| `transcripts/`, `models/` | Local only, never committed |

## Edit by hand

You can also work directly in the files. Copy an existing draft, keep its stable `id` (never reuse a retired one), check the recording, and set every `review` field: `status` to `verified`, plus `reviewer`, `checkedAt`, `sourceUrl`, and the five `…Checked` flags. Then move it to `quotes/`, increase `revision` in `catalog.json`, and run:

```sh
python3 scripts/build_catalog.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Commit the quote, `catalog.json` and `published/catalog.json` together. GitHub Actions validates the catalog and runs the tests on every push.

## Be a good neighbour

- Publish **short excerpts** with credit and a link back to the episode, never full transcripts.
- Collection downloads audio only to transcribe it on your own machine, deletes it straight away, and spaces out requests. Please keep it that way, and follow YouTube's terms where you live.

## Credits

- The Regulation Podcast and F\*\*kface, by Andrew Panton, Gavin Free, Geoff Ramsey, Eric Baudour and Nick Schwartz.
- Speech-to-text: [whisper.cpp](https://github.com/ggml-org/whisper.cpp), using OpenAI's Whisper large-v3-turbo model.
- Playlist and audio: [yt-dlp](https://github.com/yt-dlp/yt-dlp).
- Running bits: the [Regulation Lore dictionary](https://www.regulationlore.com.au/dictionary).
- Related community project: [regulationproject](https://github.com/michaelbooth1/regulationproject) by Michael Booth, with full feed transcripts and speaker analysis.
