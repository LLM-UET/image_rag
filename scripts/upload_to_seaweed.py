#!/usr/bin/env python3
"""
Upload a file to SeaweedFS.

Usage:
  python scripts/upload_to_seaweed.py --file PATH [--master http://localhost:9333] [--volume http://localhost:8080]

If no master/volume provided, the script will use the project's `SeaweedFSClient` defaults.
"""
import argparse
import sys
from pathlib import Path

# Add repo root and src to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / 'src'))

from api.seaweedfs_client import SeaweedFSClient


def main():
    parser = argparse.ArgumentParser(description="Upload a file to SeaweedFS and print fid/url")
    parser.add_argument("--file", required=True, help="Local file path to upload")
    parser.add_argument("--master", required=False, help="Seaweed master URL (overrides config)")
    parser.add_argument("--volume", required=False, help="Seaweed volume URL (optional override)")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 2

    client = SeaweedFSClient(master_url=args.master, volume_url=args.volume)

    try:
        fid, url = client.upload_file(str(file_path), filename=file_path.name)
        print("Uploaded:")
        print(" fid:", fid)
        print(" url:", url)
        return 0
    except Exception as e:
        print("Upload failed:", e)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())