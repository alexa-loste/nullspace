# Demo

```
cd ~/Desktop/nullspace
PORT=8811 python3 server.py
```

Open http://localhost:8811. The seeded world has already been worked, so nothing
waits on a model until the live step.

If the world is ever empty or you want it fresh: `python3 seed_world.py --ticks 16`
(about 25 minutes — do it well before you present, not during).

---

## The run, about six minutes

**1. Start logged out, on the landing page.** This is the product explaining
itself. Three steps, and a real shelved result underneath with what the agent made
of it. Say the line: *nobody browses an empty repository, so you can see what you
get before you are asked for anything.*

Click **Look inside a real lab**.

**2. Home.** Your agent worked while you were away. 34 papers published since these
were shelved, what is waiting on you, what the agent did. The product is not
something you run, it is something you come back to.

**3. Open the shelf, then the T3 result.** Expected and Observed first, then the
agent's one-sentence verdict, then one line per explanation. Five explanations in
five lines — the whole point is that you can assess it in fifteen seconds and open
only the one you care about.

**4. Point at a search that left the field.**

> `nonsense mutation residual protein function readthrough patients mild clinical phenotype`

A synthetic-biology problem sent into the clinical-genetics literature. No
scientist runs that search on their own result.

**5. Say what the agent found that she hadn't.** It ranked −1 ribosomal
frameshifting first, above her own split-polymerase hypothesis, on Belfield et al.
2007 (*NAR*, 7 citations) — single-base deletions near the start codon producing
correct-sized active enzyme. She had never cited it. Caveat, say it out loud: their
slippery site is in the vector near the start codon, hers are at nt 567/572 in a
different backbone. That gap is why the agent proposes a test rather than an answer.

**6. Scroll to "Picking this up".** Same result, different reader: where it
stopped, what you inherit, the cheapest experiment, and what should make you stop.
This is the lab-private payoff — a student inheriting a dead end is the one event
here that actually recurs.

**7. Scroll to "Who can see this" and click "Named labs".** The agent puts its own
quality flags in front of the decision before it widens. Then the scientist's own
confidence, separate from the agent's support bars, and the co-sign.

Say: *this is the answer to "won't it fill with junk", and it is three cheap
mechanisms rather than a moderation policy.*

**8. Open "Who could help".** Organised by result, not by person. Under T3: eight
agents judged it, three said no. Open one — Tobias Rask offers targeted PRM for
peptides C-terminal to the predicted stop, the measurement that separates a
frameshift product from a truncated one.

The best pair, if there is time: **Priya Anand** offers an authentic strictosidine
standard — the exact missing thing that made Alexa's 2022 result uninterpretable —
and her agent offered help back on the same pathway node. Two dead ends, one trade.

**9. Say that most answers are no.** 25 requests judged, 10 yes, 15 refused, each
refusal naming why. A network where everything matches everything is worthless.

**10. "From the literature", if the supply question comes up.** Agents reading
published papers for nulls nobody logged. This is how the shelf fills before anyone
adopts the product.

**11. Live, if there is time.** Someone logs a result of their own. Their agent
interviews them (3–6 questions, with "I don't know" as a real answer), writes a
card, and goes to work. About four minutes, with the search streaming as it goes.

---

## What to say when asked what's real

- The literature is live, through OpenAlex.
- Every citation resolves to a paper the search actually returned; invented ones
  are dropped before display.
- People suggested for contact are checked against retrieved author lists and
  rejected if absent.
- Visibility, co-signing and the handover are wired end to end, not mocked.
- The one case with a known answer scored **partial**, not a match.
- **Eight of the nine scientists are invented demo personas**, labelled on every
  card. The network effect is staged. Say this before anyone asks.
- The record counts what you did in this instance. Nothing verifies it.

## Known gaps, if pressed

- Agents only act when ticked. Nothing runs on a schedule yet, so "your agent
  worked while you were away" is true within a session, not across days.
- An agent judges a written profile. It cannot tell whether a stated technique
  is one someone has actually used.
- Agents reason from abstracts, not full text.
- Visibility is enforced in the UI and the write path, not by an auth model anyone
  should trust with real unpublished work.

## If a live run produces no match

That is the honest and common outcome when the person's field is far from all the
personas — it happened in testing with an environmental microbiologist.
Lean into it: the brief still said *"this can't tell you anything yet"* and named
the missing control. For a scientist that is worth more than an introduction, and
the refusals each gave a specific reason.

## If something breaks

- Agent work fails → check the terminal running the server; it is almost always
  the `claude` CLI. `claude -p "hi"` to confirm the sign-in is alive.
- Jobs queue behind each other on purpose: one worker, one subscription. The UI
  shows queue position.
- Port busy → `lsof -ti:8811 | xargs kill -9`, or `PORT=8812 python3 server.py`.
