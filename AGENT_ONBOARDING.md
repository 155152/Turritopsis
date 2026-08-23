# Filling a scanned project

`turritopsis init --scan` gives you addresses, not knowledge. Every Stage body
arrives as `[Placeholder: ...]` with `Status: unresolved`. This document is the
contract for turning that skeleton into a project map worth trusting.

Run this first:

```bash
turritopsis brief
```

It sorts the remaining work into three piles, and the piles are the whole method.

## 1. Settled — do not re-derive

`scan-evidence.json` already holds the bounded declaration map: what each covered
source file declares, how many modules import it, and explicit coverage counts for
anything the scan budget omitted. `scan-anomalies.json` already holds the
cross-layer disagreements the machine could prove.

Read them. Do not rebuild them. Re-deriving the structure is the exact cost
Turritopsis exists to remove — if the first agent has to read the whole repository
to build the map, the cost has only moved to the first window instead of
disappearing.

Anomalies are **leads, not facts**. They live beside the knowledge base and never
inside it. Confirm one before it changes a Stage body; never paste one in.

## 2. Self-serve — go read the repository

Stages under code-shaped Currents (`anatomy`, `flow`, `storage`, `gateway`, …) are
answerable by reading. Open the files listed under `## Evidence to review`, follow
the imports, and write what the module is responsible for.

**Never ask a person a question a grep would have answered.** That is the rule that
makes the human questions worth answering when you do ask them.

Write only what you verified:

```
Summary: Requests enter through app.py and are dispatched by router.dispatch().
Verified: 2026-08-24 by agent
Status: current
```

If you could not confirm something, leave it as an explicit placeholder. A
plausible guess in a Stage body is worse than an empty one, because the next agent
cannot tell them apart.

## 3. Ask — only a person can answer

`genesis`, `bounds` and `manual` are always created empty, on purpose. A scan sees
only code, and these three were never committed to it:

| Current | What is missing | Why code cannot supply it |
|---|---|---|
| `genesis` | why this design won, what was tried and rejected | rejected designs leave no files |
| `bounds` | what must never change, what looks unused but is load-bearing | the code shows what is, never what must not become |
| `manual` | what to check first when it breaks, what is still manual | recovery lives in habit, not source |

`turritopsis brief` drafts these questions for you, and every anomaly becomes a
question with its evidence already attached:

> `SHADOW_COLLECTION` holds different values in `writer.py` (`'shadows'`) and
> `reader.py` (`'shadows_v4_1024'`). Which one is authoritative, and is the other
> an unfinished migration?

The person supplies judgement. You supply the lookup. Arriving with "which of these
two is right, here is where each one lives" respects their time; arriving with
"tell me about the codebase" does not.

Record answers with attribution, because provenance is what makes them trustworthy
later:

```
Verified: 2026-08-24 by an (handoff conversation)
```

## When a human handoff exists

Drop `HANDOFF.md` (or `.turritopsis/handoff.md`) in the project and `brief` will
surface it first.

Treat it as **authoritative about intent, provisional about code**. It is the best
available source for priorities, red lines and what is frozen. It can also be six
months stale about a module that moved last week. Verify every claim about current
behaviour against the repository before recording it — and when the handoff and the
code disagree, that disagreement is itself worth a question.

Then drop every drafted question the handoff already answers. Asking something
already written down is how an agent teaches a person to stop writing things down.

## Done

A Stage is finished when its body says something the repository could not have told
you, or says something the repository confirms and cites where. Anything else stays
a placeholder.

Verify with:

```bash
turritopsis brief          # remaining should be shrinking
turritopsis anomalies      # findings you resolved should be gone
```
