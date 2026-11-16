"""End-to-end test of the path a new user takes, over real HTTP."""
import json, time, urllib.request

BASE = "http://localhost:8811"

def call(path, body=None, token=""):
    req = urllib.request.Request(BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "X-Token": token},
        method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def wait(job, token="", label=""):
    t0 = time.time()
    while True:
        j = call(f"/api/job?id={job}", token=token)
        if j["status"] == "done":
            print(f"  [{label}] {time.time()-t0:.0f}s"); return j["result"]
        if j["status"] == "error":
            raise SystemExit(f"  [{label}] FAILED: {j['error']}")
        time.sleep(1.5)

print("1. onboarding a new scientist")
r = wait(call("/api/onboard", {"text":
    "I'm a postdoc in environmental microbiology. I do anaerobic culturing of sediment "
    "communities, 16S amplicon sequencing and metagenome assembly. We have an anaerobic "
    "chamber, a MinION and access to a shared Illumina core. I can help people culture "
    "fastidious anaerobes and interpret community sequencing data."})["job"], label="onboard")
tok = r["token"]; me = r["scientist"]
print(f"   {me['name']} · {me['field']}")
print(f"   techniques: {me['techniques'][:3]}")

print("2. interview")
tr = [{"role": "scientist", "text":
    "We tried to enrich a sulfate-reducing organism from estuary sediment that shows up at "
    "about 8% in our 16S data. Twelve weeks of anaerobic enrichment on lactate plus sulfate, "
    "nothing grew above background. The 16S signal is reproducible across three sediment cores."}]
for i in range(4):
    q = wait(call("/api/interview/next", {"transcript": tr}, token=tok)["job"], tok, f"q{i+1}")
    if q.get("done"):
        print(f"   agent stopped after {i} questions: {q.get('why')}"); break
    print(f"   Q: {q['question'][:110]}")
    tr.append({"role": "agent", "text": q["question"]})
    tr.append({"role": "scientist", "text": "I don't know — we never checked that."})

print("3. building the problem card")
pr = wait(call("/api/problem/create", {"transcript": tr, "paste": tr[0]["text"]}, token=tok)["job"], tok, "card")
card = pr["problem"]["card"]
print(f"   title: {card['title'][:100]}")
print(f"   type: {card.get('result_type')} | flags: {len(card.get('quality_flags') or [])}")

print("4. letting the agent work (scout + broadcast + network responds)")
res = wait(call("/api/tick", {"mine_only": True, "rounds": 3}, token=tok)["job"], tok, "agent")
from collections import Counter
print(f"   {len(res)} actions: {dict(Counter(a['action'] for a in res))}")

inbox = call("/api/inbox", token=tok)["events"]
print(f"5. inbox has {len(inbox)} items")
for e in inbox[:6]:
    print(f"   [{e['kind']}] {e['title'][:85]}")
