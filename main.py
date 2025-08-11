import argparse
import json
import os
import time
from datetime import datetime, timedelta
from jira import JIRA

CREDENTIALS_FILE = "JiraCredentials.json"

GREEN = "\033[92m"
RESET = "\033[0m"

def print_green(msg):
    print(f"{GREEN}{msg}{RESET}")

def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.")
        exit(1)
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            creds = json.load(f)
            email = creds.get("email")
            token = creds.get("api_token")
            url = creds.get("jira_url")
            if not email or not token or not url:
                raise ValueError("Missing required fields in credentials file.")
            print_green("Credentials fetched successfully.")
            return email, token, url
    except Exception as e:
        print(f"Failed to load credentials: {e}")
        exit(1)

EMAIL, API_TOKEN, JIRA_URL = load_credentials()

parser = argparse.ArgumentParser(description="Manage Jira issues via CLI.")
parser.add_argument("--board-name", help="Jira board name")
parser.add_argument("--project", help="Jira project name")
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--add-label", help="Label to add to issues")
parser.add_argument("--move-to", help="Target status to move issues to")
parser.add_argument("--status", help="Filter by issue status")
parser.add_argument("--assignee", help="Filter by assignee email or name")
parser.add_argument("--reporter", help="Filter by reporter email or name")
parser.add_argument("--issue-type", help="Filter by issue type")
parser.add_argument("--priority", help="Filter by priority")
parser.add_argument("--labels", help="Filter by labels (comma-separated)")
parser.add_argument("--created-on", help="Filter by created date (DD-MM-YYYY)")
parser.add_argument("--set-due-date", action="store_true", help="Set due date based on severity")
args = parser.parse_args()

BOARD_NAME = args.board_name
PROJECT_NAME = args.project
LABEL_TO_ADD = args.add_label
TARGET_STATUS = args.move_to
dry_run = args.dry_run

try:
    jira = JIRA(server=JIRA_URL, basic_auth=(EMAIL, API_TOKEN))
    print_green("Jira authentication successful.")
except Exception as e:
    print(f"Jira authentication failed: {e}")
    exit(1)

def show_dots(message):
    print(message, end="", flush=True)
    for _ in range(3):
        time.sleep(0.4)
        print(".", end="", flush=True)
    print()

def get_board_id_by_name(name):
    start_at = 0
    while True:
        boards = jira.boards(startAt=start_at)
        if not boards:
            break
        for board in boards:
            if board.name == name:
                return board.id
        start_at += len(boards)
    return None

def get_project_key_by_name(name):
    projects = jira.projects()
    for project in projects:
        if project.name.lower() == name.lower():
            return project.key
    return None

def get_jql_from_board(board_id):
    config = jira._session.get(f"{JIRA_URL}/rest/agile/1.0/board/{board_id}/configuration").json()
    filter_id = config["filter"]["id"]
    board_filter = jira.filter(filter_id)
    return board_filter.jql

def build_jql(base_jql, status=None, assignee=None, reporter=None, issue_type=None, priority=None, labels=None, created_on=None):
    filters = []
    if status:
        filters.append(f'status = "{status}"')
    if assignee:
        filters.append(f'assignee = "{assignee}"')
    if reporter:
        filters.append(f'reporter = "{reporter}"')
    if issue_type:
        filters.append(f'issuetype = "{issue_type}"')
    if priority:
        filters.append(f'priority = "{priority}"')
    if labels:
        label_list = ', '.join(f'"{label.strip()}"' for label in labels.split(','))
        filters.append(f'labels IN ({label_list})')
    if created_on:
        date_obj = datetime.strptime(created_on, "%d-%m-%Y")
        date_str = date_obj.strftime("%Y-%m-%d")
        next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        filters.append(f'created >= "{date_str}" AND created < "{next_day}"')
    return base_jql + " AND " + " AND ".join(filters) if filters else base_jql

def get_all_issues(jql):
    all_issues = []
    start_at = 0
    max_results = 100

    while True:
        issues = jira.search_issues(jql, startAt=start_at, maxResults=max_results)
        if not issues:
            break
        all_issues.extend(issues)
        if len(issues) < max_results:
            break
        start_at += max_results

    return all_issues

def add_label_to_issues(issues, label):
    for issue in issues:
        key = issue.key
        labels = issue.fields.labels
        if label not in labels:
            print(f"Would update {key} with label '{label}'" if dry_run else f"Updating {key} with label '{label}'")
            if not dry_run:
                updated = labels + [label]
                jira.issue(key).update(fields={"labels": updated})
                print_green(f"Updated {key} with label '{label}'")
        else:
            print(f"{key} already has label '{label}'")

def move_issues_to_status(issues, target_status):
    for issue in issues:
        key = issue.key
        current_status = issue.fields.status.name

        if current_status.lower() == target_status.lower():
            print(f"{key} already in status '{target_status}'")
            continue

        transitions = jira.transitions(key)
        matched = next((t for t in transitions if t['name'].lower() == target_status.lower()), None)

        if not matched:
            print(f"No valid transition found for {key} → '{target_status}'")
            continue

        print(f"Would move {key} to '{target_status}'" if dry_run else f"Moving {key} to '{target_status}'")
        if not dry_run:
            jira.transition_issue(key, matched["id"])
            print_green(f"Moved {key} to '{target_status}'")

def set_due_dates_based_on_severity(issues):
    for issue in issues:
        key = issue.key
        fields = issue.fields
        severity = fields.priority.name.lower() if fields.priority else None

        if severity in ["informational", None]:
            continue

        days_to_add = {
            "critical": 7,
            "high": 15,
            "medium": 30,
            "low": 90
        }.get(severity, None)

        if not days_to_add:
            continue

        created_date = datetime.strptime(fields.created[:10], "%Y-%m-%d")
        due_date = created_date + timedelta(days=days_to_add)
        due_str = due_date.strftime("%d-%m-%Y")

        print(f"Setting due date for {key} to {due_str}")
        if not dry_run:
            jira.issue(key).update(fields={"duedate": due_date.strftime("%Y-%m-%d")})
            print_green(f"Due date set for {key}")

# === Execution ===
if dry_run:
    if BOARD_NAME:
        show_dots(f"Looking for board: {BOARD_NAME}")
        board_id = get_board_id_by_name(BOARD_NAME)
        if board_id:
            print_green(f"Board '{BOARD_NAME}' exists.")
        else:
            print(f"Board '{BOARD_NAME}' not found.")
            exit(1)
    elif PROJECT_NAME:
        show_dots(f"Looking for project: {PROJECT_NAME}")
        project_key = get_project_key_by_name(PROJECT_NAME)
        if project_key:
            print_green(f"Project '{PROJECT_NAME}' exists.")
        else:
            print(f"Project '{PROJECT_NAME}' not found.")
            exit(1)
    exit(0)

if not BOARD_NAME and not PROJECT_NAME:
    print("Either --board-name or --project must be provided.")
    exit(1)

if BOARD_NAME:
    show_dots(f"Looking for board: {BOARD_NAME}")
    board_id = get_board_id_by_name(BOARD_NAME)
    if not board_id:
        print(f"Board '{BOARD_NAME}' not found.")
        exit(1)
    base_jql = get_jql_from_board(board_id)
else:
    show_dots(f"Looking for project: {PROJECT_NAME}")
    project_key = get_project_key_by_name(PROJECT_NAME)
    if not project_key:
        print(f"Project '{PROJECT_NAME}' not found.")
        exit(1)
    base_jql = f"project = {project_key} ORDER BY Rank ASC"

final_jql = build_jql(base_jql, args.status, args.assignee, args.reporter, args.issue_type, args.priority, args.labels, args.created_on)
print(f"JQL: {final_jql}")

issues = get_all_issues(final_jql)
print(f"Total issues matching filters: {len(issues)}")
if len(issues) == 0:
    print_green("No issues found matching the filters. Script completed.")
    exit(0)

if LABEL_TO_ADD:
    show_dots(f"Adding label '{LABEL_TO_ADD}'")
    add_label_to_issues(issues, LABEL_TO_ADD)

if TARGET_STATUS:
    print(f"Moving issues to status '{TARGET_STATUS}'")
    move_issues_to_status(issues, TARGET_STATUS)

if args.set_due_date:
    print("Setting due dates based on severity...")
    set_due_dates_based_on_severity(issues)

print_green("Script completed.")
