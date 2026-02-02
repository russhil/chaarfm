import boto3
import os
from dotenv import load_dotenv
from botocore.config import Config

load_dotenv()

endpoint = os.getenv("S3_ENDPOINT")
key = os.getenv("S3_ACCESS_KEY")
secret = os.getenv("S3_SECRET_KEY")

print(f"Connecting to {endpoint}...")

client = boto3.client(
    's3',
    endpoint_url=endpoint,
    aws_access_key_id=key,
    aws_secret_access_key=secret,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

try:
    response = client.list_buckets()
    print("Buckets found:")
    for bucket in response['Buckets']:
        print(f"- {bucket['Name']}")
except Exception as e:
    print(f"Error: {e}")
