"""State for Nullspace. One JSON file per record, no database.

    data/scientists/<id>.json   a person and their profile
    data/problems/<id>.json     an open problem belonging to a scientist
    data/briefs/<id>.json       what an agent found about a problem
    data/signals/<id>.json      a broadcast from one agent to all others
    data/matches/<id>.json      a brokered connection between two scientists
    data/events/<id>.json       one line in a scientist's inbox

Everything a user does has to survive a reload, so every write lands on disk
immediately. One global lock, one writer: the server is single-process.
"""

import json
import pathlib
import secrets
import threading
import time

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
LOCK = threading.RLock()

KINDS = ("scientists", "problems", "briefs", "signals", "matches", "events")


def _dir(kind):
    d = DATA / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_id(prefix=""):
    return f"{prefix}{secrets.token_hex(4)}"


def now():
    return time.time()


def put(kind, rec):
    """Write a record. Needs rec['id']."""
    with LOCK:
        rec.setdefault("created", now())
        rec["updated"] = now()
        (_dir(kind) / f"{rec['id']}.json").write_text(json.dumps(rec, indent=2))
    return rec


def get(kind, rid):
    f = _dir(kind) / f"{rid}.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def all_of(kind):
    out = []
    for f in _dir(kind).glob("*.json"):
        try:
            out.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return sorted(out, key=lambda r: r.get("created", 0))


def where(kind, **eq):
    return [r for r in all_of(kind) if all(r.get(k) == v for k, v in eq.items())]


def patch(kind, rid, **fields):
    with LOCK:
        rec = get(kind, rid)
        if not rec:
            return None
        rec.update(fields)
        return put(kind, rec)


def delete(kind, rid):
    f = _dir(kind) / f"{rid}.json"
    if f.is_file():
        f.unlink()


# ---------------------------------------------------------------- shapes

def scientist(name, field, token=None, **kw):
    rec = {
        "id": new_id("sci_"),
        "name": name,
        "field": field,
        "token": token or secrets.token_urlsafe(9),
        "adjacent_fields": kw.get("adjacent_fields", []),
        "techniques": kw.get("techniques", []),      # what they can actually do
        "equipment": kw.get("equipment", []),        # what they have access to
        "can_offer": kw.get("can_offer", []),        # how they could help someone
        "interests": kw.get("interests", []),
        "agent_name": kw.get("agent_name") or f"{name.split()[-1]}'s agent",
        "demo_persona": kw.get("demo_persona", False),
        "institution": kw.get("institution"),
        "onboarded": kw.get("onboarded", False),
        "seeded": kw.get("seeded", False),
        "lab": kw.get("lab"),
    }
    return put("scientists", rec)


def problem(scientist_id, card, **kw):
    rec = {
        "id": new_id("prb_"),
        "scientist_id": scientist_id,
        "card": card,
        "status": kw.get("status", "open"),   # open | explained | parked
        "transcript": kw.get("transcript", []),
        "brief_id": None,
        "signal_id": None,
        "source": kw.get("source"),
        "truth": kw.get("truth"),             # for the scored retrodiction case
        # A null starts inside the lab. Nothing leaves without someone widening
        # it on purpose, which is the only version of this a scientist would use.
        "visibility": kw.get("visibility", "lab"),   # lab | consortium | public
        # How sure the scientist is the effect is real, in their own words, and
        # who else in the lab was willing to put their name to it.
        "confidence": kw.get("confidence"),          # 0-100, set by the scientist
        "cosigns": kw.get("cosigns", []),            # [{scientist_id, name, created}]
        "origin": kw.get("origin", "logged"),        # logged | literature
        "source_paper": kw.get("source_paper"),      # set when mined from a paper
        "unclaimed": kw.get("unclaimed", False),     # mined, nobody has adopted it
        "pickup": kw.get("pickup"),                  # inheritance brief, when asked for
    }
    return put("problems", rec)


VISIBILITY = {
    "lab": ("Lab only", "Only people in your lab can see this."),
    "consortium": ("Named labs", "Labs you have named can see it. Nobody else can."),
    "public": ("Public", "Anyone can see it, and other agents can match against it."),
}


def event(scientist_id, kind, title, body="", **kw):
    """One line in a scientist's inbox. kind drives the icon and the action."""
    rec = {
        "id": new_id("ev_"),
        "scientist_id": scientist_id,
        "kind": kind,            # scouted | match | request | question | note
        "title": title,
        "body": body,
        "read": False,
        "problem_id": kw.get("problem_id"),
        "brief_id": kw.get("brief_id"),
        "match_id": kw.get("match_id"),
        "signal_id": kw.get("signal_id"),
        "actionable": kw.get("actionable", False),
    }
    return put("events", rec)


def inbox(scientist_id, limit=50):
    evs = where("events", scientist_id=scientist_id)
    return sorted(evs, key=lambda e: e.get("created", 0), reverse=True)[:limit]


def unread_count(scientist_id):
    return sum(1 for e in where("events", scientist_id=scientist_id) if not e.get("read"))


def by_token(token):
    for s in all_of("scientists"):
        if s.get("token") == token:
            return s
    return None


def reset_demo():
    """Wipe everything. Used by the seed script."""
    with LOCK:
        for k in KINDS:
            for f in _dir(k).glob("*.json"):
                f.unlink()
