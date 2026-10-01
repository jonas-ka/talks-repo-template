# Getting started: from zero to your first generated talk

This is the step-by-step for a new user. It assumes a Mac (Keynote export needs one; on
Linux everything except the Keynote and PowerPoint exporters works), no prior Claude Code
experience, and an afternoon. Steps 1–6 are set-up, 7–9 are the first run, 10–11 are the
part that decides whether the pipeline becomes yours: **giving Claude Code the context it
needs, and tuning the template over your first few talks.**

---

## 1. Accounts (20 min)

1. **Claude subscription.** Claude Code runs on a *Claude Pro* or *Claude Max* plan
   (claude.ai → upgrade), or on a pay-as-you-go API account. Pro is enough to start; the
   ingestion week used a lot of sessions, and Max removes the waiting when a 5-hour window
   runs out. One subscription covers the web app, the desktop app and Claude Code.
2. **Anthropic API key — optional, for one stage.** The vision classification of your old
   figures (`talks classify`) calls the API directly in a batch; that is billed per token on
   an *API* account (console.anthropic.com), not on the subscription. Order of magnitude:
   about $5 per 500 images at half price through the Batch API, so $20–30 for a large
   archive. You can skip this stage entirely and describe figures by hand as you need them.
3. **GitHub account**, and a **Google account** with API access only if you have Google
   Slides decks or want the shared figure library (step 6).

## 2. Tools (20 min)

```sh
# Homebrew (brew.sh), then:
brew install git gh uv typst          # Typst >= 0.14 is required (0.15 at the time of writing)
gh auth login                         # GitHub from the terminal
uv python install 3.12                # a Python for the pipeline
```

Fonts: **STIX Two Text** and **STIX Two Math** (free). macOS 13 and later ship both under
`/System/Library/Fonts/Supplemental/`; otherwise install them from stixfonts.org or
`brew install --cask font-stix-two-text font-stix-two-math`. Check with
`typst fonts | grep -i stix`.

**Visual Studio Code** (code.visualstudio.com) and, inside it, the **Claude Code** extension
(Extensions → search "Claude Code", publisher Anthropic). It installs the `claude`
command too; the first start asks you to log in with your Claude account. You can equally
run `claude` in a terminal — the extension only adds the side panel, diffs in the editor
and the file-aware prompts. The current install notes live at
https://docs.claude.com/en/docs/claude-code (search "Claude Code setup" if the path moved).

## 3. Your repository from the template (5 min)

1. Open https://github.com/<you>/talks-repo-template and click **Use this template →
   Create a new repository**. Name it (`talks-repo` is fine) and make it **private**: your
   decks and unpublished plots will live in it.
2. Clone it and install the pipeline:

   ```sh
   git clone git@github.com:<you>/talks-repo.git ~/Projects/talks-repo
   cd ~/Projects/talks-repo
   uv sync
   ```

## 4. Prove the toolchain (5 min)

```sh
uv run talks generate example-talk   # brief -> deck: PDF (tagged, PDF/UA-1) + HTML, report.md
uv run talks layout example-talk     # the layout check per page
uv run talks pptx example-talk       # a PPTX with live text, for Google Slides
open talks/example-talk/*.pdf
```

If this works, Typst, the fonts, Python and the theme are all in place. If `typst` complains
about a font, go back to step 2. The example deck is also what your own decks will look
like before you touch the theme.

## 5. Open the repository in VS Code and start Claude Code (5 min)

`code ~/Projects/talks-repo`, then open the Claude Code panel (or run `claude` in VS Code's
terminal). Claude Code reads `CLAUDE.md` in the repository root at the start of every
session: it is the one file that tells it who you are, what it may never do, how you like
to work, and what it has learned. **Everything below is about getting that file right.**

## 6. Optional: Google API access (15 min, only if needed)

Needed for Google Slides decks (read through the Slides API; the PPTX/PDF exports are
unreliable) and for mirroring the figure library to a shared drive. In Google Cloud
Console: create a project, enable the *Drive API* and *Slides API*, create an *OAuth client
ID* of type Desktop, download it as `credentials.json` into the repository root. The first
API call opens a browser to consent and writes `token.json`. Both files are git-ignored;
`CLAUDE.md` forbids committing or printing them. Put the API key for step 1.2 into `.env`
as `ANTHROPIC_API_KEY=...` (also ignored).

---

## 7. The first session: context, context, context (1 h)

Claude Code can only be as good as what it knows about you. Spend the first session
*telling*, not building. A prompt that worked:

> Read CLAUDE.md, PROJECT_PLAN.md and RECIPE.md. Do not run any pipeline stage yet. Then
> interview me to fill every placeholder in CLAUDE.md: my name and affiliation, the folders
> where my old decks are (read-only), the kinds of talks I give and for whom, my lab's
> colours, fonts and logos, which sponsors must appear where, accessibility rules I must
> meet, and the way I like to work. Write my answers into CLAUDE.md and show me the diff.

Have these ready and point Claude Code at them (paths, or paste):

- **Your CV's presentation list** — it becomes the spine (`talks.yaml`), one entry per talk.
- **The folders with your old decks** (Keynote, PowerPoint, PDF, Google Slides). Say which
  institution or period matters most; the pipeline takes a third of the time when it knows
  what to do carefully and what to skim.
- **Three reference decks** that look the way you want your talks to look. The theme in
  this template was *derived* from three such decks, not invented; ask for the same.
- **Brand assets**: logos (put them in `themes/logos/` under the names the theme uses),
  the colour palette, fonts, any style guide, where sponsor logos must and must not appear.
- **Rules**: what is confidential, what must never be deleted, what needs your sign-off,
  accessibility requirements (this template compiles tagged PDF/UA-1 by default).
- **Your habits**: "answer before you change anything", "ask before deleting", "explain
  terms", "commit after every stage", "write a review sheet I correct before you go on".
  These are in `CLAUDE.md` already; keep the ones you mean and change the rest.

Rule of thumb: if you would tell a new student something on their first day, it belongs in
`CLAUDE.md`. If it is something that *happened* (a decision, a number, a dead end), it
belongs in the log book (`docs/LOGBOOK_GUIDE.md`) — ask Claude Code to open one in the
first week: *"write a lab notebook for this repo and backfill it from our conversation and
the git log."*

## 8. Ingest your old decks, one stage at a time (1–2 days, mostly waiting and reviewing)

Each stage writes a review sheet into `review/`; you correct it, Claude Code applies the
corrections to the manifests, then the next stage runs. Resist running everything at once.

```
talks ingest-cv      CV -> talks.yaml                    review: talk types, awards, dates
talks discover       folders -> files.yaml               review: which files are which talk
talks enrich         durations, audiences, formats       review: the low-confidence rows
talks export         decks -> archive/<talk>/            Keynote via AppleScript: be at the Mac
talks extract        slides, pictures, build sequences
talks classify       captions, alt text, kinds (API)     review: captions and swaps
talks equations      LaTeX from Keynote, notes, vision   review: the rendered equations
talks catalog        assets/catalog.yaml + figures       review: supersedes suggestions
```

What to expect (from the first run of this pipeline, 67 talks over eight years): 864 files
found, 281 decks of which 212 were the author's own; 32 of 32 Keynote decks exported once
the exporter opened them the way a double-click does; 887 picture uses collapsing to 493
unique images after perceptual-hash deduplication; 87 unique equations, 430 of their uses
traced to Keynote's own LaTeX and 58 to speaker notes, only 10 needing vision; about $5 of
API spend per 500 classified images. The archive's binaries (2.7 GB) stay out of git.

## 9. Your first real talk (1–2 h)

1. Write `talks/<slug>/brief.yaml` (title, date, event, minutes, audience, topics, abstract,
   notes). Ask Claude Code to draft it from the invitation e-mail if you have one.
2. `uv run talks generate <slug>` → read `report.md`: the blocks chosen, the timing, the
   assets with problems, the research updates since your last talk on the topic, the
   layout flags.
3. Iterate with Claude Code on the blocks, slide by slide. Ask it to render and show you
   each slide; insist on the layout pass (`talks layout <slug>`) before you call it done.
4. `uv run talks pptx <slug>` if the venue uses Google Slides; `talks publish <slug>` to
   put the deliverables where you keep your trips.

## 10. Fine-tune the template over your first few talks (the important part)

The template is one person's practice. The first three to five talks are where it becomes
yours, and the work is small if you do it as you go:

- **Theme.** Compare the first generated deck with your reference decks side by side and
  dictate the differences (title size, where the logo sits, caption style, colours of
  panels). Every change goes into `themes/`, never into a single talk.
- **CLAUDE.md.** Each time Claude Code does something you did not want — deleted, assumed,
  skipped a review, wrote too much text on a slide — say so *and have it write the rule into
  CLAUDE.md*. Each time it learns a technical lesson (a Typst quirk, a font that falls back,
  a folder that holds placeholders), same thing. The file in this template grew from one
  page to ten this way; its "lessons" are why things work on the first try now.
- **Captions and alt text.** The drafts are right about nine times in ten. Review them in the
  sheet before a figure is used; the tenth one is the mislabelled photo that would have gone
  on a slide.
- **Blocks.** Prefer editing a block over editing `main.typ`: the next talk on the topic
  gets the improvement for free. Give blocks honest `minutes`.
- **Numbers on slides.** Have Claude Code print every number with its label before it goes
  on a slide. The one wrong number in this template's history came from two values read off
  one bare shell output.
- **Log book.** After every substantial session: *"add a log-book entry."* In a month you
  will want to know why a block says what it says.

## 11. Habits that keep it working

- One repository, private; the method public through a generated template if you like
  (`talks make-template` in the source repository).
- Commit after each stage and each finished slide; small commits with plain messages.
- Keep the figure library honest: every figure with source, alt text and version; a
  superseded figure can never appear in a new talk, because the build refuses it.
- When Claude Code's context gets long, it summarises; the git log and the log book are
  what carry over. Keep both current and sessions can be short.

Questions and improvements: open an issue on the template repository.
