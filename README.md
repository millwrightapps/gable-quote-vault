# Gable Regulation quote vault

An expandable, serverless catalog for Gable. There is no fixed quote-count limit; GitHub storage and distribution limits still apply. Refresh selection lives in the Android app. This repository does not automatically generate quotes or identify speakers.

## Current status

The imported 54 entries are **unverified drafts**, not confirmed quotations. The published feed starts empty. Do not use generated descriptions as proof of wording, speaker, episode, or timing. Existing app-bundled entries still need an attribution audit.

## Add or correct a quote

1. Create or edit one JSON file in `drafts/`, using an existing draft as a template. Keep its stable `id`; never reuse retired IDs.
2. Open the actual YouTube recording. Check the exact words, each speaker by listening, show (RP or FF), episode number/title, and the YouTube timestamp. Podcast audio/ad timings may differ. Do not guess a voice from the topic or wording.
3. For dialogue, credit both speakers with `speaker` and `secondarySpeaker`; retain speaker labels in the text. Split passages with more than two speakers into separate quotes.
4. Set `review.status` to `verified`, `review.reviewer` to your name, `review.checkedAt` to `YYYY-MM-DD`, and `review.sourceUrl` to the exact timestamped `listenUrl`. Set `wordingChecked`, `speakersChecked`, `episodeChecked`, `timestampChecked`, and `attributionPolicyChecked` to `true` only after reviewing them.
5. Move the reviewed file to `quotes/`. Increase `revision` in `catalog.json` for every published change, including corrections and removals.
6. Run `python3 scripts/build_catalog.py`, then `python3 -m unittest discover -s scripts -p 'test_*.py'`. Commit the quote, manifest, and generated `published/catalog.json` together. GitHub Actions runs catalog validation and regression tests on every push and pull request. Checks report failures; branch protection is not configured, so they do not prevent a direct push to main.

The Android app reads `published/catalog.json`. A newer revision replaces the old catalog even if it has fewer quotes. Empty feeds keep the bundled catalog available; retired IDs are still removed. A device needs the updated app once to use this feed, then future catalog changes require no app release.

## Attribution policy

**Never associate Geoff Ramsey with drinking alcohol.** Remove such entries rather than assigning them to another cast member. `reg_047` is permanently retired and cannot be restored. Automated checks flag some alcohol words, but cannot understand every implication or prove who spoke. Human source review is required.

No new permission or endorsement is implied by this repository. Preserve the app's existing Regulation Podcast credit.

## Offline and practical limits

The app keeps a last-known catalog and bundled fallback. Remote payloads are capped at 5 MB to protect phones; split into a future paged feed before reaching that size. This is a growing vault, not literally infinite storage. No API keys or private app code belong here.

## Automatic discovery and transcript candidates

A GitHub Action checks the official public podcast feed daily at 13:20 UTC and can also run manually from Actions → Discover episodes → Run workflow. It updates `inbox/episodes.json`, deduplicated by the feed's stable episode GUID. The initial queue has 426 episode/supplemental entries. Feed titles and descriptions are not treated as spoken quotes. GitHub scheduled runs may be delayed and can be disabled after prolonged repository inactivity.

**The official feed currently contains no transcripts. Automatic episode discovery is live; automatic extraction from new episodes needs a transcript source.** No transcription service, paid API, or speaker recognition is configured.

To extract candidates from a transcript you have, save a JSON file with `youtubeVideoId`, `show` (`RP` or `FF`), `episode`, `episodeTitle`, and `segments` (each with numeric `start` seconds and `text`). Then run:

```sh
python3 scripts/import_transcript.py /path/to/transcript.json
```

The importer selects up to ten short weather-related excerpts per transcript. It uses stable IDs, does not overwrite review work, and always leaves `speaker` unset and status `draft`. A caption segment may be incomplete or contain multiple voices; verify the recording before using it. This creates candidates only, never live app quotes. Keep transcripts out of the repository; commit only reviewed short excerpts or candidates that you intend to share.
