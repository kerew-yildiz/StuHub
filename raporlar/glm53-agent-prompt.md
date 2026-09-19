# StuHub — 13-Item Improvement Batch (Sequential, Single Agent)

## Who you are and how you must work

You are the ONLY agent working on this job. You have NO parallelism: never spawn workers,
never split tasks. Work strictly phase-by-phase, in the given order. You may not start
Phase N+1 until Phase N has passed its Definition of Done.

You work inside the StuHub repository: React 18 + TypeScript + Vite + Tailwind frontend in
`apps/frontend`, FastAPI + SQLite backend in `apps/backend`. You can find files yourself —
paths mentioned below are hints, not exhaustive instructions.

## Language rules (STRICT)

1. All work you do is in ENGLISH: your reasoning, code you write, NEW code comments, test
   names, commit messages. Do not write Turkish anywhere except the single final report.
2. Do NOT modify pre-existing Turkish comments or Turkish UI strings unless a task
   explicitly requires it. User-facing UI copy (labels, buttons, aria-labels, tooltips)
   must REMAIN TURKISH — the product language is Turkish.
3. At the very END of the whole job, write ONE report in TURKISH (see "Final report").
   That is the only Turkish artifact you produce.

## Hard rules

- Git: at the start, create branch `feat/glm-13-item-batch` from the current default
  branch. Commit after each completed phase with a clear English message. NEVER push.
- Never leave the repository with failing tests, lint, or typecheck.
- No database schema changes. No new runtime dependencies unless a task says so.
- Do not rename public API endpoints; prefer backward-compatible changes, and when a
  response field must be removed, update every frontend consumer and test in the same phase.
- Do not touch deployment configs, seed data, or user data.

## Environment

- Windows. Backend tooling: `uv` (run inside `apps/backend`), frontend: `npm`
  (run inside `apps/frontend`).
- Backend checks: `uv run ruff check src tests`, `uv run pyright`, `uv run pytest -q`
- Frontend checks: `npm run lint`, `npm run typecheck`, `npm test`; final also `npm run build`
- Global quality gate (end of every phase for the area you touched, and ALL of them in
  the final phase): every command above must pass.

## Codebase map (hints)

- Frontend design system: `apps/frontend/src/styles/theme.css` (tokens, glass system,
  cursor ring styles). Components in `apps/frontend/src/components/`, pages in
  `apps/frontend/src/pages/`, hooks in `hooks/`, API clients in `api/`. Tests are vitest,
  colocated as `*.test.tsx`.
- Backend LLM prompt strings live in `apps/backend/src/prompts/` as Python constants.
  Generation services in `apps/backend/src/services/`, HTTP layer in
  `apps/backend/src/routers/`, tests in `apps/backend/tests/` (pytest).
- PDF export engine: backend `services/export_service.py` — a pymupdf "Story" HTML+CSS
  text layer plus a PyMuPDF drawing layer (page background, topic cards, header, footer).

---

## Phase 1 — Performance: remove cursor-reactive effects, add one global cursor glow

Goal: the app feels heavy because of per-frame cursor-reactive visual effects. Remove ALL
of them and replace with ONE subtle global cursor glow.

What to change:
- Remove the panel reflection/glow system entirely: the `data-reflect` panel attribute
  machinery, the `::after` reflection overlays on `.glass-panel`, the `--reflect-*` token
  block, and the per-frame CSS variables used only by that system (edge/parallax/smear
  state), plus the CursorRing logic that scans hovered panels and writes those variables
  every frame.
- Remove the glow box-shadows attached to cursor ring states (the cursor-glow tokens and
  the box-shadow rules that use them on ring/beam elements). The ring itself stays.
- KEEP: the custom cursor (ring, dot, beam), all hover effects (glass sweep, lift,
  brightness — they are state-based, not cursor-tracked), the `pointer: coarse` and
  `prefers-reduced-motion` guards and tests that rely on them.
- ADD one global cursor glow: a fixed, pointer-events-none layer (extend the cursor
  component or add a sibling element) rendering a large, heavily blurred radial gradient
  that follows the cursor. Requirements: diameter roughly 500-700px, blur equivalent of at
  least 40px, peak alpha at most 0.10, white in dark theme and black in light theme
  (derive from existing color tokens). No mix-blend-mode, no backdrop-filter — it must be
  a single cheap composited layer positioned via transform (use the existing
  requestAnimationFrame pattern already present in the cursor component).

Definition of Done:
- No `data-reflect` selectors, `--reflect-*` tokens, or reflection scan logic remain.
- The glow layer exists, is mounted with the same reduced-motion / coarse-pointer guards,
  and there are no per-frame DOM reads of panel rects.
- Cursor component tests updated: reflection assertions removed, glow layer mount asserted.
- All frontend gates pass.

---

## Phase 2 — Remove the [n] citation system end-to-end (keep source-grounded generation)

Goal: the numbered-citation system ([n], ⟨n⟩) must disappear from everything the end user
sees, together with its validation machinery. Note/quiz/flashcard/chat generation must
STILL be grounded in retrieved sources — grounding is mandatory, citation display is gone.

What to remove:
- Prompts (`apps/backend/src/prompts/`): every citation rule block ("ATIF KURALLARI",
  `[n]` requirements, citations_json blocks, "Her soruya/karta atıf ekle" rules) from the
  note prompts, quiz prompts, flashcard prompts, overall quiz prompts, and chat prompt.
- Backend generation (`services/`): the citation registry/resolution logic, citation
  validation (fuzzy quote checking), the bibliography/"Kaynakça" block generation, and the
  citation fields in generated JSON schemas for quiz and flashcards
  (`citations: [{"id": N}]`). Citations are no longer produced, stored requirements, or
  validated.
- KEEP completely: retrieval/RAG grounding, the source fallback chain that guarantees
  notes are never incomplete (web search fallback for CONTENT, slides fallback,
  deterministic fallback), coverage checking of note structure.
- User-facing warnings about missing sources must not surface anywhere (e.g. flashcard
  warnings like "atıfsız kartlar (kaynak yok)"). Backend may log them; they must not reach
  the UI. Remove/replace the warnings plumbing where it would otherwise be displayed.
- Frontend: remove citation chips, `stuhub-citation://` link scheme, CitationLink and
  CitationPopup usage in the note viewer, citation chip lists in flashcard and quiz
  feedback components, the Citation types in API clients, and their tests. Note export
  code that strips `[n]`/`[Slide N]` markers may stay (harmless) or be simplified.

Definition of Done:
- No user-visible citation markers, citation chips, bibliography sections, or
  source-not-found warnings remain.
- grep for `[n]`-related identifiers (`citation`, `CitationPopup`, `citations_json`
  display usage, `⟨`, `stuhub-citation`) shows no rendering path or generation requirement
  left, except harmless historical-data compatibility (old notes may still contain `[n]`
  text in stored markdown — that text simply renders as plain text).
- Backend + frontend tests updated; all gates pass.

---

## Phase 3 — Note viewer visual cleanup (content untouched) + icon-only collapse button

Goal A: the current note output is efficient but visually crowded; improve visual
separation and order in the note reader WITHOUT changing any content.
- Only presentation: refine heading hierarchy, vertical rhythm, spacing between sections,
  list spacing, blockquote/callout styling, and per-section visual separation, consistent
  with the existing monochrome glass design system in theme.css.
- The markdown input to the renderer must remain byte-identical. No content
  transformation, no reordering, no rewriting, no truncation.

Goal B: the "Daralt (liste görünümü)" toggle button becomes icon-only (no text).
- Use a lucide-react icon that communicates collapse/expand (and switch icon when toggled
  to full-note mode, or use two distinct icons). Keep Turkish accessible name and tooltip
  (aria-label / title), e.g. "Liste görünümü" and "Tam not" depending on state.
- Update the NoteViewer tests that assert on the button text.

Definition of Done:
- Reader looks calmer and more structured; content unchanged (tests assert same markdown
  in, same text out).
- Icon-only button implemented; tests updated; frontend gates pass.

---

## Phase 4 — PDF download naming based on chapter title

Goal: downloaded PDFs are currently named like `stuhub-not-{id}-{variant}.pdf`. New rule:
- digital variant: `{chapter title} - Digital Copy.pdf`
- physical variant: `{chapter title} - Physical Copy.pdf`

What to change:
- Backend export endpoint: build the filename from the chapter title (it already joins
  chapters for the title), sanitize filesystem-unsafe characters (`/ \ : * ? " < > |`),
  collapse whitespace, and send a proper Content-Disposition with both an ASCII fallback
  and RFC 5987 `filename*=` for Turkish characters.
- Frontend `exportNotePdf`: derive the download filename the same way (it has the chapter
  title available on the notebook page — pass it down or parse the Content-Disposition
  header; pick ONE approach and implement it consistently).
- Markdown export naming stays as-is.

Definition of Done:
- Downloading a digital PDF from the UI saves as e.g. "1. Perspectives Research - Digital Copy.pdf".
- Backend test asserts the header and sanitization; frontend test asserts the chosen
  filename derivation; all gates pass.

---

## Phase 5 — PDF layout redesign (cards, headings, footer, overflow, margins)

Goal: redesign the topic-card layout in the PDF export engine. This is one coherent pass
over the same file/engine; do NOT ship intermediate states.

New layout rules:
1. Sub-topic headings (headings matching the note's topics list) are OUTSIDE the cards:
   horizontally centered, bold, styled distinctly. Immediately below each heading, a card
   starts and contains that heading's content, until the next sub-topic heading.
2. Page-break rule for cards: if a card's content does not fit on the page, the card CLOSES
   at the page bottom (rounded bottom corners) and a NEW card OPENS at the top of the next
   page (rounded top corners), with the content continuing. The old rule — an open card
   continuing across a page boundary as a flat-ended box — must be removed.
3. Main note title (the note's h1): horizontally centered, in a LARGER font size than
   sub-topic headings, with a horizontal separator line directly below it. The separator
   width equals the rendered width of the LAST line of the title (if the title wraps to
   multiple lines, measure the final line, not the longest or the whole block).
4. Footer: the footer elements ("StuHub · date" left, page number right) must be INSIDE
   the card area at the bottom of each page — cards must extend to enclose the footer band.
   Content flow must stop above the footer so content and footer never overlap.
5. Vertical overflow: text must never escape card boundaries. Recompute card rectangles
   from the actual text layout, keep consistent internal padding, and ensure the drawn
   card fully contains every text span it wraps (including the last line of lists and
   code blocks).
6. Side margins: increase the page side margins of the cards by 35% (currently about
   16pt, so about 21.6pt) and align the text block with the new card geometry.

Definition of Done:
- Backend tests updated/extended for: centered sub-topic headings outside cards; card
  closed-and-reopened across page breaks (rounded corners on both sides of the break);
  footer positioned inside the card rect with no content overlap; 35% larger side margins;
  separator line width measured from the last title line.
- The test suite generates PDFs from fixture markdown that exercises: long headings,
  multi-line titles, long paragraphs, lists, code blocks, and a section breaking across
  pages. All backend gates pass.

---

## Phase 6 — Study time tracking: real, live values

Goal: study-time tracking must show real, current values for both chapters and courses.

Definitions (do not reinterpret):
- Chapter study time = time spent in the chapter workspace across ALL its tabs
  (Genel, Notlar, Quiz, Flashcard Practice, Materyale Sor) — in practice the whole
  notebook page session for that chapter.
- Course study time = time in the course-level views (Genel, Notlar, Kaydedilenler,
  Flashcard Practice, Kaydırarak Quiz, Materyale Sor, Ödev Değerlendir, Ödev Taslak Koçu)
  PLUS the sum of the course's chapter study times.

What to do:
- Verify and keep the existing tracking: chapter heartbeats fire while the notebook page
  is open and active (all tabs of the notebook page share the route, so confirm this holds
  when switching tabs), and course-level sessions record with the course id while on the
  course page. The backend totals endpoint already returns course total + per-chapter
  breakdown; reuse it.
- Display live values:
  - Notebook page overview ("ÇALIŞMA SÜRESİ" block): replace the static "Veri birikiyor"
    placeholder with the chapter's real accumulated time (from the study-time endpoint)
    plus the current live session seconds, refreshing at least every 30 seconds while the
    page is open. When there is no recorded time and no session time, show "0 dk"
    (remove the placeholder text entirely).
  - Course page: display the course's total study time (same endpoint, same live refresh
    behavior) in a suitable place in the course header/overview.
- Reuse the existing duration formatting helper (extract it to a shared module if it is
  currently component-local).

Definition of Done:
- A hook/component fetches study time, adds the live session increment, and refreshes
  periodically; unit tests with a mocked API cover both displays.
- The placeholder text is gone; tracking tests (heartbeat hook) still pass; all gates pass.

---

## Phase 7 — Small UI fixes: chapter heading, heatmap chat removal

Task A: the "Chapter'lar" section heading on the course page must be horizontally centered
and 1pt larger than other section titles (implement via a dedicated class or inline style
so other section titles are unaffected; base is 18px, so about 19.3px).

Task B: remove chat from the weak-topic heatmap completely:
- Frontend heatmap component: remove the CHAT column and the chat percentage from the
  legend/weights note.
- Backend heatmap: stop collecting the chat signal and renormalize the weakness weights to
  quiz 0.625 / card 0.375 (the renormalization of the current 0.5/0.3/0.2). Remove the
  chat question count and the chat weight from the API response.
- The chat service itself is NOT touched.
- Update backend and frontend heatmap tests.

Definition of Done:
- Heatmap table shows only KONU / QUIZ / KART / ZAYIFLIK; API no longer carries chat fields.
- "Chapter'lar" heading centered and +1pt; all gates pass.

---

## Phase 8 — Flashcard swipe animation rework (masked slide, 25% threshold)

Goal: replace the current swipe animation (whole card quickly fades + flies horizontally)
with a masked slide: the card slides out/in as if entering a closed area, with NO fade.

Behavior:
- The card container clips its content (an outer wrapper with overflow hidden masks the
  moving card). During a committed swipe the card slides horizontally out of the mask;
  the next card slides in. No opacity animation anywhere in this motion.
- Release rule: while dragging, if the user releases when the card has moved LESS than 25%
  of the card width, the card returns to its original position (smooth ease/spring back,
  no fade). If it has moved 25% or more (or a fast flick — adapt the existing flick
  detection to the new threshold), the swipe commits and the card slides out under the mask.
- Keep everything else: click-to-flip, Space to flip, keyboard arrows to answer, the
  DOĞRU/YANLIŞ stamps tied to drag direction and progress, the progress bar, exit flow,
  and the SRS rating mapping (right = good, left = again).
- Implementation notes: use the existing transform/transition patterns; no new
  dependencies. Be careful that the overflow-hidden mask does not break the 3D flip
  (put the mask on an outer wrapper and keep perspective on the inner element).

Definition of Done:
- FlashcardPlayer tests updated: release under 25% returns the card, at/over 25% commits,
  keyboard flows unchanged, and no assertion depends on opacity fade.
- All frontend gates pass.

---

## Phase 9 — Final verification, cleanup, Turkish report

1. Run EVERY quality gate: backend ruff + pyright + pytest, frontend lint + typecheck +
   test + build. Fix anything red.
2. Search the codebase for dead leftovers of the removed systems (citation plumbing,
   reflection tokens, unused exports) and clean them.
3. Write the FINAL REPORT in TURKISH to `raporlar/glm53-ui-pdf-isleri.md`, in the style of
   other reports in that folder. For each phase include: what changed (files + short
   description), how you verified it (test counts), and any known limitations. End with a
   short plain-Turkish summary a non-technical reader understands. This file is the ONLY
   Turkish text you produce in the whole job.

## Whole-job Definition of Done

- All 13 user items implemented exactly as specified above.
- Every phase's Definition of Done met; every quality gate green.
- Branch `feat/glm-13-item-batch` contains one or more clean English commits per phase.
- Turkish report written; no processes left running; no temp files left in the repo.
