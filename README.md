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

**The official feed currently contains no transcripts.** GitHub Actions only refreshes the episode list; it does not fetch transcripts. The review dashboard pulls English captions directly from the official Regulation Podcast YouTube playlist when you press **Refresh queue**. The pull runs on your Mac, not on a GitHub cloud runner, because YouTube blocks many cloud IP addresses. No paid transcription service, cookie, proxy, or speaker recognition is used.

To extract candidates from a transcript you have, save a JSON file with `youtubeVideoId`, `show` (`RP` or `FF`), `episode`, `episodeTitle`, and `segments` (each with numeric `start` seconds and `text`). Then run:

```sh
python3 scripts/import_transcript.py /path/to/transcript.json
```

The importer selects up to ten short excerpts on any topic per transcript. It uses stable IDs, does not overwrite review work, and always leaves `speaker` unset and status `draft`. A caption segment may be incomplete or contain multiple voices; verify the recording before using it. This creates candidates only, never live app quotes. Keep transcripts out of the repository; commit only reviewed short excerpts or candidates that you intend to share.

## Review dashboard (on your Mac)

Double-click **Open Quote Review.command** from the vault folder. The first launch creates a private Python environment and installs the pinned, free YouTube tools. Or start the dashboard from a terminal:

```sh
./Open\ Quote\ Review.command
```

Then open **http://127.0.0.1:8765**. Keep that process running while reviewing. Refresh queue reads the official YouTube playlist and captions from this Mac; GitHub Actions does not make transcript requests. This is a local dashboard, not a publicly hosted admin page; GitHub credentials stay in your local `gh` login. No API keys or paid speech service are used.

Select a candidate → play its 35-second preview → correct words, speaker(s), episode and recording start time → confirm the recording and attribution policy → **Approve & publish**. Approval atomically moves the draft to `quotes/`, increments the revision and publishes the app feed on GitHub. A changed draft or concurrent GitHub update blocks publication rather than overwriting it. You need your existing `gh` login with repository write permission. Approvals are public Git commits. Keep unreviewed or unsuitable entries unapproved; “Review next” just skips them.

**Speaker suggestions:** the local version only suggests a speaker when the exact quote and episode match an already human-reviewed entry with consistent credits. Its percentage measures text agreement, not voice confidence. Otherwise it shows Unknown / confidence unavailable. Imported Gemini speaker names are displayed only as unverified draft credits. Voice recognition is not configured. This avoids inventing confidence values before any confirmed voice samples exist.

**Playback:** existing video IDs preview YouTube at the editable start time. Candidates without a video use the official feed's audio when the episode title matches; the player stops after 35 seconds. Feed ads may shift audio timing. The original transcript link remains available if audio or YouTube embedding fails. Approval requires a reviewed recording and timing, from YouTube or a supported RT Archive episode.

Each approval records the suggestion shown at review time and whether the reviewer agreed. This creates evaluation data for a future speaker model; no automatic-approval threshold is enabled.

**Refresh queue** collects more candidates on demand from the official Regulation Podcast YouTube playlist, saves drafts and progress to GitHub, and reloads the review list. Each click aims for 10 candidates and checks up to 20 unprocessed numbered episodes, with a five-second pause between transcript requests. It reports how many candidates were found and never publishes them as approved. Local uncommitted vault edits block collection to avoid mixing your work with imported drafts. If YouTube blocks requests from your connection, the dashboard pauses pulls for 30 minutes and leaves the video available to retry later.

**Add quote** opens a manual-entry form. Enter the quote, show, episode number/title, and an optional source link. **Save draft** writes only your entry to GitHub and selects it for review. It does not fetch transcripts or approve the quote. Speakers and playback timing are checked separately before publication.

Collection includes general podcast moments, jokes, stories, and lore—not only weather. New candidates receive the `random` tag so they fit the app’s general quote pool; reviewers can replace it with more specific weather or mood tags. Existing drafts and review decisions are preserved.

Batch collection stops after 10 new candidates or 20 numbered videos. It keeps looking past supplemental videos and unsuitable excerpts. Previously processed videos are skipped; temporary fetch failures can be retried later. Older imported drafts are left untouched.

## Review from your phone on the same Wi-Fi

Double-click **Open Phone Quote Review.command** on the Mac. It prints a phone URL and a fresh pairing code. Connect the phone to the same trusted Wi-Fi, open that URL, and enter the code. Keep the Mac awake and the dashboard running. If another dashboard is already running, stop that process first to free port 8765.

LAN mode requires pairing before reading drafts or making changes, keeps GitHub credentials on the Mac, checks the request host/origin, and limits pairing attempts. Pairing expires when the server restarts. This uses HTTP on your local network, so use trusted Wi-Fi only; no router port forwarding or public hosting is configured. The normal launcher remains local-only.

### Ad screening

The transcript importer skips the opening two minutes and screens nearby blocks around advertising signals (including a brand reveal after a generic promotional line). It also rejects common promotions. This is conservative screening, not a guarantee: reviewers should still reject ads or questionable context. Approved entries are not changed by this screening.

Automatic collection deduplicates wording across approved quotes, drafts, and quarantined excerpts, including capitalization, punctuation, and very small wording differences in longer sentences. It looks for another passage when a source repeats existing wording. Existing duplicate drafts are preserved under `quarantine/`; approved quotes are retained.

**Remove quote** removes the selected draft from the review queue and moves it to `quarantine/` in one GitHub commit. Removed wording is excluded from automatic imports. The copy remains recoverable on GitHub. This action does not delete or change approved quotes.

### Editorial quality screening

The collector ranks eligible excerpts instead of taking the first short line. A free, deterministic rule-based score favors complete sentences with clear opinions, contrasts, or unusual premises. It rejects fragments, filler openings, unclear references, and uncertain transcript context. Only scores of 70/100 or higher are eligible. Transcript imports return up to ten ranked candidates. Fewer candidates is preferable to filling the queue with weak lines.

Automatic drafts display an **Editorial score** with reasons. This is a heuristic, not a probability of humor, accuracy, or speaker identity. Existing manually entered drafts and approved quotes are unchanged. Weak automatic drafts remain recoverable in `quarantine/`.

### RT Archive recordings

The review dashboard supports **F\*\*kFace episodes 1–56** from [RT Archive](https://rtarchive.org/). Use **Add quote**, choose FF and the episode, then select **RT Archive** as the recording source during review. Choose the matching episode, enter the start time in seconds, and use the 35-second preview to check the words and speakers. Approved entries link to that archive recording at the reviewed time. YouTube remains available.

The recording index is `inbox/rtarchive_episodes.json`. As checked on October 2, 2026, none of these 56 recordings were marked as having transcripts. Connecting them enables manual review and playback; **Refresh queue does not transcribe or extract quotes from these recordings**. The archive is not a complete transcript source for all episodes. Availability and player loading depend on RT Archive and Internet Archive.

### Lore-aware selection

Candidate scoring uses an editable list of topic labels from the [Regulation Lore dictionary](https://www.regulationlore.com.au/dictionary), stored in `inbox/lore_terms.json`. Definitions and example sentences are not imported as quotes. Exact normalized phrase matches add a relevance boost and appear in the candidate’s score explanation. Generic single-word entries are omitted to reduce random matches. Matches cannot bypass fragment, ad, intro, duplicate, or human attribution checks; dictionary mentions do not identify a speaker.

Each newly processed video can contribute multiple distinct candidates. Previously processed videos are not automatically re-fetched, and YouTube rate-limit backoff still applies. Supplied transcript imports can contribute up to ten ranked candidates. Manual entry remains available without collection.
