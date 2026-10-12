#!/bin/sh
# Inject the procedure itself at session start: an installed skill alone is often never invoked.
echo "The creative-tournament plugin is installed. For any open-ended task in this session (generating ideas, writing, designing a page or game, or solving a problem under constraints that rule out the usual approach), you must follow the procedure below before producing the deliverable, even if the task looks simple."
echo
sed '1,/^---$/{/^---$/!d;};1,/^---$/d' "${CLAUDE_PLUGIN_ROOT}/skills/creative-tournament/SKILL.md"
