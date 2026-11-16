"""Run one agent action for a scientist, printing as it goes.

    python3 run_recheck.py sci_c2bf3f15 [n]

Used before a demo so nothing waits on a model while someone is watching.
"""

import sys

import agentd


def main():
    sid = sys.argv[1] if len(sys.argv) > 1 else "sci_c2bf3f15"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    agent = agentd.Agent(sid)
    for i in range(n):
        nxt = agent.next_action()
        if not nxt:
            print("nothing left to do")
            return
        print(f"\n[{i+1}/{n}] {nxt[0]} — {nxt[2]}", flush=True)
        out = agent.tick(on_progress=lambda m, data=None: print(f"  {str(m)[:150]}", flush=True))
        print(f"  -> {out}", flush=True)


if __name__ == "__main__":
    main()
