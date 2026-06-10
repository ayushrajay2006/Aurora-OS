from brain.planner import planner

queries = [
    "open notepad type hello world press enter",
    "open edge switch to edge type batman trailer press enter",
    "open vscode type hello world",
    "open discord switch to discord type hello",
    "open edge close edge switch to edge"
]

print("=== PLANNER RULE VERIFICATION ===")
for q in queries:
    print(f"\n[QUERY]: {q}")
    reply, actions = planner.create_plan(q, [])
    print(f"[REPLY]: {reply}")
    for idx, act in enumerate(actions, 1):
        print(f"  {idx}. {act.get('tool_name') or act.get('tool')} ({act.get('arguments') or act.get('args')})")
    print("-" * 50)
