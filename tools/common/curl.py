import requests
from langchain_core.tools import tool

# one other approach is to use python subprocess and pipe output but its not good. 

@tool
def curl_ip_tool(ip_address: str, port: int = 80, use_https: bool = False):
    """
    Acts like 'curl'. Use this to see what content is hosted on a specific IP address.
    Example: ip_address="192.168.1.1", port=80
    """
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{ip_address}:{port}"
    
    try:
        # We set a short timeout so the agent doesn't hang if the IP is dead
        # verify=False is used here because internal IPs often have self-signed certs
        response = requests.get(url, timeout=5, verify=False)
        
        # Return status and first 2000 characters of content
        return {
            "status": response.status_code,
            "headers": dict(response.headers),
            "content": response.text[:2000] 
        }
    except Exception as e:
        return f"Error connecting to {url}: {str(e)}"