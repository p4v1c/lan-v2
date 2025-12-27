#!/usr/bin/env python3
import argparse
import os
import subprocess

def start(container_name):
    print(f"Starting AlgoHub with container: {container_name}...")
    env = os.environ.copy()
    env["PENTEST_CONTAINER"] = container_name
    # Ajout de --build pour forcer la reconstruction de l'image
    subprocess.run(["docker", "compose", "up", "-d", "--build"], env=env, check=True)
    print("AlgoHub started successfully.")

def stop():
    print("Stopping AlgoHub...")
    subprocess.run(["docker", "compose", "down"], check=True)
    print("AlgoHub stopped successfully.")

def main():
    parser = argparse.ArgumentParser(description="AlgoHub CLI")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the AlgoHub services.")
    start_parser.add_argument("container", help="The name of the pentesting container (e.g., exegol-Lan).")

    subparsers.add_parser("stop", help="Stop the AlgoHub services.")

    args = parser.parse_args()

    if args.command == "start":
        start(args.container)
    elif args.command == "stop":
        stop()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
