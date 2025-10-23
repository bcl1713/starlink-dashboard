# Rule: Filing a GitHub Issue

## Goal

To guide an AI assistant in creating or updating GitHub issues for this
repository using the `gh` CLI, ensuring no duplicate issues are created and
issues are properly labeled and, if appropriate, linked to a project.

## Process

1. **Receive Issue Details:** The user provides a description of the issue,
   including a title, detailed body, and any suggested labels or urgency.
2. **Try to understand the issue fully:** Look at the code base and try to
   understand the issue. Ask clarifying questions if needed.
3. **Search for Existing Issues:** Before creating a new issue, the AI _must_
   search for existing open issues that might be duplicates. Use
   `gh issue list --search "TITLE_KEYWORDS"`.
4. **Handle Duplicates:**
   - If a highly similar open issue is found, the AI should present the existing
     issue to the user. Ask if the user wants to update or comment on the
     existing issue with the new information. Only proceed if the new
     information adds significant value.
   - If the user confirms, use
     `gh issue comment <ISSUE_NUMBER> --body "Updated information: ..."` or
     `gh issue edit <ISSUE_NUMBER> --body "..."`.
5. **Gather Label Information:**
   - List existing labels using `gh label list` to identify appropriate labels.
   - If a required label does not exist, create it using
     `gh label create <LABEL_NAME> --description "<DESCRIPTION>" --color "<HEX_COLOR>"`.
   - Prioritize labels like 'bug', 'feature', 'enhancement', 'documentation',
     'refactor'.
   - If the issue is critical and requires immediate attention, suggest adding
     the 'hotfix' label.
6. **Gather Project Information (Optional):**
   - List project items for project ID 3 (assuming this is the main project)
     using `gh project item-list 3 --owner bcl1713` to see existing phases.
   - If appropriate, suggest adding the issue to an existing project phase or
     creating a new one if the issue represents a significant new work stream.
7. **Create New Issue (if no duplicate):**
   - Construct the `gh issue create` command with the provided title, body, and
     identified labels.
   - Example:
     `gh issue create --title "Issue Title" --body "Issue description..." --label "bug,backend" --project "Project Name/Phase Name"`
8. **Confirm and Execute:** Present the proposed `gh` command to the user for
   confirmation before execution.

## Output

- Confirmation of issue creation or update, including the issue number and a
  link to the GitHub issue.
- If an existing issue was updated, confirmation of the update.

## Final Instructions

1. Do NOT create or update any issues without user confirmation.
2. Always search for duplicates first.
3. Prioritize using existing labels.
4. Provide the full `gh` command to the user before execution.
