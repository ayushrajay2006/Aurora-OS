import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import main
main.import_tool_modules()

from brain.planner import planner

def test():
    response_text = """<speech>I've opened Microsoft Edge as requested.</speech>
<goal_status>partial</goal_status>

[JSON]
{
  "tools": [
    {
      "name": "press_key",
      "args": {
        "keys": "win+up"
      },
      "description": "Maximize the Microsoft Edge window"
    }
  ]
}
[/JSON]
"""
    
    reply, actions, speech_text, goal_status = planner.parse_response(response_text)
    print(f"Actions returned by planner.py: {actions}")
            
if __name__ == "__main__":
    test()
