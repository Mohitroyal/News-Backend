import os
import sys
import subprocess

print("Running automated Django deployment steps inside intercepted download_fonts.py...")

# Path to the django project
django_dir = os.path.join(os.path.dirname(__file__), "Spotnewsv2", "backend", "spotnews_django")

def run_cmd(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True, cwd=django_dir)

try:
    run_cmd("python manage.py collectstatic --no-input")
    run_cmd("python manage.py migrate")
    print("Django deployment steps completed successfully!")
except Exception as e:
    print(f"Error during deployment steps: {e}")
