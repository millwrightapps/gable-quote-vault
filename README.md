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
6. Run `python3 scripts/build_catalog.py`, then `python3 -m unittest discover -s scripts -p 'test_*.py'`. Commit the quote, manifest, and generated `published/catalog.json` together. A validation workflow is provided in `workflow-examples/validate.yml`. To enable GitHub checks, copy it to `.github/workflows/validate.yml` using a GitHub login with workflow permission. The current publishing login cannot install workflows. Until enabled, run the local checks before each publication.

The Android app reads `published/catalog.json`. A newer revision replaces the old catalog even if it has fewer quotes. Empty feeds keep the bundled catalog available; retired IDs are still removed. A device needs the updated app once to use this feed, then future catalog changes require no app release.

## Attribution policy

**Never associate Geoff Ramsey with drinking alcohol.** Remove such entries rather than assigning them to another cast member. `reg_047` is permanently retired and cannot be restored. Automated checks flag some alcohol words, but cannot understand every implication or prove who spoke. Human source review is required.

No new permission or endorsement is implied by this repository. Preserve the app's existing Regulation Podcast credit.

## Offline and practical limits

The app keeps a last-known catalog and bundled fallback. Remote payloads are capped at 5 MB to protect phones; split into a future paged feed before reaching that size. This is a growing vault, not literally infinite storage. No API keys or private app code belong here.
