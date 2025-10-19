# Data Analysis Tools Benchmark

## Introduction

You are working on a system that aggregates logs from multiple microservices. For each log is registered as an event containing the following information:

* The service name
* The timestamp when it occurred
* An *almost* arbitrary message about what happened.

In principle, the message can be arbitrary, the developer picks the message they want to log at anytime to help them debug. However, logging the status code of the response of any microservice is standarized so that they all look like HTTP Status Code: XXX. This way you can easily compare different services and see which one has more errors.

The data source for the task is going to be a directory in which JSON files are stored. Each JSON file looks like:

```json
{"service": "monitoring", "timestamp": 1745319168.057018, "message": "HTTP Status Code: 200"}
```

## Task

How fast can you figure out the rate of different status codes from a sed of messages stored on S3? It depends on the implementation, you need to do the following:

1. Pure Python (no additional dependencies used, besides boto3 to read the data). 
2. Pandas implementation, use pandas library to process the get insights about the data.
3. Polars
4. DuckDB
5. Spark

For each of the implementations you will measure processing time, disk, CPU and RAM usage for workloads that go from 5GB, 10GB, 15GB, ..., 25GB. All experiments will be done on a m5.2xlarge runing ubuntu. 

Use `bash run.sh [FOLDER NAME]` to execute each of the experiments and create the initial dataset using `uv run generator.py`

Write a report on the results of the experiments. 

## Optional Task

Find out whether there is any benefit from converting the data first to parquet files and then reading those files instead of the raw json files. This one only need to be implemented in Spark and Polars.



