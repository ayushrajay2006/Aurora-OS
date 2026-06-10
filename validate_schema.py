import sys, os
sys.path.insert(0, '.')
os.chdir('D:/Aurora')
from brain.planner import planner

test_cases = [
    'open steam',
    'close steam',
    'open vscode',
    'open god of war',
    'open college stuff folder'
]

print('=' * 60)
for case in test_cases:
    print(f'\nTEST: {case}')
    # We will simulate the LLM returning the new schema Format A
    if 'open ' in case and 'folder' not in case:
        app = case.replace('open ', '')
        mock_response = f'```json\n[{{\"tool_name\": \"open_app\", \"arguments\": {{\"app_name\": \"{app}\"}}}}]```'
    elif 'folder' in case:
        mock_response = f'```json\n[{{\"tool_name\": \"open_folder\", \"arguments\": {{\"path\": \"college stuff folder\"}}}}]```'
    elif 'close' in case:
        app = case.replace('close ', '')
        mock_response = f'```json\n[{{\"tool_name\": \"close_app\", \"arguments\": {{\"app_name\": \"{app}\"}}}}]```'
    else:
        mock_response = '```json\n[{"tool_name": "unknown"}]\n```'
        
    _, actions = planner.parse_response(mock_response)
    
    for idx, act in enumerate(actions, 1):
        tool_name = act.get('tool_name') or act.get('tool')
        args = act.get('arguments') or act.get('args') or {}
        
        if not tool_name:
            print(f'     [!] Invalid schema: Action missing tool name. Action object: {act}')
            continue
            
        print(f'[SCHEMA]')
        print(f'Received Action: {act}')
        print(f'Resolved Tool: {tool_name}')
        print(f'Resolved Arguments: {args}')
print('=' * 60)
