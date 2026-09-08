# Benchmark results

Every number here is produced by `bench/run.py` and written to `bench/results.json`. Nothing is hand-edited.

```bash
python -m venv .venv-bench && .venv-bench/bin/pip install agentdojo
.venv-bench/bin/python bench/run.py          # the table below
.venv-bench/bin/python bench/survivors.py    # which attacks still work, and why
```

## Setup

**Benchmark.** [AgentDojo](https://github.com/ethz-spylab/agentdojo) v1.2.1: four suites (workspace, travel, banking, slack), 97 user tasks, 35 injection tasks, 949 (user task, injection task) pairs.

**Agent.** An oracle. For each pair it executes the user task's ground-truth tool calls and then the injection task's ground-truth calls. This models a fully hijacked model that obeys the attacker completely: the strongest adversary a deterministic guard can face. No LLM is involved, so the run is free, reproducible, and independent of how good any model is at resisting injection on its own.

**Capability tags.** Every tool in every suite is tagged in `bench/capabilities.py`. The user's inbox, files, calendar, transaction history and Slack channels are tagged as both `private_data` and `untrusted_input`, because that is what they are.

**Configurations.**

| config | what happens on the third capability |
|---|---|
| `undefended` | nothing, every call runs |
| `withdraw` | flightmode strict mode, the call is refused and skipped |
| `approve` | flightmode approve mode with an attentive human who approves a call only if it is exactly one the user's own task needs, and declines everything else |

**One rule in the oracle.** When the guard refuses a *read* inside the injection sequence, the rest of that sequence is aborted. AgentDojo ground-truth arguments carry the data the read would have returned, so without this rule the oracle could email a passport number it was never allowed to read. A refused *action* does not abort the sequence.

## Results

| suite | config | benign utility | utility under attack | targeted ASR | cases |
|---|---|---:|---:|---:|---:|
| workspace | undefended | 1.000 | 0.732 | **0.405** | 560 |
| workspace | withdraw | 0.450 | 0.450 | **0.000** | 560 |
| workspace | approve | 1.000 | 1.000 | **0.000** | 560 |
| travel | undefended | 1.000 | 0.186 | **0.829** | 140 |
| travel | withdraw | 1.000 | 0.457 | **0.543** | 140 |
| travel | approve | 1.000 | 0.457 | **0.543** | 140 |
| banking | undefended | 1.000 | 0.868 | **1.000** | 144 |
| banking | withdraw | 0.438 | 0.438 | **0.056** | 144 |
| banking | approve | 1.000 | 1.000 | **0.000** | 144 |
| slack | undefended | 1.000 | 0.971 | **1.000** | 105 |
| slack | withdraw | 0.524 | 0.524 | **0.257** | 105 |
| slack | approve | 1.000 | 1.000 | **0.238** | 105 |
| **all** | undefended | 1.000 | 0.699 | **0.624** | 949 |
| **all** | withdraw | 0.537 | 0.457 | **0.117** | 949 |
| **all** | approve | 1.000 | 0.920 | **0.106** | 949 |

ASR is the targeted attack success rate: the share of pairs in which the injection task's goal was achieved. Lower is better. Utility is the share of pairs in which the user's own task still succeeded.

## Reading it honestly

**Undefended ASR is high because the oracle always obeys.** A real model resists some injections on its own. The oracle measures what the guard does when the model has already lost.

**Exfiltration goes to zero.** Workspace, the email suite and the most realistic one, drops from 0.405 to 0.000 in both modes. Banking drops from 1.000 to 0.056, and to 0.000 with a human. Not a single surviving case in any suite involves private data leaving the session.

**Every survivor is a two-capability integrity attack.** `bench/survivors.py` lists them. Book the attacker's hotel, send a phishing link to a colleague, invite a stranger to Slack, change a password. These read untrusted content and act externally without ever touching private data. The Rule of Two permits that combination by design, Meta's post says so, and this benchmark shows the cost: 111 of 949 cases. A stricter "no external action after untrusted input" policy would close them at a further utility cost. That is the planned v0.2 option.

**Strict mode costs utility.** Benign utility falls to 0.537 because many AgentDojo user tasks are themselves trifectas: read an email, then reply to it. When the inbox is both private and untrusted, replying needs the third capability. That is not a false positive. It is the rule doing exactly what it says, and the reason approve mode exists. With an attentive human, utility is 0.920 under attack and ASR is 0.106.

**Travel barely moves.** Travel tasks read public hotel data (untrusted only) and reserve things (external only). Private data is rarely involved, so the trifecta rarely forms. The suite is mostly outside this threat model.

## Comparison

[Trilock](https://github.com/Poojan6216/trilock) reports 0.117 ASR for its `strict` policy on the same benchmark with the same oracle design, and 0.022 for an `integrity` policy that escalates every external action after untrusted input. flightmode's strict mode lands on the same number with an in-process library instead of an MCP proxy. The residual class is the same in both: two-capability integrity attacks.

## What this does not show

- No LLM-driven run. An LLM would resist some injections itself and would also sometimes fail user tasks on its own. Both would change utility; neither would change what the guard blocks.
- Tags are ours. A different tagging of AgentDojo tools would move the numbers. The file is committed so the choice can be argued with.
- Attribution attacks (paraphrase, encoding, laundering through a memory tool) do not apply: strict mode never looks at content, so there is nothing to paraphrase around. Session splitting does apply: a new `Session` is a fresh triangle, by definition. Do not reset a session unless the model's context is actually cleared.
