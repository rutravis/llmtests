"""Test 8 — MCP Tool Usage

Evaluate the model's ability to construct correct tool calls for the onebrain
memory MCP server. Tests cover: search queries, create/update/delete workflows,
chained multi-step operations, and error handling (duplicates, NotFound).
"""

import textwrap
from .conftest import TestCase, TestResult, run_suite


TEST_CASES: list[TestCase] = [
    # -----------------------------------------------------------------------
    # 1. Memory search — construct a precise hybrid query with filters
    # -----------------------------------------------------------------------
    TestCase(
        name="mcp_memory_search",
        description=(
            "Construct a correct memory_search tool call to find memories about "
            "a specific topic, using appropriate filters."
        ),
        prompt=textwrap.dedent("""\
            You have access to the onebrain MCP server with these tools:

            **memory_search** — Hybrid retrieval over ACTIVE memories.
            Args: query (required), types (array of note/fact/decision/preference/task/context),
                  scopes (array of global/project), tags (string array), project (single label),
                  date_from/date_to (ISO-8601), limit (default 5).

            **memory_list** — Browse memories newest-first.
            Args: cursor, limit (default 20), type (singular), scope, status, project.

            **memory_get** — Fetch one memory by uid.
            Args: uid (required string).

            **memory_remember** — Create a memory.
            Args: title, body, type (note/fact/decision/preference/task/context),
                  tags (array), scope (global/project), project (label for project scope),
                  confidence (0-1), expires_at (ISO-8601).

            **memory_update** — Modify a memory by uid.
            Args: uid, title/body/tags/confidence/pinned/expires_at/status/scope/project/type.

            **memory_delete** — Permanently delete a memory by uid.
            Args: uid, reason (optional string).

            **memory_stats** — Operational snapshot. No args.

            Task: Write the exact JSON argument object you would send to `memory_search`
            to find all "fact" and "decision" type memories tagged with "llmtests" from
            September 2026, limited to 10 results. Include only the arguments JSON — no
            prose explanation.

            Requirements:
            - Use correct field names (not camelCase or snake_case variants)
            - types must be an array of strings
            - tags must be an array of strings
            - date_from and date_to must be valid ISO-8601 dates
            - limit must be a number
        """),
        expected_keywords=[
            "memory_search", "query", "types", "tags", "date_from", "date_to",
            "limit", "llmtests", "fact", "decision", "[", "]", "{", "}",
        ],
        min_length=100,
    ),

    # -----------------------------------------------------------------------
    # 2. Create → Update → Archive lifecycle
    # -----------------------------------------------------------------------
    TestCase(
        name="mcp_memory_lifecycle",
        description=(
            "Construct a correct sequence of tool calls to create a memory, update it, "
            "then archive it."
        ),
        prompt=textwrap.dedent("""\
            You have access to the onebrain MCP server. Each tool call is a separate JSON
            object written to the appropriate device path (e.g., xd://mcp__onebrain_memory_remember).

            Task: Write three sequential tool calls for this workflow:

            1. Create a memory with title "LLM Test Suite Results", body describing that
               nail-qwen3.6-35b-a3b-mtp scored 20/20 on the llmtests battery, type="fact",
               tags=["llmtests","results"], scope="project", project="llmtests", confidence=0.95.

            2. Update that memory (use a placeholder uid "PLACEHOLDER_UID") to add tag
               "verified" and change confidence to 1.0, pinned=true. Note: pinned clears expires_at.

            3. Archive the same memory (uid "PLACEHOLDER_UID") by setting status="archived".

            For each step, write ONLY the JSON arguments object for that tool call. Do not
            include any prose or explanation between them. Format as three separate JSON blocks.

            Requirements:
            - Step 1 uses memory_remember with title/body/type/tags/scope/project/confidence
            - Step 2 uses memory_update with uid, tags (add "verified"), confidence=1.0, pinned=true
            - Step 3 uses memory_update with uid and status="archived"
            - All field names must match the schema exactly
        """),
        expected_keywords=[
            "memory_remember", "title", "body", "type", "tags", "scope", "project",
            "confidence", "memory_update", "uid", "pinned", "status", "archived",
            "llmtests", "nail-qwen3.6-35b-a3b-mtp", "verified", "{", "}", "[", "]",
        ],
        min_length=200,
    ),

    # -----------------------------------------------------------------------
    # 3. Chained workflow — search → get → update with error handling
    # -----------------------------------------------------------------------
    TestCase(
        name="mcp_chained_workflow",
        description=(
            "Construct a multi-step chained workflow: search for memories, retrieve one by UID, "
            "then update it, including error-handling branches."
        ),
        prompt=textwrap.dedent("""\
            You have access to the onebrain MCP server. Write a complete Python script that
            performs this chained workflow using subprocess calls to write JSON to device paths:

            Workflow:
            1. Call memory_stats to get operational snapshot (no args).
            2. Call memory_search with query="llm evaluation", types=["fact","decision"], limit=5.
            3. If search returns hits, call memory_get on the first hit's uid.
            4. Update that memory: add tag "reviewed", set confidence to 0.8.
            5. Handle errors: if memory_get returns NotFound, skip update and log error.

            Write the Python script with proper JSON construction for each tool call. Use
            subprocess.run or write to device paths. Include try/except blocks around each
            step. The script should be executable Python code in a fenced block.

            Requirements:
            - Correct field names in all JSON objects (query, types, limit, uid, tags, confidence)
            - Proper error handling for NotFound and other errors
            - At least one try/except block
            - memory_stats called with empty args {}
            - memory_search uses plural "types" not singular "type"
        """),
        expected_keywords=[
            "memory_stats", "memory_search", "memory_get", "memory_update", "query",
            "types", "limit", "uid", "tags", "confidence", "try", "except",
            "NotFound", "llm evaluation", "{", "}", "[", "]", "subprocess",
        ],
        min_length=400,
        requires_correct_code=True,
    ),
]


def run_tests(client, model_name: str) -> list[TestResult]:
    """Execute all MCP tool usage test cases."""
    return run_suite(
        client, model_name, TEST_CASES,
        system_prompt=(
            "You are an expert at using the onebrain memory MCP server. "
            "Construct precise JSON arguments for each tool call. Follow schemas exactly."
        ),
        temperature=0.1,
    )


def test_mcp_tools(client, model_name: str):
    """Run the full MCP tools battery and assert minimum pass rate."""
    results = run_tests(client, model_name)
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n=== MCP Tools Tests ===")
    for r in results:
        print(f"  {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")

    assert passed >= total * 0.6, f"Only {passed}/{total} MCP tool tests passed (need ≥60%)"


if __name__ == "__main__":
    from .conftest import get_client
    client, model = get_client()
    results = run_tests(client, model)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.score:.2%})")
        for d in r.details:
            print(f"       {d}")
