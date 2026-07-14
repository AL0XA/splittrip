"""Install requirements without SOCKS proxy (local dev helper)."""
import os
import subprocess
import sys

env = os.environ.copy()
for key in list(env):
    if "proxy" in key.lower():
        del env[key]
env["NO_PROXY"] = "*"
env["no_proxy"] = "*"

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    env=env,
)
