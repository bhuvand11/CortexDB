"""
main.py

CortexDB phase 2 entry point. Routes each question through the full
LangGraph pipeline and prints the final answer plus the reasoning trace.

Run from the repo root:
    python agent/main.py "What are total sales by region?"
    python agent/main.py "Why did sales drop in South Storage in July 2016?"
"""

import sys
from agent.audit import init_audit_db
from agent.graph import build_graph


def main():
    if len(sys.argv) < 2:
        print('Usage: python agent/main.py "your question here"')
        sys.exit(1)

    question = sys.argv[1]
    init_audit_db()

    app = build_graph()
    result = app.invoke({"question": question})

    print("\n" + "=" * 60)
    print(f"QUESTION: {question}")
    print(f"ROUTE: {result.get('route')}")
    print("=" * 60)
    print("\nANSWER:\n")
    print(result.get("final_answer", "No answer produced."))
    print("\n" + "=" * 60)
    print("Full trace logged to db/audit.sqlite")


if __name__ == "__main__":
    main()