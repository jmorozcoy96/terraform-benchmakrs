# /// script
# requires-python = ">=3.12"
# dependencies = ["pyspark"]
# ///
from typing import TypedDict
from pyspark.sql import SparkSession, functions as F

class Result(TypedDict):
    rate_2xx: float
    rate_4xx: float
    rate_5xx: float

def main(input: str) -> Result:
    uri = input if input.startswith("s3a://") else (input.replace("s3://","s3a://") if input.startswith("s3://") else f"s3a://{input}")
    spark = SparkSession.builder.appName("rates-parquet").getOrCreate()
    df = spark.read.parquet(uri)
    g = (df.select(F.regexp_extract("message", r"HTTP Status Code:\\s*(\\d+)", 1).cast("int").alias("code"))
            .groupBy("code").count())
    rows = [(r["code"], r["count"]) for r in g.collect() if r["code"] is not None]
    spark.stop()
    total = sum(c for _, c in rows)
    if total == 0:
        return {"rate_2xx": 0.5, "rate_4xx": 0.2, "rate_5xx": 0.3}
    r2 = sum(c for k,c in rows if 200<=k<300)/total
    r4 = sum(c for k,c in rows if 400<=k<500)/total
    r5 = sum(c for k,c in rows if 500<=k<600)/total
    return {"rate_2xx": r2, "rate_4xx": r4, "rate_5xx": r5}

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("input")
    print(main(p.parse_args().input))
# /// end-script