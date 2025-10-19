# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3"]
# ///

import argparse
import concurrent.futures
import datetime
import json
import math
import os
import pathlib
import random
import tempfile
import time
import uuid
from typing import Any, Callable, Iterator

import boto3

# ========= Config =========
# Toma ~95 bytes promedio por línea (ajustable si tus líneas cambian mucho)
BYTES_PER_LINE_EST = 95

STATUSES = [200, 201, 202, 203, 301, 302, 400, 401, 402, 403, 404, 409, 429, 500, 502, 503]
SERVICES = ["training", "evaluation", "inference", "monitoring", "auth", "orders", "catalog", "payments"]


def _now_iter() -> Iterator[float]:
    """Genera timestamps crecientes para simular eventos."""
    now = datetime.datetime.now()
    while True:
        now += datetime.timedelta(seconds=random.randint(1, 300))
        yield now.timestamp()


def _generate_random_event(ts_iter: Iterator[float]) -> dict[str, Any]:
    return {
        "service": random.choice(SERVICES),
        "timestamp": next(ts_iter),
        "message": f"HTTP Status Code: {random.choice(STATUSES)}",
    }


# ============= Writers =============
class _LocalWriter:
    def __init__(self, dir_: pathlib.Path):
        self._dir = dir_
        self._dir.mkdir(parents=True, exist_ok=True)

    def upload_part(self, local_path: str, part_idx: int) -> None:
        # Destino final .json (NDJSON por compatibilidad con ex-*)
        dest = self._dir / f"part-{part_idx:06d}.json"
        os.replace(local_path, dest)  # mover atómico
        print(f"[local] wrote {dest}")


class _S3Writer:
    def __init__(self, bucket: str, prefix: str):
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._s3 = boto3.client("s3")
        # Crea el bucket si no existe (si existe, ignora error)
        try:
            self._s3.create_bucket(Bucket=self._bucket)
        except Exception:
            pass

    def upload_part(self, local_path: str, part_idx: int) -> None:
        key = f"{self._prefix}/part-{part_idx:06d}.json" if self._prefix else f"part-{part_idx:06d}.json"
        self._s3.upload_file(local_path, self._bucket, key)
        os.remove(local_path)
        print(f"[s3] s3://{self._bucket}/{key}")


# ============= Modo por tamaño (GB) =============
def _generate_by_size(writer, size_gb: int) -> None:
    """
    Genera ~size_gb de NDJSON repartidos en muchas partes .json (línea por evento).
    """
    lines_needed = int((size_gb * (1024 ** 3)) / BYTES_PER_LINE_EST)
    batch = 20000  # nº de líneas por parte (ajustable)
    batches = math.ceil(lines_needed / batch)
    ts_iter = _now_iter()

    tmpdir = tempfile.mkdtemp()
    try:
        for b in range(batches):
            path = os.path.join(tmpdir, f"tmp-{uuid.uuid4().hex}.json")
            with open(path, "w") as f:
                # escribir NDJSON
                for _ in range(min(batch, lines_needed - b * batch)):
                    rec = _generate_random_event(ts_iter)
                    f.write(json.dumps(rec, separators=(",", ":")) + "\n")

            writer.upload_part(path, b)

            if (b + 1) % 50 == 0 or (b + 1) == batches:
                print(f"Uploaded {b + 1}/{batches} parts (~{size_gb}GB target).")
    finally:
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass


# ============= Modo compat: por número de archivos =============
def _compat_generate_num_files(num_files: int, writer_single_record: Callable[[dict[str, Any]], None]) -> None:
    ts_iter = _now_iter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for _ in range(num_files):
            event = _generate_random_event(ts_iter)
            executor.submit(writer_single_record, event)


def _compat_local_single_writer(dir_: pathlib.Path) -> Callable[[dict[str, Any]], None]:
    dir_.mkdir(parents=True, exist_ok=True)

    def _w(event: dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":"))
        name = f"{uuid.uuid4()}.json"
        print(f"[local-compat] writing {name}")
        with open(dir_ / name, "w") as fh:
            fh.write(payload)

    return _w


def _compat_s3_single_writer(bucket: str, prefix: str) -> Callable[[dict[str, Any]], None]:
    s3 = boto3.client("s3")
    try:
        s3.create_bucket(Bucket=bucket)
    except Exception:
        pass

    def _w(event: dict[str, Any]) -> None:
        payload = json.dumps(event, separators=(",", ":"))
        name = f"{uuid.uuid4()}.json"
        key = f"{prefix.rstrip('/')}/{name}" if prefix else name
        print(f"[s3-compat] writing {key}")
        s3.put_object(Bucket=bucket, Key=key, Body=payload)

    return _w


# ============= CLI =============
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate NDJSON logs locally or in S3.")
    p.add_argument("output", help="Local dir or s3://bucket/prefix")
    p.add_argument("--size-gb", type=int, default=None, help="Generate ~SIZE_GB of NDJSON under output prefix")
    p.add_argument("--is-bucket", action="store_true", help="(compat) Treat 'output' as a bucket name")
    p.add_argument("--num-files", type=int, default=None, help="(compat) Number of single-record JSON files to create")
    return p.parse_args()


def main():
    args = parse_args()

    # Modo por tamaño (recomendado)
    if args.size_gb is not None:
        out = args.output
        if out.startswith("s3://"):
            # s3://bucket/prefix
            _, _, rest = out.partition("s3://")
            parts = rest.split("/", 1)
            bucket = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""
            writer = _S3Writer(bucket, prefix)
        else:
            writer = _LocalWriter(pathlib.Path(out))
        _generate_by_size(writer, args.size_gb)
        return

    # Modo compat por archivos individuales
    if args.num_files is None:
        raise SystemExit("You must pass either --size-gb N or --num-files N")

    if args.is_buckets := args.is_bucket:
        # args.output = bucket en modo compat
        writer_fn = _compat_s3_single_writer(args.output, "generator")
    else:
        # args.output = carpeta local en modo compat
        writer_fn = _compat_local_single_writer(pathlib.Path(args.output))

    _compat_generate_num_files(args.num_files, writer_fn)


if __name__ == "__main__":
    main()
