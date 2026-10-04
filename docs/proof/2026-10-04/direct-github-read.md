# Direct GitHub comparison

Recorded before reading the Standup MCP result, using `gh api graphql` and
`gh issue/pr view` on public `trekhleb` repositories. This is one operator's
comparison, not a controlled benchmark or the repository owner's priorities.

The aggregate snapshot is retained in `github-baseline.json`. It uses the same
bounded repository query as Standup so the first comparison has the same input
coverage. Direct CLI reads then add the bodies and discussion of selected items.

My first three candidates:

1. Review the two concrete correctness fixes in `javascript-algorithms`:
   [PR 2220](https://github.com/trekhleb/javascript-algorithms/pull/2220)
   (inserting at the end loses the inserted node on a subsequent append) and
   [PR 2219](https://github.com/trekhleb/javascript-algorithms/pull/2219)
   (an interpolation search can loop forever). Both were submitted by
   `Darkslayer3324j`; neither had comments or reviews in this read. Their bodies
   provide reproductions and claimed tests. Review those claims before merging;
   the read itself does not establish that either patch is correct.
2. Ask for the smallest reproduction and exit logs on
   [`claude-pod` issue 1](https://github.com/trekhleb/claude-pod/issues/1).
   `ryanpeach` reports an immediate exit and does not know how to obtain logs.
   There are no comments. A short diagnostic response can unblock the next step;
   the issue's age does not prove the user is still waiting.
3. Review the small documentation correction
   [`javascript-algorithms` PR 2188](https://github.com/trekhleb/javascript-algorithms/pull/2188)
   by `chenlichao`. Its title makes it a candidate for a short review; the diff
   has not been reviewed here, so no merge recommendation follows.

The unaddressed resource proposal in `trekhleb.github.io` issue 103 and the
directory submission in `promote-your-next-startup` PR 23 are real, but the
correctness reports and blocked user are stronger first candidates. This is an
explicit prioritisation judgment, not a claim about the owner's preferences.

Important limits: the aggregate query samples oldest/newest open threads and
only the most recently pushed active repositories. Last update is not creation
date or verified waiting time. Green default-branch CI does not prove a PR is
safe to merge. Open threads alone do not prove whose action is needed. Bot PRs
may matter operationally but should not be described as people waiting.
