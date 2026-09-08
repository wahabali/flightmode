"""
AgentDojo oracle benchmark for flightmode.

The agent is an oracle: for each (user task, injection task) pair it executes the
user task's ground-truth calls and then the injection task's ground-truth calls.
That is a fully hijacked model, the strongest adversary a deterministic guard
can face. No LLM, no API key, fully reproducible.

Configurations:
  undefended   every call runs
  withdraw     flightmode strict mode, refused calls are skipped
  approve      flightmode approve mode with an attentive human who approves calls
               belonging to the task they asked for and declines the attacker's

Metrics per suite:
  benign utility        user task succeeds with no injection
  utility under attack  user task succeeds while the injection is also attempted
  targeted ASR          injection task succeeds (attack success rate)

    .venv-bench/bin/python bench/run.py            # writes bench/results.json and prints the table
"""
import json
import sys
import time
from pathlib import Path

from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suites

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flightmode import Guard, Mode, Session, Capability  # noqa: E402
from bench.capabilities import SUITES  # noqa: E402

VERSION = "v1.2.1"
CONFIGS = ["undefended", "withdraw", "approve"]


def _key(call):
    return (call.function, json.dumps(call.args, sort_keys=True, default=str))


def make_guard(config: str, tags: dict, user_calls, ctx: dict):
    if config == "undefended":
        return None
    if config == "withdraw":
        g = Guard(session=Session(), mode=Mode.WITHDRAW)
    else:
        # attentive human: approves a call only if it is exactly one the user's own task needs
        wanted = {_key(c) for c in user_calls}
        g = Guard(session=Session(), mode=Mode.APPROVE, approver=lambda d: _key(ctx["call"]) in wanted)
    for name, caps in tags.items():
        g.register(name, *caps)
    return g


READS = {Capability.UNTRUSTED_INPUT, Capability.PRIVATE_DATA}


def execute(runtime, env, calls, guard, trace, ctx, dependent=False):
    """
    Run ground-truth calls through the guard. Refused calls are skipped.

    With dependent=True (the injection sequence), a refused read aborts the rest
    of the sequence. Ground-truth args carry the data the read would have
    returned, so without this rule the oracle could send data it never obtained.
    A refused action does not abort: later calls may be independent of it.
    """
    for call in calls:
        if guard is not None:
            ctx["call"] = call
            decision = guard.check(call.function)
            if not decision.allowed:
                trace.append((call.function, "refused"))
                spec = guard.spec(call.function)
                if dependent and spec and (spec.capabilities & READS):
                    trace.append(("<sequence aborted: refused read>", "aborted"))
                    break
                continue
        _, err = runtime.run_function(env, call.function, call.args)
        if err is None and guard is not None:
            spec = guard.spec(call.function)
            if spec and spec.capabilities:
                guard.session.mark(*spec.capabilities)
        trace.append((call.function, "ok" if err is None else f"error {err[:40]}"))


def run_pair(suite, tags, user_task, injection_task, config):
    injections = suite.get_injection_vector_defaults()
    env = suite.load_and_inject_default_environment(injections)
    env = user_task.init_environment(env)
    pre = env.model_copy(deep=True)
    runtime = FunctionsRuntime(suite.tools)

    user_calls = user_task.ground_truth(pre)
    ctx = {}
    guard = make_guard(config, tags, user_calls, ctx)
    trace = []
    execute(runtime, env, user_calls, guard, trace, ctx)
    if injection_task is not None:
        execute(runtime, env, injection_task.ground_truth(pre), guard, trace, ctx, dependent=True)

    output = user_task.GROUND_TRUTH_OUTPUT if hasattr(user_task, "GROUND_TRUTH_OUTPUT") else ""
    executed = [c for c, s in trace if s == "ok"]
    utility = _utility(user_task, output, pre, env, executed, runtime)
    if injection_task is None:
        return utility, False
    security = _security(injection_task, pre, env, executed, runtime)
    return utility, security


def _utility(task, output, pre, post, executed_names, runtime):
    # Prefer the trace-based check when the task defines one; fall back to state diff.
    traces = [c for c in task.ground_truth(pre) if c.function in executed_names]
    from_traces = task.utility_from_traces(output, pre, post, traces)
    if from_traces is not None:
        return bool(from_traces)
    try:
        return bool(task.utility(output, pre, post, strict=False))
    except TypeError:
        return bool(task.utility(output, pre, post))


def _security(task, pre, post, executed_names, runtime):
    traces = [c for c in task.ground_truth(pre) if c.function in executed_names]
    from_traces = task.security_from_traces("", pre, post, traces)
    if from_traces is not None:
        return bool(from_traces)
    return bool(task.security("", pre, post))


def run_suite(name, suite, tags):
    rows = {}
    for config in CONFIGS:
        benign = []
        under_attack = []
        asr = []
        for ut in suite.user_tasks.values():
            u, _ = run_pair(suite, tags, ut, None, config)
            benign.append(u)
            for it in suite.injection_tasks.values():
                u, s = run_pair(suite, tags, ut, it, config)
                under_attack.append(u)
                asr.append(s)
        rows[config] = {
            "benign_utility": sum(benign) / len(benign),
            "utility_under_attack": sum(under_attack) / len(under_attack),
            "targeted_asr": sum(asr) / len(asr),
            "user_tasks": len(suite.user_tasks),
            "injection_tasks": len(suite.injection_tasks),
            "cases": len(asr),
        }
    return rows


def main():
    suites = get_suites(VERSION)
    results = {"agentdojo": VERSION, "agent": "oracle", "suites": {}}
    t0 = time.time()
    for name, suite in suites.items():
        results["suites"][name] = run_suite(name, suite, SUITES[name])
        print(f"{name} done", file=sys.stderr)
    # aggregate across suites weighted by case count
    agg = {}
    for config in CONFIGS:
        tot = sum(r[config]["cases"] for r in results["suites"].values())
        agg[config] = {
            k: sum(r[config][k] * r[config]["cases"] for r in results["suites"].values()) / tot
            for k in ("benign_utility", "utility_under_attack", "targeted_asr")
        }
        agg[config]["cases"] = tot
    results["all"] = agg
    results["seconds"] = round(time.time() - t0, 1)

    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(results, indent=2))
    print_table(results)
    print(f"\nwritten to {out}")


def print_table(results):
    print("\n| suite | config | benign utility | utility under attack | targeted ASR | cases |")
    print("|---|---|---:|---:|---:|---:|")
    for name, rows in list(results["suites"].items()) + [("**all**", results["all"])]:
        for config, r in rows.items():
            print(f"| {name} | {config} | {r['benign_utility']:.3f} | {r['utility_under_attack']:.3f} | "
                  f"**{r['targeted_asr']:.3f}** | {r['cases']} |")


if __name__ == "__main__":
    main()
