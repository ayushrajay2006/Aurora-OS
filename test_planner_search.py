from brain.planner import planner

queries = [
    "search ironman fanbase edit on youtube",
    "search python tutorials on youtube",
    "search best rust libraries on github"
]

print("=== PLANNER RULE 16 VERIFICATION ===")
for q in queries:
    print(f"\n[QUERY]: {q}")
    reply, actions = planner.create_plan(q, [])
    print(f"[REPLY]: {reply}")
    for idx, act in enumerate(actions, 1):
        print(f"  {idx}. {act.get('tool_name') or act.get('tool')} ({act.get('arguments') or act.get('args')})")
    print("-" * 50)
