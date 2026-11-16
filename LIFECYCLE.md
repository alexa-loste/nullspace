# The demo: one null, four years, two people

The arc is a full life cycle of a negative result — not a tour of features.
A result dies in 2022. The field moves. Someone else picks it up in 2026.

Everything in it is real except the people: the null is Alexa's own, the
literature is live OpenAlex, and the work published since genuinely came out
after the experiment was shelved.

---

## Why this arc and not a feature tour

A negative-results repository is easy to describe and hard to believe, because
the obvious objection is *nobody will use it*. The lifecycle answers that
objection in the only way that works: by showing that the person who logs the
null and the person who benefits are **different people at different times**,
and that the second one gets something worth having.

That is also why the demo needs more than one lab and more than one year.

---

## Act 1 — 2022. The null happens.

**Who:** Alexa, a graduate student. **Screen:** the result page.

She built a 13-gene camptothecin precursor pathway in yeast. No strictosidine
by LC-MS. No peak for its immediate precursors either. The project stopped.

Open the result and read the two lines at the top — Expected, Observed — then
the agent's verdict. The agent was given **only literature published up to
2022**, which is stated on the page. Its reading at the time:

> an uninformative null: with no authentic standard, no MS/MS, and no
> demonstrated flux at any single step, the experiment lacks the positive
> controls needed to distinguish a real absence from a detection failure

Five explanations, ranked, each with the experiment that would decide it.

**The line to say:** *this is what a null looks like when it is written down
properly. Normally it is a slide that says "didn't work" and then it is gone.*

## Act 2 — now. The agent goes back.

**Screen:** the same result, section "What the field did since 2022".

The agent re-reads the literature, this time with the cap lifted, and grades
its own 2022 reasoning against what was actually published. Each explanation
gets a verdict — held up, contradicted, superseded, or nothing bears on it —
and the whole null gets one of: resolved, narrowed, still open.

**The line to say:** *the agent is marking its own homework in public, and the
interesting outcome is not that it was right.*

Point at what changed: the same build has since been published working, at
titers a routine LC-MS would have seen easily. That moves the null from
"we can't tell" to "our build didn't flux" — a different, answerable question.

## Act 3 — someone is looking for a project.

**Who:** Theo, a rotation student. **Screen:** Ready to pick up.

He has no project. He opens the repository — not his lab's shelf, the whole
thing — sorted by how much the field has moved under each null. The ones at the
top are the ones later work has answered or narrowed.

**The line to say:** *a null whose literature has changed is the cheapest
project in science. The work is already done, the question is sharper than when
it was asked, and nobody is competing for it.*

This screen is the reason the repository has to be multi-lab. Inside one lab it
is a filing cabinet. Across labs it is a place to find work.

## Act 4 — the handover.

**Screen:** the result, section "Picking this up".

Not the page the original scientist reads. Where it stopped, what he would
inherit — strains, constructs, data — the cheapest experiment that would tell
him whether to continue, and the result that should make him stop. Plus who to
contact: another lab's agent offered an authentic standard, which is the exact
missing control that made the 2022 result uninterpretable.

**The line to say:** *this is the artefact that does not exist anywhere in
science today. When a student leaves, this is what leaves with them.*

## Act 5 — it gets handed over.

Alexa picks Theo and hands it to him with one line. It lands in his inbox with
the handover attached, not a link and a hope.

**The closing line:** *that is the whole product. A result that would have
died, a question that got sharper on its own, and a person who needed a project
finding one. The agents are what make it cost nobody anything.*

---

## Running it

```
PORT=8811 python3 server.py
```

Start logged out. "Look inside a real lab" enters as Alexa.

For Act 3 you want to be somebody else. The rotation student's key is printed by
`seed_repo.py`; paste it into "I have a key" on the landing page, or keep two
browser profiles open and switch between them. Switching accounts live is more
convincing than describing it.

## What to say when asked what's real

- The null is real, from the Isaacs lab at Yale.
- The literature is live OpenAlex, and the as-of cap is a real date filter on
  the search, not a prompt instruction.
- Every citation resolves to a paper the search returned; invented ones are
  dropped before display.
- The scientists other than Alexa are invented, and labelled as such.
- The nulls mined from published papers are real papers; the extraction is the
  agent's reading of the abstract, and it refuses most of what it reads.

## What is not built

- Nothing verifies that a co-sign came from someone qualified.
- Visibility is enforced in the write path, not by an auth model anyone should
  trust with real unpublished work.
- Agents read abstracts, not full text.
