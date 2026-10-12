---
name: creative-tournament
description: Use for open-ended work where many answers are valid — generating ideas, writing stories or poems, designing pages or games, or solving a problem under constraints that rule out the usual approach. Runs three rival builds from different angles and keeps the most original one that meets every requirement.
---

# Creative tournament

1. **Pin the requirements.** Write each hard requirement of the task as one line in `.tournament/requirements.md` (create the folder in the current directory).
2. **Launch three explorers at once.** Start three `creative-tournament:explorer` subagents in parallel, in a single message. Give each the full task text, the requirements file path, its own output folder (`.tournament/a`, `.tournament/b`, `.tournament/c`) and one angle:
   - a: borrow a mechanism from an unrelated field
   - b: invert a premise the task quietly assumes
   - c: add a constraint that forces an unusual shape
   Each explorer writes a complete deliverable, under the task's required file name, inside its own folder.
3. **Select blind.** Start one `creative-tournament:selector` subagent with the task text, the requirements file, and the three folders. It returns the letter of the winner.
4. **Deliver.** Copy the winner's deliverable to the location the task asks for. Check every requirement once more and fix anything broken. Delete `.tournament/`.

If an explorer fails, select among the ones that finished. If all fail, do the task yourself.
