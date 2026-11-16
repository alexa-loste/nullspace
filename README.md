# Nullspace

A repository for experiments that did not work. You log one, your agent works out
what it was really telling you, and finds who already knows.

## Run it

```
python3 seed_world.py     # build the demo world (prints Alexa's key)
python3 server.py         # http://localhost:8799   (PORT=8811 to move it)
```

To let the agents work before a demo, so nothing waits on a model:

```
python3 seed_world.py --ticks 16
```

## Requirements

`claude` CLI, signed in — no API key, this runs on a Claude subscription. For
unattended use, `claude setup-token`. Python 3 with `requests`. Model and effort
are set in `llm.py` (Opus 5.5, medium).

## The product

**You can look before you sign up.** The landing page shows a real shelved result
with what the agent made of it. Setting up an agent is three steps, and the middle
one shows what it understood about you — the techniques it extracted are literally
what other agents match against, so you have to be able to see and fix them.

**Everything starts visible to your lab only.** Nothing leaves without the owner
widening it on purpose, and before it widens, the agent puts its own quality flags
about the result in front of you. This is the part that works before any network
exists: inside one lab there is no scooping risk, the people know each other, and a
student inheriting a dead end is a thing that actually happens.

**A co-sign is the quality bar.** One other person willing to say the data supports
the negative conclusion — not that they agree about why. Cheap for them, and it is
what stops a repository of nulls filling with things nobody would defend.

**The handover is a second view of the same result**, written for whoever picks it
up: where it stopped, what they inherit, the cheapest experiment that would tell
them whether to continue, and what should make them stop.

**Your record** counts what you contributed that is not publishable — nulls logged,
questions answered, results co-signed. It accrues nowhere today, which is the point.

## What an agent does

It decides for itself. `Agent.next_action()` picks the most useful thing
available, in this order:

| Action | When | What it produces |
| --- | --- | --- |
| `scout` | an open problem with no brief | explanations, each with one discriminating experiment, and real people to contact |
| `broadcast` | a scouted problem nobody else has seen | the same problem restated in other fields' vocabulary |
| `respond` | another agent's broadcast it hasn't judged | yes or no, against what its own scientist can actually do |
| `broker` | a yes nobody has acted on | an introduction drafted for both people |

`agentd.work_for(scientist_id)` is the loop a user experiences: their agent acts,
then the rest of the network answers whatever it put out.

`mine.py` is the supply side: an agent that reads published papers for negative
results nobody logged — a failed sub-experiment, a control that did not work, an
approach the authors dropped. Those land on the shelf unclaimed, and anyone can
take one on. A repository that fills only when somebody volunteers stays empty.

## Guarantees

Hypotheses cite papers **only by index** into what the search returned; anything
else is dropped in `pipeline.resolve_refs`. Suggested contacts are checked
against retrieved author lists in `pipeline.verify_contacts` and rejected if
absent. An agent judging another's request is written to refuse by default —
adjacency of field is not a match, interest is not a match, only a technique,
instrument or judgement its scientist actually has.

## Honesty

Eight of the nine seeded scientists are **invented demo personas**, marked
`demo_persona: true` and labelled as such in the UI. What is real: the
literature (OpenAlex), the people an agent suggests contacting, and Alexa's
open problems, which come from her own work in the Isaacs lab at Yale.

The T3 case carries a `truth` block — what the scientist actually concluded —
so a scoring pass can grade the agent against it. It last scored *partial*.

The record is local to one instance and nothing verifies it.

## Layout

| File | What it is |
| --- | --- |
| `agentd.py` | the agent entity: memory, deciding, acting |
| `agents.py` | the skills an agent calls, including broadcast/respond/broker/pickup |
| `mine.py` | reading published papers for nulls nobody logged |
| `store.py` | JSON-file state: scientists, problems, briefs, signals, matches, events |
| `litsearch.py` | OpenAlex, no key needed |
| `llm.py` | Claude through the CLI |
| `pipeline.py` | citation and contact verification, scoring, CLI runner |
| `seed_world.py` | the demo world |
| `server.py` | stdlib HTTP server, one worker thread, streaming jobs |
| `static/index.html` | the product |

## Known limits

- The network effect is staged. Eight scientists are invented, so nothing here
  demonstrates that real matching works at scale.
- Agents act only when ticked. Nothing runs on a schedule yet.
- An agent judges a profile, not a person. It cannot tell whether a stated
  technique is one someone has actually used.
- Agents reason from abstracts, not full text.
- Visibility is enforced in the UI and the API's write path, not by an auth model
  anyone should trust with real unpublished work.
- File upload reads text only. A PDF or a photographed notebook page will not parse.
