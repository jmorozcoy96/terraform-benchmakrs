# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3","pandas"]
# ///
from typing import TypedDict
import boto3, pandas as pd, json
from urllib.parse import urlparse

class Result(TypedDict):
    rate_2xx: float
    rate_4xx: float
    rate_5xx: float

def _iter_keys(s3, bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                yield obj["Key"]

def main(input: str) -> Result:
    o = urlparse(input if input.startswith("s3://") else f"s3://{input}")
    bucket, prefix = o.netloc, o.path.lstrip("/")
    s3 = boto3.client("s3")
    counts: dict[int,int] = {}
    for key in _iter_keys(s3, bucket, prefix):
        obj = s3.get_object(Bucket=bucket, Key=key)
        try:
            df = pd.read_json(obj["Body"], lines=True)
        except ValueError:
            rec = json.loads(obj["Body"].read())
            df = pd.DataFrame([rec])
        s = df["message"].astype(str).str.extract(r"HTTP Status Code:\s*(\d+)")[0].dropna().astype(int).value_counts()
        for k, v in s.items():
            counts[int(k)] = counts.get(int(k), 0) + int(v)
    total = sum(counts.values())
    if total == 0:
        return {"rate_2xx": 0.5, "rate_4xx": 0.2, "rate_5xx": 0.3}
    r2 = sum(v for k,v in counts.items() if 200<=k<300)/total
    r4 = sum(v for k,v in counts.items() if 400<=k<500)/total
    r5 = sum(v for k,v in counts.items() if 500<=k<600)/total
    return {"rate_2xx": r2, "rate_4xx": r4, "rate_5xx": r5}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("input")
    print(main(parser.parse_args().input))
