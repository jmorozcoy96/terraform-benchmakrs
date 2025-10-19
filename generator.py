# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "boto3",
# ]
# ///


import concurrent.futures
import datetime
import json
import pathlib
import random
import uuid
from typing import Any, Callable, Iterator

import boto3


def main(num_files: int, writer: Callable[[dict[str, Any]], None]):
    event_generator = _generate_random_event()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for _ in range(num_files):
            event = next(event_generator)
            executor.submit(writer, event)


class _LocalWriter:
    def __init__(self, dir: pathlib.Path):
        self._dir = dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        name = f"{uuid.uuid4()}.json"
        print(f"writing {name}")
        with open(self._dir / name, "w") as file:
            file.write(payload)


class _S3Writer:
    def __init__(self, bucket: str, prefix: str):
        self._bucket = bucket
        self._prefix = prefix
        self._s3 = boto3.client("s3")
        self._s3.create_bucket(Bucket=self._bucket)

    def __call__(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        name = f"{uuid.uuid4()}.json"
        print(f"writing {name}")
        self._s3.put_object(Bucket=self._bucket, Key=f"{self._prefix}/{name}", Body=payload)


def _generate_random_event() -> Iterator[dict[str, Any]]:
    random.seed(a=42)
    statuses = [200, 201, 202, 203, 400, 401, 402, 403, 404, 500]
    services = ["training", "evaluation", "inference", "monitoring"]
    now = datetime.datetime.now()
    while True:
        status_code = random.choice(statuses)
        now += datetime.timedelta(seconds=random.randint(1, 300))
        yield {
            "service": random.choice(services),
            "timestamp": now.timestamp(),
            "message": f"HTTP Status Code: {status_code}",
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Output path for the data, could be a local directory or a bucket, specify with the --is-bucket flag")
    parser.add_argument("--is-bucket", action="store_true", help="Whether the output is a bucket")
    parser.add_argument(
        "--num-files",
        default=1000,
        type=int,
        help="Number of files to generate in the output directory",
    )
    args = parser.parse_args()

    if args.is_bucket:
        writer = _S3Writer(args.output, "generator")
    else:
        writer = _LocalWriter(pathlib.Path(args.output))

    main(args.num_files, writer)
