# Episode 13 shadow-run playbook

## Start once, from a frozen system

1. Record the exact Git commit or PRE13 tag as `system_version`.
2. Initialize the run pack with
   `scripts/evaluation/init_episode_run.py` from this Skill.
3. Create the episode state from the approved Episode 13 plan. Do not preload
   imagined pressure changes; later changes must enter through normal commands.
4. Register stable Agent identities, roles and capabilities. Keep author and
   independent-review authority separate.
5. Start the Human UI as a disposable projection. A UI close, crash or restart
   must not mutate the backend. Reopening resumes from the backend cursor.

The production objective outranks the evaluation objective. Do not inject
destructive faults into real Episode 13 work.

## Normal Main Agent loop

1. Call `next` and follow the one returned action.
2. If the action is unclear, use targeted `explain`; do not load the full graph
   or service source.
3. For `work`, call `begin` and give the worker only its returned capsule plus
   the domain Skill named by that task.
4. Record token deltas and evidence-bearing progress through `heartbeat`.
5. Submit content-addressed artifacts, run deterministic gates, and assign an
   independent reviewer.
6. Stop at a Human gate. The Human may act in the UI or authorize the Main Agent
   to issue the equivalent backend command.
7. Resume with `next`; do not infer completion from a successful command.

The user can still ask “进度怎么样”“有可审片吗”“把 T040 打回”. Answer from the
same backend state and perform authorized changes through the public Agent
interface. Do not operate the webpage with debug-style clicks merely to imitate
the Human UI.

For a state-changing natural-language instruction such as “时间不够了，增加并行”:

1. The Main Agent/coordinator performs the one semantic judgment; no hidden
   monitor silently changes capacity.
2. Record an `observe` event with category `human_intent_routing`, a concise
   faithful summary, intended system effect, and the request IDs of the commands
   chosen. Do not copy unrelated conversation.
3. Issue the auditable budget/dispatch commands. The deterministic backend then
   calculates capacity, validates compatibility and enforces reservations.
4. Record whether the intended effect occurred and the time to the first added
   live lease. A later evaluator judges the intent-to-command mapping.

## Human feedback delivery

- A submitted annotation is immediately durable and visible to the Main Agent
  through state/events.
- If its producer is working and the premise remains valid, deliver it at the
  next heartbeat attention boundary without revoking the live lease.
- If it invalidates the task premise or the Human explicitly reopens an approved
  result, use the recorded change/revision route and let the backend determine
  the affected descendants.
- The next author and independent reviewer must receive the exact annotation or
  Human conflict resolution in their scoped capsules. The frozen capsule log is
  the verification evidence; a chat summary is not.

## Parallel pressure

When the user says time is short or the ready frontier expands:

1. Read `next` dispatch usage and scaling advice.
2. Bring enough compatible author Agents online within the configured policy.
3. Use `dispatch-reserve` with one `TASK=AGENT` assignment per ready task.
4. Let each assigned Agent call `begin` with its stable identity.
5. Verify overlapping active leases and preserve independent reviewer capacity.

Do not create artificial work, duplicate completed tasks or weaken quality and
Human gates merely to make all Agents appear busy.

## Freeze and handoff

At closeout:

1. Export state into the run pack's `frozen-evidence/` directory.
2. Fill the instrumentation paths, evidence index, observations and
   retrospective. Generate no false zeroes for absent telemetry.
3. Set the final user authority state explicitly; machine PASS is insufficient.
4. Set `evaluation-handoff.json` to `evaluation_ready` and run
   `check_run_pack.py <run-dir> --ready`.
5. Do not modify state-supervision source in this production Session. Hand the
   frozen pack to a later evaluation Session for diagnosis and regressions.
