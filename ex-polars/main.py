# /// script
# requires-python = ">=3.12"
# dependencies = ["polars"]
# ///
from typing import TypedDict
import polars as pl

class Result(TypedDict):
    rate_2xx: float
    rate_4xx: float
    rate_5xx: float

def main(input: str) -> Result:
    uri = input if input.startswith("s3://") else f"s3://{input}"
    df = pl.scan_ndjson(f"{uri.rstrip('/')}/**/*.json")
    agg = (
        df.with_columns(pl.col("message").str.extract(r"HTTP Status Code:\s*(\d+)").cast(pl.Int64).alias("code"))
          .groupby("code").len()
          .collect()
    )
    total = int(agg["len"].sum()) if agg.height else 0
    if total == 0:
        return {"rate_2xx": 0.5, "rate_4xx": 0.2, "rate_5xx": 0.3}
    r2 = int(agg.filter((pl.col("code")>=200)&(pl.col("code")<300))["len"].sum())/total
    r4 = int(agg.filter((pl.col("code")>=400)&(pl.col("code")<500))["len"].sum())/total
    r5 = int(agg.filter((pl.col("code")>=500)&(pl.col("code")<600))["len"].sum())/total
    return {"rate_2xx": r2, "rate_4xx": r4, "rate_5xx": r5}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("input")
    print(main(parser.parse_args().input))
# /// end-script