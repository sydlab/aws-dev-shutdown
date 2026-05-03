#!/usr/bin/env python3
"""
Stop tagged dev EC2 instances older than MAX_AGE_HOURS.
Controlled by env vars; intended for GitHub Actions or local runs.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or not str(v).strip():
        return default
    try:
        return int(str(v).strip(), 10)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {v!r}") from e


def main() -> dict[str, Any]:
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    ec2 = boto3.client("ec2", region_name=region)

    max_age = _env_int("MAX_AGE_HOURS", 8)
    if max_age < 1:
        raise ValueError(f"MAX_AGE_HOURS must be at least 1 (got {max_age})")
    dry_run = _env_bool("DRY_RUN", True)
    tag_key = os.environ.get("TARGET_TAG_KEY", "AutoShutdown")
    tag_value = os.environ.get("TARGET_TAG_VALUE", "true")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age)

    filters = [
        {"Name": f"tag:{tag_key}", "Values": [tag_value]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]
    paginator = ec2.get_paginator("describe_instances")

    stale: list[dict[str, Any]] = []
    for page in paginator.paginate(Filters=filters):
        for reservation in page.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                iid = inst["InstanceId"]
                lt = inst.get("LaunchTime")
                if lt is None:
                    continue
                launch = lt if lt.tzinfo else lt.replace(tzinfo=timezone.utc)
                if launch < cutoff:
                    name = ""
                    for t in inst.get("Tags", []):
                        if t.get("Key") == "Name":
                            name = t.get("Value") or ""
                            break
                    stale.append(
                        {
                            "InstanceId": iid,
                            "Name": name,
                            "LaunchTime": launch.isoformat(),
                            "Region": region,
                        }
                    )

    ids = [x["InstanceId"] for x in stale]
    stopped: list[str] = []

    if dry_run:
        result = {
            "dry_run": True,
            "region": region,
            "max_age_hours": max_age,
            "tag": f"{tag_key}={tag_value}",
            "would_stop": ids,
            "details": stale,
            "count": len(ids),
        }
        print(json.dumps(result, indent=2))
        return result

    if ids:
        # EC2 accepts at most 1000 instance IDs per StopInstances request.
        batch_size = 1000
        for i in range(0, len(ids), batch_size):
            chunk = ids[i : i + batch_size]
            ec2.stop_instances(InstanceIds=chunk)
        stopped = ids

    result = {
        "dry_run": False,
        "region": region,
        "max_age_hours": max_age,
        "tag": f"{tag_key}={tag_value}",
        "stopped": stopped,
        "details": stale,
        "count": len(stopped),
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        err = {"error": str(e), "type": type(e).__name__}
        print(json.dumps(err), file=sys.stderr)
        sys.exit(1)
