"""OSS/CDN Upload Service — 自动上传参考图获得公网 URL."""
import os
from loguru import logger


async def upload_to_oss(local_path: str, remote_key: str = "",
                        provider: str = "local",
                        endpoint: str = "", bucket: str = "",
                        access_key: str = "", secret_key: str = "") -> str:
    """
    上传文件到 OSS，返回公网 URL.

    Provider: local | minio | aliyun_oss
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    if provider == "local":
        return f"file://{os.path.abspath(local_path)}"

    if provider == "minio":
        import boto3
        from botocore.config import Config
        client = boto3.client(
            "s3",
            endpoint_url=endpoint or "http://localhost:9000",
            aws_access_key_id=access_key or "minioadmin",
            aws_secret_access_key=secret_key or "minioadmin",
            config=Config(signature_version="s3v4"),
        )
        key = remote_key or os.path.basename(local_path)
        client.upload_file(local_path, bucket or "dy-auto-assets", key)
        url = f"{endpoint}/{bucket}/{key}"
        logger.info(f"Uploaded to MinIO: {url}")
        return url

    if provider == "aliyun_oss":
        import oss2
        auth = oss2.Auth(access_key, secret_key)
        b = oss2.Bucket(auth, endpoint, bucket)
        key = remote_key or f"characters/{os.path.basename(local_path)}"
        b.put_object_from_file(key, local_path)
        url = f"https://{bucket}.{endpoint.replace('https://', '')}/{key}"
        logger.info(f"Uploaded to OSS: {url}")
        return url

    logger.warning(f"Unknown OSS provider: {provider}, returning local path")
    return f"file://{os.path.abspath(local_path)}"
