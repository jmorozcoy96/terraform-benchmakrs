# Data Analysis Tools Benchmark (AWS + Terraform)

Este proyecto compara el rendimiento para contar códigos HTTP ("HTTP Status Code: XXX") en logs NDJSON almacenados en S3 usando:

* Python puro

* Pandas

* Polars

* DuckDB

* Spark

Métricas: tiempo de pared, CPU, RAM (RSS) y logs detallados.
Los datasets se generan por tamaño lógico: 5GB, 10GB, 15GB (puedes ampliar a 20/25GB si lo necesitas).

# 0) Prerrequisitos

AWS CLI v2 y Terraform ≥ 1.5

Una key pair en AWS (si vas a usar SSH; con SSM no es necesario)

Recomendado: autenticación con AWS SSO

En tu laptop: git, y (opcional) uv / python3 si fueras a probar en local

# 1) Autenticación con AWS SSO (local)
aws configure sso
Completa: SSO Start URL, SSO Region, cuenta y rol. Nombra el perfil: p.ej. benchmark-sso

aws sso login --profile benchmark-sso
export AWS_PROFILE=benchmark-sso
export AWS_SDK_LOAD_CONFIG=1


Si no usas SSO, configura aws_access_key_id/aws_secret_access_key con aws configure.

# 2) Crear el bucket S3 (Terraform)

Este módulo crea un bucket con un nombre único usando un prefijo.

cd Archive/infrastructure/s3
terraform init
terraform apply -auto-approve -var 'prefix=bench-alumno'


Copia el nombre del bucket que aparece (o revísalo en la consola). Lo usaremos más adelante.

# 3) Lanzar la EC2 con permisos S3 (Terraform)

Crea una m5.2xlarge con Ubuntu 22.04, Instance Profile con permisos de S3 (lectura y escritura), y dependencias base.

cd ../ec2
terraform init
terraform apply -auto-approve \
  -var 'prefix=bench-alumno' \
  -var 'bucket_name=<mi-bucket>' \
  -var 'key_name=<tu-keypair>'    # si usarás SSH
instance_type por defecto m5.2xlarge


Importante (permisos S3): este módulo debe adjuntar una policy al rol de la EC2 con s3:PutObject, s3:GetObject y s3:ListBucket sobre:

arn:aws:s3:::<mi-bucket>
arn:aws:s3:::<mi-bucket>/*


Si al generar datos ves AccessDenied: s3:PutObject, vuelve a aplicar el Terraform de EC2 con esa política incluida.

Guarda la IP pública (si usarás SSH) y confirma que la instancia llegó a estado running.

# 4) Conectarte a la EC2 y preparar el repo
## Opción A — AWS SSM (sin SSH/puerto 22)

Requisito: la EC2 tiene asociada la policy AmazonSSMManagedInstanceCore (el módulo de EC2 ya lo incluye).

aws ssm start-session --target <INSTANCE_ID>
dentro de la sesión:
sudo -iu ubuntu
cd ~

## Opción B — SSH
ssh -i ~/.ssh/<tu-keypair>.pem ubuntu@<EC2_PUBLIC_IP>

Clonar tu repo en la EC2
cd ~
git clone https://github.com/jmorozcoy96/terraform-benchmakrs.git repo
cd repo

Instalar dependencias que pueden faltar

Muchas vienen del user-data, pero asegúralo (especialmente tabulate que usa Pandas para to_markdown):

python3 -m pip install --user --upgrade pip
python3 -m pip install --user tabulate "polars[s3]" s3fs boto3 pandas duckdb pyspark

(Solo Spark) Configurar paquetes Hadoop-AWS en runtime
export PYSPARK_SUBMIT_ARGS="--packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 pyspark-shell"

# 5) Generar los datasets en S3 (5GB, 10GB, 15GB)

Define variables:

export BUCKET=<mi-bucket>         # p.ej. bench-alumno-xxxxxx
export PREFIX=logs                # puedes usar otro prefijo


Genera los tamaños (cada uno queda en su subcarpeta: s3://$BUCKET/$PREFIX/5GB, …/10GB, …/15GB):

for GB in 5 10 15; do
  echo "==> Generando ${GB}GB en s3://$BUCKET/$PREFIX/${GB}GB"
  python3 generator.py "s3://$BUCKET/$PREFIX/${GB}GB" --size-gb $GB
done


Si tardara demasiado o se “pega”, puedes interrumpir con Ctrl+C. Para cancelar definitivamente si la terminal no responde, abre otra sesión y mata el proceso python3 del generador con pkill -f generator.py.

# 6) Ejecutar el benchmark

Tu run.sh espera un prefijo S3 completo y una lista de implementaciones (por defecto solo ex-python).
Asegúrate de haber modificado tu run.sh para que ejecute cada tamaño construyendo URI="${SOURCE%/}/$label" .

Ejemplo: correr todas las herramientas sobre 5/10/15GB:

Estando en ~/repo
bash run.sh "s3://$BUCKET/$PREFIX" ex-python,ex-pandas,ex-polars,ex-duckdb,ex-spark


El script llamará a cada ex-*/main.py usando uv run (asegúrate de tener uv instalado; si no, instala con pip install uv o cambia uv run por python3).

Para Spark, recuerda exportar PYSPARK_SUBMIT_ARGS como arriba.

(Opcional) Parquet

Si quieres comparar JSON vs Parquet (solo Polars y Spark):

Convierte JSON → Parquet en S3:

# Polars:
python3 - <<'PY'
import polars as pl, os
bucket=os.environ["BUCKET"]; src=f"s3://{bucket}/{os.environ.get('PREFIX','logs')}/10GB"
dst=f"s3://{bucket}/logs_parquet/10GB"
pl.scan_ndjson(f"{src}/**/*.ndjson").sink_parquet(f"{dst}/part-*.parquet")
print("OK:", dst)
PY

# Spark:
python3 - <<'PY'
from pyspark.sql import SparkSession
import os
bucket=os.environ["BUCKET"]; src=f"s3a://{bucket}/{os.environ.get('PREFIX','logs')}/10GB"
dst=f"s3a://{bucket}/logs_parquet/10GB"
spark=SparkSession.builder.getOrCreate()
spark.read.json(src).write.mode("overwrite").parquet(dst)
spark.stop()
print("OK:", dst)
PY


Corre variantes ex-polars_v2 y/o ex-spark_v2 contra s3://$BUCKET/logs_parquet/10GB.

# 7) Resultados

Crudos por job: results/raw/

CSV de métricas: results/metrics.csv

Reporte: results/report.md

Ver reporte:

cat results/report.md

# Limpieza
## EC2
cd Archive/infrastructure/ec2
terraform destroy -auto-approve

## S3 (opcional; elimina datos y el bucket)
cd ../s3
terraform destroy -auto-approve

# Solución de problemas

## AccessDenied: s3:PutObject
Tu rol de EC2 necesita estas acciones sobre tu bucket:

s3:PutObject, s3:GetObject, s3:ListBucket
y recursos:

arn:aws:s3:::<mi-bucket>
arn:aws:s3:::<mi-bucket>/*


Vuelve a aplicar el Terraform de EC2 con esa policy.
Verifica identidad dentro de la EC2:

aws sts get-caller-identity
aws s3 ls s3://$BUCKET


## Spark no puede leer S3
Asegúrate de exportar:

export PYSPARK_SUBMIT_ARGS="--packages org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262 pyspark-shell"


## Pandas pide tabulate
Instala:

python3 -m pip install --user tabulate


## DuckDB error httpfs
Dentro del script ya se hace:

INSTALL httpfs; LOAD httpfs; SET s3_region='auto'; SET s3_url_style='path';


Asegúrate de tener conexión a internet y que tu bucket/URI sea correcto.

run.sh solo muestra ex-python

Pasa el prefijo S3 completo: s3://<bucket>/<prefix>

Pasa la lista de herramientas: ex-python,ex-pandas,ex-polars,ex-duckdb,ex-spark

Asegúrate de que run.sh construye URI="${SOURCE%/}/$label" por cada tamaño (5GB/10GB/15GB).