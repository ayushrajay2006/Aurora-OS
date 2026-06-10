import sys, os, time
sys.path.insert(0, '.')
os.chdir('D:/Aurora')

from brain.app_resolver import app_resolver
from tools.open_app import OpenAppTool
from tools.close_app import CloseAppTool
from tools.open_folder import OpenFolderTool

sep = '=' * 60

# --- TEST 1: open steam ---
print(sep)
print('TEST 1: open steam')
r = app_resolver.resolve_app('steam')
print('  [Resolver] steam ->', r)
result = OpenAppTool().execute('steam')
print('  [open_app] success=' + str(result['success']) + ' | ' + result['output'])

time.sleep(4)

# --- TEST 2: close steam ---
print()
print('TEST 2: close steam')
result = CloseAppTool().execute('steam')
print('  [close_app] success=' + str(result['success']) + ' | ' + result['output'])

# --- TEST 3: open vscode ---
print()
print('TEST 3: open vscode')
r = app_resolver.resolve_app('vscode')
print('  [Resolver] vscode ->', r)
result = OpenAppTool().execute('vscode')
print('  [open_app] success=' + str(result['success']) + ' | ' + result['output'])

# --- TEST 4: open god of war ---
print()
print('TEST 4: open god of war (resolver only)')
r = app_resolver.resolve_app('god of war')
print('  [Resolver] god of war ->', r)

# --- TEST 5: open palworld ---
print()
print('TEST 5: open palworld (resolver only)')
r = app_resolver.resolve_app('palworld')
print('  [Resolver] palworld ->', r)

# --- TEST 6: open college stuff folder ---
print()
print('TEST 6: open college stuff folder')
result = OpenFolderTool().execute('college stuff folder')
print('  [open_folder] success=' + str(result['success']) + ' | ' + result['output'])

# --- Custom game scan summary ---
print()
print('CUSTOM GAME SCAN SUMMARY:')
games = app_resolver.scan_custom_game_dirs()
for name, path in sorted(games.items()):
    print('  -', name, '->', path)

# --- close_app: already-closed app test ---
print()
print('TEST 7: close notepad (not running) - must return success=False')
result = CloseAppTool().execute('notepad')
print('  [close_app] success=' + str(result['success']) + ' | ' + result['output'])

print(sep)
