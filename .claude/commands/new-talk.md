---
description: Make one talk end to end - brief, generate, layout pass, report, (publish), log book, commit
argument-hint: <slug, or a description like "TRIUMF colloquium, 45 min, nuclear, 11 Nov">
---

Make one talk from start to finish. The talk: $ARGUMENTS

Follow CLAUDE.md throughout (hard rules, "Answer questions before making changes", Slide
style, the layout pass). Work through these steps in order and report briefly after each.

1. **Find or draft the brief.**
   - If `talks/<slug>/brief.yaml` exists (the argument is a slug, or matches a folder under
     `talks/`), read it and any `TODO.md` or notes in that folder.
   - Otherwise derive a slug `YYYY-MM-<event>` from the description and draft `brief.yaml` in
     the schema from CLAUDE.md (title, date, event, duration_min, audience, topics, abstract,
     notes, sponsors, spine). Fill only what the description and `talks.yaml` support; mark
     the rest `TODO`.
   - Show the brief to the author and wait for corrections before generating. This is the one
     stop that is always made.

2. **Look back.** Find the most recent talk in `talks.yaml` that shares the brief's topics,
   and list the `updates.md` entries dated after it. Name blocks that look stale given those
   updates, and any figure whose catalog entry has a newer version (`supersedes`).

3. **Generate.** Run `uv run talks generate <slug>` (`--force` if `main.typ` exists and the author
   agreed to regenerate). Report the blocks, the minutes against the budget, any asset problem
   (missing alt text, superseded asset, missing file) and the compile result. If the time does
   not fit, propose which blocks to drop or add, or use an explicit `blocks:` list in the brief.

4. **Layout pass.** Run `uv run talks layout <slug>`, then render every page to PNG and look
   at each one. Fix spacing, fill, column balance, caption lines and figure alignment in the
   blocks (not in `main.typ`, which is regenerated), recompile, and look again until every
   page is presentable. A fix that belongs to the theme goes in `lab/themes/` and upstream
   with `scripts/lab-templates.sh push`. Slide titles are in Title Case; one figure per slide;
   no bullet walls. A slide flagged text-heavy (more than 120 body words) loses at least 10 %
   of its words: rewrite more concisely, keep every number and claim that matters, then
   enlarge type or spacing so the body still fills the slide.

5. **Report.** Summarise for the author: the deck (page count, minutes, blocks), what changed since
   the last talk on the topic, open items, and the remaining layout flags with the reason
   each is acceptable. Write it to `talks/<slug>/report.md` as well.

6. **Exports and publish (on request only).** `uv run talks pptx <slug>` if a Google Slides
   version is wanted. `uv run talks publish <slug>` copies the PDF, HTML and PPTX to the
   Talks-and-Travel folder on Drive. Run the publish only when the author says so, after a
   `--dry-run` that shows the target folder.

7. **Spine and CV.** Check that the talk is in `talks.yaml` (generate appends it unless
   `spine: false`). Set `cv: false` for internal meetings so they stay out of the CV.

8. **Log book and commit.** Add a `#note` for this talk under today's `#day` in
   `notes/talks-repo-logbook.typ` (append a new `#day` if today has none). Record decisions,
   numbers and open items, not a narrative. Compile it with
   `typst compile --root . notes/talks-repo-logbook.typ`. Then commit the brief, the blocks,
   `talks.yaml` and the log book, with a descriptive message; built PDFs, HTML and PPTX stay
   ignored. Push.
