# Jira Helper

Bulk-manage Jira issues from the terminal. Select a scope (board or project), apply rich filters, then add labels, move issues to a target status, and/or set due dates based on priority—safely with a dry-run mode.

## Features

* **Scope selection**

  * Use a **board’s own filter JQL** or a **project key** as the base set.
* **Rich filters**

  * `status`, `assignee`, `reporter`, `issue-type`, `priority`, `labels`, **created-on (DD-MM-YYYY)**.
* **Bulk actions**

  * **Add label** to all matches.
  * **Move to status** (matches transition by name, case-insensitive).
  * **Set due date** from **priority**:

    * Critical → +7 days
    * High → +15 days
    * Medium → +30 days
    * Low → +90 days
    * (skips Informational/None)
* **Safety**

  * `--dry-run` verifies targets and prints intended operations without writing.

---

## Prerequisites

* **Python** 3.8+
* **pip** and virtualenv (recommended)
* **Jira account** with API token and access to the target projects/boards
* **Permissions** to:

  * Browse issues in the target scope
  * Transition issues (if using `--move-to`)
  * Edit issues (for labels / due dates)

### Python dependencies

* [`jira` (atlassian-python-api)](https://pypi.org/project/jira/)

Install:

```bash
pip install jira
```

---

## Setup

1. **Clone** this repository and `cd` into it.
2. Create a credentials file named **`JiraCredentials.json`** in the repo root:

```json
{
  "email": "your.email@example.com",
  "api_token": "YOUR_JIRA_API_TOKEN",
  "jira_url": "https://your-domain.atlassian.net"
}
```

3. (Optional) Create and activate a **virtual environment**:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install jira
```

---

## Usage

> You must provide **either** `--board-name` **or** `--project`.

### Dry run first (recommended)

Validates the board/project and shows intended actions without making changes.

```bash
python script.py --board-name "AppSec Board" --status "To Do" --labels "security,bug" --dry-run
```

### Common examples

* **Add a label** to all High-priority bugs in a project:

```bash
python script.py --project "Payments" --issue-type "Bug" --priority "High" --add-label "triaged"
```

* **Move issues** to “In Review”:

```bash
python script.py --project "Website" --move-to "In Review"
```

* **Set due dates** for all issues created on a given day:

```bash
python script.py --board-name "Platform Board" --created-on "12-08-2025" --set-due-date
```

* **Combine filters**:

```bash
python script.py \
  --board-name "Engineering Board" \
  --status "In Progress" \
  --assignee "alice@example.com" \
  --labels "backend,security" \
  --add-label "needs-review"
```

### Full flag reference

```text
--board-name "<Board Name>"      Use this board’s filter JQL as the base
--project "<Project Name>"       Use this project (resolved to KEY)
--dry-run                        Print actions without making changes

--add-label "<label>"            Add a label to each matching issue
--move-to "<Status Name>"        Transition each issue to this status (by name)
--set-due-date                   Set due date based on priority mapping

--status "<Status Name>"         Filter by current status
--assignee "<email or name>"     Filter by assignee
--reporter "<email or name>"     Filter by reporter
--issue-type "<type>"            Filter by issue type (e.g., Bug, Task)
--priority "<priority>"          Filter by priority (e.g., High)
--labels "a,b,c"                 Filter: issues with ANY of these labels
--created-on "DD-MM-YYYY"        Filter: created on that calendar day

-h / --help                      Show argparse help
```

---

## How it works (high level)

1. **Authenticate** using `JiraCredentials.json`.
2. **Determine scope**:

   * `--board-name`: fetch board → read its **filter JQL** → use as base JQL.
   * `--project`: resolve project **key** → base JQL `project = KEY ORDER BY Rank ASC`.
3. **Build final JQL** by appending filters (status, assignee, labels, etc.).
4. **Fetch all matching issues** with pagination (100 per page).
5. **Apply actions** in order: add label → move to status → set due dates.
6. **Dry run** prints “Would update / Would move” and **does not** write anything.

**Transitions:** The script enumerates available transitions per issue and matches by **transition name** (case-insensitive), then calls the transition by its ID.

---

## Notes & gotchas

* **Assignee/Reporter matching**: In some Jira Cloud setups, JQL prefers `accountId` rather than email/display name. If matching fails, consider enhancing the script to resolve emails → accountIds.
* **Labels filter** uses `labels IN (...)`, which matches **any** of the listed labels. To require all, chain with `AND` in code.
* **Priority vs Severity**: Due date logic uses **Priority**. If your instance uses a separate **Severity** custom field, adapt the mapping accordingly.
* **Board JQL**: Board filter JQL is pulled from the Agile configuration. This uses a private client session; if Atlassian changes internals, that call may need updating.
* **Time zones**: `--created-on` converts to an inclusive day window `[date, nextDay)`. This avoids off-by-one issues around midnight.

---

## Troubleshooting

* **“Jira authentication failed”**

  * Verify `JiraCredentials.json` fields, your Jira domain, and API token validity.
* **“Board/Project not found”**

  * Check exact names; use `--dry-run` to confirm visibility and access.
* **“No valid transition found …”**

  * Ensure the target status is reachable from each issue’s current status and that your account can transition issues.
* **Labels not updated**

  * Confirm your account has **Edit Issues** permissions for those projects.

---


## Acknowledgements

Built with ❤️ and the excellent `jira` Python library.
