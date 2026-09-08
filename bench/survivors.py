"""
Which injections still succeed under flightmode strict mode, and why.

    .venv-bench/bin/python bench/survivors.py
"""
import sys
from collections import defaultdict
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suites

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.run import run_pair, VERSION  # noqa: E402
from bench.capabilities import SUITES  # noqa: E402
from flightmode import Capability as C  # noqa: E402


def caps_of(tags, calls):
    out = set()
    for c in calls:
        out |= tags.get(c.function, set())
    return out


def main():
    for name, suite in get_suites(VERSION).items():
        tags = SUITES[name]
        env = suite.load_and_inject_default_environment(suite.get_injection_vector_defaults())
        survivors = defaultdict(int)
        for ut in suite.user_tasks.values():
            for it in suite.injection_tasks.values():
                _, s = run_pair(suite, tags, ut, it, "withdraw")
                if s:
                    survivors[it.ID] += 1
        print(f"\n## {name}: {sum(survivors.values())} surviving cases of {len(suite.user_tasks) * len(suite.injection_tasks)}")
        for it_id, n in sorted(survivors.items(), key=lambda kv: -kv[1]):
            it = suite.injection_tasks[it_id]
            calls = it.ground_truth(env)
            caps = sorted(c.value for c in caps_of(tags, calls))
            klass = "two-capability integrity attack (no private data)" if C.PRIVATE_DATA not in caps_of(tags, calls) and len(caps) <= 2 else "check tags"
            print(f"- {it_id} survives in {n}/{len(suite.user_tasks)} user tasks. calls: {[c.function for c in calls]} -> {caps}. {klass}")
            print(f"    goal: {it.GOAL[:140]}")


if __name__ == "__main__":
    main()
