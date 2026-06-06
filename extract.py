import json

def extract_planner():
    with open(r'C:\Users\ayush\.gemini\antigravity\brain\8f93a515-4209-4b38-b181-7b7e54d4bd85\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i in range(len(lines)-1, -1, -1):
        try:
            data = json.loads(lines[i])
            content = data.get('content', '')
            if 'Showing lines 1 to 168' in content and 'planner.py' in content:
                # Extract code
                lines_of_content = content.split('\n')
                code = []
                capture = False
                for line in lines_of_content:
                    if '1: import json' in line:
                        capture = True
                    if capture:
                        # strip the leading 'X: '
                        parts = line.split(': ', 1)
                        if len(parts) == 2 and parts[0].isdigit():
                            code.append(parts[1])
                
                with open('planner_recovered.py', 'w', encoding='utf-8') as out:
                    out.write('\n'.join(code))
                print("Recovered!")
                return
        except:
            pass
            
if __name__ == "__main__":
    extract_planner()
