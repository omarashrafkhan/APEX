import subprocess
import sys
import shlex
from langchain.tools import tool

SQLMAP_PATH = r"C:\Users\abdul\Downloads\sqlmapproject-sqlmap-e433332\sqlmap.py"

@tool
def run_sqlmap(command_args: str) -> str:
    """
    Run sqlmap commands for SQL injection testing.
    
    Use this tool to test web applications for SQL injection vulnerabilities.
    
    Args:
        command_args: The sqlmap arguments as a string. 
                      Example: '-u "http://target.com/page?id=1" --dbs'
                      Example: '-u "http://target.com/login" --data="user=a&pass=b" --batch'
    
                      
To get a list of basic options and switches use:

   -h

To get a list of all options and switches use:

   -hh
   
    Returns:
        The stdout/stderr output from sqlmap as a string.
    """
    if not command_args or not command_args.strip():
        return "Error: command_args is required. Example: -u \"http://localhost:60489/admin.php\" --batch"

    # Parse while preserving quoted arguments like --data="a=1&b=2"
    parsed_args = shlex.split(command_args)

    # Normalize URL after -u/--url to include scheme if omitted
    for i, token in enumerate(parsed_args):
        if token in ("-u", "--url") and i + 1 < len(parsed_args):
            raw_url = parsed_args[i + 1].strip('"').strip("'")
            if raw_url and not raw_url.lower().startswith(("http://", "https://")):
                raw_url = f"http://{raw_url}"
            parsed_args[i + 1] = raw_url

    # Build the command: python sqlmap.py <args>
    cmd = [sys.executable, SQLMAP_PATH] + parsed_args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        output = f"[CMD] {' '.join(cmd)}\n\n" + result.stdout
        if result.stderr:
            output += "\n[STDERR]:\n" + result.stderr
        return output if output else "No output returned."
    
    except subprocess.TimeoutExpired:
        return "Error: sqlmap timed out after 120 seconds."
    except FileNotFoundError:
        return f"Error: Could not find sqlmap at {SQLMAP_PATH}"
    except Exception as e:
        return f"Error running sqlmap: {str(e)}"