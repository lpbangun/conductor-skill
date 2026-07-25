# Context-Preserving Long Stages in Herdr

Use this pattern when a Conductor implementation, review, or long evaluation should run without filling the parent chat context.

## Pattern

1. **Write a self-contained stage brief** under the project’s `.hermes/` directory. Include:
   - goal and explicit non-goals;
   - immutable contracts/fixtures;
   - required skills and methods;
   - safety and authority boundaries;
   - exact verification commands;
   - machine-readable and human-readable result artifacts;
   - one unmistakable final completion marker.
2. **Create an unfocused tab in the existing mission workspace**, unless isolation requires a separate workspace. Give it a stage-level label such as `Controller Build`; do not reuse an unrelated pane.
3. **Launch one durable agent in that tab** with the brief preloaded. Keep implementation logs, test output, and iterative debugging in the tab rather than relaying them into the parent conversation.
4. **Verify startup, not just launch acceptance.** Inspect process identity and a small recent output window. A created tab or returned pane ID does not prove the agent reached its task.
5. **Treat the tab's root pane as structural until verified otherwise.** Prefer running the stage directly in the newly created root pane. If `herdr agent start --tab ...` creates an additional pane, do not close the original root merely because it looks empty: on some tab layouts, closing it removes the whole tab and interrupts the agent. Remove a bootstrap pane only after checking the resulting tab topology and proving the execution pane survives independently. Preserve unrelated panes and tabs.
6. **Attach a completion-bound watcher** to the agent process or unique final marker. Prefer one completion notification over repeated polling or streamed logs.
7. **Require durable result artifacts** containing status, verification results, blockers, and next action. A wrapper exit code is transport evidence, not proof of task success.
8. **Verify independently in the parent session** after completion: read the result artifact, inspect changed files, rerun the relevant gates, and validate external side effects before reporting success.
9. **Close the completed stage pane/tab promptly after verification**, preserving Git/filesystem state and unrelated Herdr surfaces.

## Failure handling

- If the agent fails during startup, inspect the clean Herdr shell environment before retrying. Use an absolute launcher path or explicitly prepend the required user-local bin directory in the stage wrapper, then verify the real child process started. Reuse the same dedicated tab when its root pane still exists; do not create a trail of stale tabs.
- Distinguish `agent process exited` from `stage passed`. Missing result artifacts are a failure requiring inspection.
- If parent verification finds a fail-open evaluator or forged/insufficient evidence path, invalidate the prior success artifact before resuming corrections. The resumed implementation tab may fix code and RED regressions, but it must stop at `PENDING_EXTERNAL` for any gate requiring independent review; launch that reviewer in a separate process/session and bind its captured output afterward.
- Reject contradictory artifacts (for example, a report says review is pending while result JSON says it passed) before any rerun or user-facing success claim.
- If the task blocks, keep the report concise and include an exact recovery command or decision request.
- Do not weaken frozen acceptance fixtures from inside the implementation stage. A suspected evaluator defect is reported as a blocker and reviewed separately.

## Parent-chat communication

At launch, report only the workspace/tab/agent identity, scope, and watcher state. During execution, avoid progress chatter unless there is a material blocker requiring user input. On completion, return a concise verified summary and artifact paths.
