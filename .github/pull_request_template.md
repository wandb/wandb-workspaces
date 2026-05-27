<!--
Ensure PR title compliance with the [conventional commits standards](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#conventional-commits)
-->
Please use conventional commits in your PR title. If you are unsure what conventional commits are or how to use them, please check out [conventional commits standards](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#conventional-commits).

JIRA/GH Issues(s)
-----------
Paste links to relevant JIRA/GH issues here, one per line e.g.
- Fixes WB-NNNNN
- Fixes #NNNN

Description
-----------
<!--
Include reference to internal ticket "Fixes WB-NNNNN" and/or GitHub issue "Fixes #NNNN" (if applicable)
-->
_What does this PR do? Write a short paragraph to contextualize and explain your change._

Testing
-------
How was this PR tested?

- [ ] _Added unit tests_
- [ ] _Manual testing (include description)_
- [ ] _N/A (include explanation)_

Server compatibility
--------------------
<!--
If this PR relies on backend or UI behavior that only exists in some
W&B Server releases, apply the matching label from the Labels sidebar:

  - `requires-server/X.Y+`     — minimum tagged server release needed
  - `requires-server/unreleased` — works on SaaS today but not yet in any
                                   tagged server release; on-prem users
                                   should wait for a future server.

Leave unchecked if the change is pure SDK / works on all supported servers.
-->

- [ ] _Requires a minimum W&B Server version (label `requires-server/X.Y+` applied)_
- [ ] _SaaS only — not yet in any tagged W&B Server release (label `requires-server/unreleased` applied)_
- [ ] _N/A — works on all currently supported servers_

