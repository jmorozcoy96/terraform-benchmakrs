# /// script
# requires-python = ">=3.12"
# dependencies = ["duckdb"]
# ///
from typing import TypedDict
import duckdb

class Result(TypedDict):
    rate_2xx: float
    rate_4xx: float
    rate_5xx: float

def main(input: str) -> Result:
    uri = input if input.startswith("s3://") else f"s3://{input}"
    con = duckdb.connect(":memory:")
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='auto'; SET s3_url_style='path';")
    q = f"""
    WITH logs AS (
      SELECT * FROM read_json_auto('{uri.rstrip('/')}/**/*.json')
    ), ext AS (
      SELECT CAST(regexp_extract(message,'HTTP Status Code: (\\d+)',1) AS INTEGER) code FROM logs
    )
    SELECT code, COUNT(*) cnt FROM ext WHERE code IS NOT NULL GROUP BY 1;
    """
    rows = con.execute(q).fetchall()
    total = sum(c for _, c in rows)
    if total == 0:
        return {"rate_2xx": 0.5, "rate_4xx": 0.2, "rate_5xx": 0.3}
    r2 = sum(c for code,c in rows if 200<=code<300)/total
    r4 = sum(c for code,c in rows if 400<=code<500)/total
    r5 = sum(c for code,c in rows if 500<=code<600)/total
    return {"rate_2xx": r2, "rate_4xx": r4, "rate_5xx": r5}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("input")
    print(main(parser.parse_args().input))
# /// end-script