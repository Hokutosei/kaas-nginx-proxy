from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import docker
import os

# File paths for different mappings
DOMAINS_MAP_FILE = "/etc/nginx/domains.map"  # K3s API SNI routing
APPS_MAP_FILE    = "/etc/nginx/apps.map"     # HTTP app routing

NGINX_CONTAINER = os.getenv("NGINX_CONTAINER", "nginx-proxmox")

app = FastAPI()
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

class Mapping(BaseModel):
    domain: str     # full hostname
    target: str     # IP:port

def update_map_file(map_file: str, domain: str, target: str):
    """Add or update a mapping in the given map file, then reload Nginx."""
    line = f"{domain} {target};\n"
    try:
        # Read current lines (if file exists)
        lines = []
        if os.path.exists(map_file):
            with open(map_file, "r") as f:
                lines = f.readlines()

        # Remove any existing entry for this domain
        lines = [l for l in lines if not l.strip().startswith(domain)]

        # Add the new entry
        lines.append(line)

        # Sort for reproducibility
        with open(map_file, "w") as f:
            f.writelines(sorted(lines))

        # Reload Nginx
        container = client.containers.get(NGINX_CONTAINER)
        container.exec_run("nginx -s reload")

        return {"status": "updated", "domain": domain, "map_file": map_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Existing: Add or update a K3s API domain mapping ===
@app.post("/add")
def add_k3s_mapping(mapping: Mapping):
    return update_map_file(DOMAINS_MAP_FILE, mapping.domain, mapping.target)

# === New: Add or update an HTTP app mapping ===
@app.post("/add-app")
def add_app_mapping(mapping: Mapping):
    return update_map_file(APPS_MAP_FILE, mapping.domain, mapping.target)