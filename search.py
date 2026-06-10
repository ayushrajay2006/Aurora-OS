import os
def search():
    for root, _, files in os.walk('D:/Aurora'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    try:
                        content = file.readlines()
                        for i, line in enumerate(content):
                            if '["tool"]' in line or "['tool']" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '["args"]' in line or "['args']" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '["tool_name"]' in line or "['tool_name']" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '["arguments"]' in line or "['arguments']" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '.get("tool")' in line or ".get('tool')" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '.get("args")' in line or ".get('args')" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '.get("tool_name")' in line or ".get('tool_name')" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                            if '.get("arguments")' in line or ".get('arguments')" in line:
                                print(f"{path}:{i+1}:{line.strip()}")
                    except: pass
search()
