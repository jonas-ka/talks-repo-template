# lab-templates

The canonical home of the Karthein Lab's document templates and style (Typst themes for
slides, posters, lecture notes, CV and lab notebook; palette and tokens; matplotlib style and
figure notebook; the guides). Public repository; consumers pull it as a git subtree into
`lab/` and pin a tag. `README.md` says how; `CHANGELOG.md` says what changed in each tag.

## Hard rules

- **No private material.** No real logos (placeholders only), no figures of the group, no
  names of students, no absolute paths of anyone's home folder, no Drive mirror paths or
  Drive ids, no credentials. The lab's public contact address may appear (it is on every
  slide footer); personal addresses of others may not. The CI scan (see
  `.github/workflows/ci.yml`) fails the build on the home-folder prefix, the Drive mirror
  prefix and API-key patterns.
- **A change compiles the examples** (`make check`: every `examples/*.typ` with
  `--pdf-standard ua-1`) before it is committed; a tag is made only on a green CI.
- **Versions are tags `vYYYY.MM.N`**; `VERSION` holds the current one; `CHANGELOG.md` gets a
  line per change under the next tag. Consumers update deliberately by tag, never silently.
- **Accessibility stays built in**: every theme sets document title and language, figures
  and equations need alt text (`fig`, `cat-fig`, `eq(alt:)`, the `.alts.yaml` sidecar), the
  palette's contrast ratios are in `palette.yaml` and are not lowered.
- **Drive copies are create-only**: `scripts/sync_drive.py` never overwrites, renames or
  deletes; a changed file goes up under a versioned name.

## Working style

- Answer questions before making changes; ask before deleting; explain plainly.
- Edits to a theme while building a document happen in the consumer's `lab/` folder and are
  pushed upstream with `scripts/lab-templates.sh push` (that is the intended path), or here
  directly. After a push, bump `VERSION`, add the changelog line, tag, and pull the tag into
  the other consumers.
- The layout pass applies to the examples too: compile, look, fix.

## Consumers (pull by tag)

`jonas-ka/talks-repo` (private; also generates the public `talks-repo-template` from its
`lab/`), `jonas-ka/phys206-mechanics`, `jonas-ka/phys698-nucl-exp`, `jonas-ka/karthein-cv`,
and, once wired, `fastsims` and `ion-optics-surrogate` (lab notebook template, figure README).
`.github/workflows/update-consumers.yml` opens an update pull request in each when a tag is
pushed; it needs a `CONSUMER_TOKEN` secret (a fine-grained personal access token with
contents and pull-request write on those repositories) and does nothing until one exists.

## Where things came from

Themes and guides were written in `talks-repo` (September 2026) and moved here on
2026-10-02; the lab-notebook template and the figure README were canonical in `fastsims`
until then. History before the move is in those repositories.
