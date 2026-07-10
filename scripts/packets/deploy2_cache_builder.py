#!/usr/bin/env python3
"""Generate one DEPLOY-2 Film Room role cache in an isolated process."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

from tqe.workshop.app_service import (
    film_room_execute_document,
    film_room_role_documents,
    read_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    documents = film_room_role_documents(read_json(args.plan))
    if args.role not in documents:
        raise SystemExit(f"role {args.role!r} is absent from {args.plan}")
    records = film_room_execute_document(documents[args.role], output_root=args.output_root)
    if len(records) != 1:
        raise SystemExit(f"expected one execution record, got {len(records)}")
    record = records[0]
    print(
        json.dumps(
            {
                "plan": str(args.plan),
                "role": args.role,
                "cache_before": record["cache_before"]["cache_status"],
                "cache_after_execute": record["cache_after_execute"]["cache_status"],
                "execution_id": record["execution"]["execution_id"],
                "returned_result_count": record["execution"].get("returned_result_count"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    del record, records, documents
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
