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

The importer selects up to ten short excerpts on any topic per transcript. It uses stable IDs, does not overwrite review work, and always leaves `speaker` unset and status `draft`. A caption segment may be incomplete or contain multiple voices; verify the recording before using it. This creates candidates only, never live app quotes. Keep transcripts out of the repository; commit only reviewed short excerpts or candidates that you intend to share.

### Podscripts collection is enabled

The daily discovery workflow also checks [Podscripts](https://podscripts.co/podcasts/regulation-podcast/). It reads up to 20 previously unprocessed transcript pages per run, aiming for 10 new candidates, with a pause between requests, and collects at most **one short excerpt (25 words maximum) per episode**. It skips obvious promotional passages and supplements without explicit episode numbers. Candidates are saved under `drafts/podscripts_*.json`; processed source URLs are tracked in `inbox/podscripts_processed.json`.

Podscripts provides approximate **audio segment times**, not verified YouTube timestamps or speaker identities. These are stored separately in `source.audioSegmentTimestamp`; playback timestamps, links, and speakers remain unset. Human review is mandatory. Keyword filtering can still select an ad or an uninteresting/incomplete passage; reject those drafts. No automatic publication or paid transcription occurs. Regulation Search remains an alternative for manual cross-checking, not an integrated source.

## Review dashboard (on your Mac)

Run this from your local vault folder:

```sh
python3 scripts/review_server.py
```

Then open **http://127.0.0.1:8765**. Keep that process running while reviewing. This is a local dashboard, not a publicly hosted admin page; GitHub credentials stay in your local `gh` login. No API keys or paid speech service are used.

Select a candidate → play its 35-second preview → correct words, speaker(s), episode and YouTube start time → confirm the recording and attribution policy → **Approve & publish**. Approval atomically moves the draft to `quotes/`, increments the revision and publishes the app feed on GitHub. A changed draft or concurrent GitHub update blocks publication rather than overwriting it. You need your existing `gh` login with repository write permission. Approvals are public Git commits. Keep unreviewed or unsuitable entries unapproved; “Review next” just skips them.

**Speaker suggestions:** the local version only suggests a speaker when the exact quote and episode match an already human-reviewed entry with consistent credits. Its percentage measures text agreement, not voice confidence. Otherwise it shows Unknown / confidence unavailable. Imported Gemini speaker names are displayed only as unverified draft credits. Voice recognition is not configured. This avoids inventing confidence values before any confirmed voice samples exist.

**Playback:** existing video IDs preview YouTube at the editable start time. Candidates without a video use the official feed's audio when the episode title matches; the player stops after 35 seconds. Feed ads may shift audio timing. The original transcript link remains available if audio or YouTube embedding fails. Approval requires a reviewed YouTube recording and timing.

Each approval records the suggestion shown at review time and whether the reviewer agreed. This creates evaluation data for a future speaker model; no automatic-approval threshold is enabled.

**Refresh queue** collects more candidates on demand, saves them to GitHub, and reloads the review list. Each click aims for 10 candidates, checking up to 20 transcript pages; after recent episodes are exhausted it walks older index pages. It reports how many candidates were found and never publishes them as approved. Local uncommitted vault edits block collection to avoid mixing your work with imported drafts.

**Add quote** opens a manual-entry form. Enter the quote, show, episode number/title, and an optional source link. **Save draft** writes only your entry to GitHub and selects it for review. It does not fetch transcripts or approve the quote. Speakers and playback timing are checked separately before publication.

Collection includes general podcast moments, jokes, stories, and lore—not only weather. New candidates receive the `random` tag so they fit the app’s general quote pool; reviewers can replace it with more specific weather or mood tags. Existing drafts and review decisions are preserved.

Batch collection stops after 10 new candidates, 20 episodes, four older index pages, or about two minutes (an in-flight request may finish afterward). It keeps looking past supplemental episodes and unsuitable excerpts. One short excerpt per source is retained.

## Review from your phone on the same Wi-Fi

Double-click **Open Phone Quote Review.command** on the Mac. It prints a phone URL and a fresh pairing code. Connect the phone to the same trusted Wi-Fi, open that URL, and enter the code. Keep the Mac awake and the dashboard running. If another dashboard is already running, stop that process first to free port 8765.

LAN mode requires pairing before reading drafts or making changes, keeps GitHub credentials on the Mac, checks the request host/origin, and limits pairing attempts. Pairing expires when the server restarts. This uses HTTP on your local network, so use trusted Wi-Fi only; no router port forwarding or public hosting is configured. The normal launcher remains local-only.

### Ad screening

Automatic Podscripts collection skips the opening two minutes and screens nearby transcript blocks around advertising signals (including a brand reveal after a generic promotional line). Both importers reject common promotions. Suspect existing automatic drafts are retained in `quarantine/`, outside the dashboard queue and published feed. This is conservative screening, not a guarantee: reviewers should still reject ads or questionable context. Approved entries are not changed by this cleanup.
