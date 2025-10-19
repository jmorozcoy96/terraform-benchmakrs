# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3","pytest"]
# ///
import main

def test_default_no_data():
    assert main.main("s3://nonexistent-bucket/path") == {
        "rate_2xx": 0.5,
        "rate_4xx": 0.2,
        "rate_5xx": 0.3,
    }
# /// end-script