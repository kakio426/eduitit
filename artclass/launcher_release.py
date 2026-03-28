import os
import re
from io import BytesIO


LAUNCHER_RELEASE_PREFIX = "launcher/windows"
LAUNCHER_RELEASE_LATEST_KEY = f"{LAUNCHER_RELEASE_PREFIX}/latest.yml"
SAFE_RELEASE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()\-]{0,200}$")


class LauncherReleaseError(Exception):
    pass


class LauncherReleaseValidationError(LauncherReleaseError):
    pass


def get_launcher_bucket_settings():
    return {
        "bucket_name": (os.getenv("LAUNCHER_BUCKET_NAME") or "").strip(),
        "endpoint_url": (os.getenv("LAUNCHER_BUCKET_ENDPOINT") or "").strip(),
        "access_key_id": (os.getenv("LAUNCHER_BUCKET_ACCESS_KEY_ID") or "").strip(),
        "secret_access_key": (os.getenv("LAUNCHER_BUCKET_SECRET_ACCESS_KEY") or "").strip(),
        "region_name": (os.getenv("LAUNCHER_BUCKET_REGION") or "").strip(),
    }


def is_launcher_bucket_configured():
    settings = get_launcher_bucket_settings()
    return all(settings.values())


def _normalize_release_filename(filename):
    normalized = os.path.basename(str(filename or "").strip())
    if not normalized or "/" in normalized or "\\" in normalized:
        raise LauncherReleaseValidationError("파일 이름이 올바르지 않습니다.")
    if not SAFE_RELEASE_FILENAME_RE.match(normalized):
        raise LauncherReleaseValidationError("파일 이름에는 영문, 숫자, 공백, 점, 괄호, 밑줄, 대시만 사용할 수 있습니다.")
    return normalized


def _build_object_key(filename):
    return f"{LAUNCHER_RELEASE_PREFIX}/{_normalize_release_filename(filename)}"


def _is_cleanup_candidate_key(key):
    normalized_key = str(key or "").strip()
    if not normalized_key.startswith(f"{LAUNCHER_RELEASE_PREFIX}/"):
        return False
    lowered = normalized_key.lower()
    return lowered.endswith(".exe") or lowered.endswith(".exe.blockmap")


def _load_s3_client():
    settings = get_launcher_bucket_settings()
    if not all(settings.values()):
        raise LauncherReleaseError("런처 bucket 연결 정보가 아직 설정되지 않았습니다.")

    try:
        import boto3
    except ImportError as exc:
        raise LauncherReleaseError("boto3가 설치되지 않아 bucket에 연결할 수 없습니다.") from exc

    return boto3.client(
        "s3",
        endpoint_url=settings["endpoint_url"],
        aws_access_key_id=settings["access_key_id"],
        aws_secret_access_key=settings["secret_access_key"],
        region_name=settings["region_name"],
    )


def parse_latest_yml_text(raw_text):
    text = str(raw_text or "")
    version = ""
    installer_filename = ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("version:") and not version:
            version = stripped.split(":", 1)[1].strip().strip("'\"")
            continue
        if stripped.startswith("path:") and not installer_filename:
            installer_filename = stripped.split(":", 1)[1].strip().strip("'\"")
            continue
        if stripped.startswith("url:") and not installer_filename:
            installer_filename = stripped.split(":", 1)[1].strip().strip("'\"")

    if not version:
        raise LauncherReleaseValidationError("latest.yml에서 버전 정보를 읽지 못했습니다.")
    if not installer_filename:
        raise LauncherReleaseValidationError("latest.yml에서 설치파일 이름(path)을 읽지 못했습니다.")

    installer_filename = _normalize_release_filename(installer_filename)
    if not installer_filename.lower().endswith(".exe"):
        raise LauncherReleaseValidationError("latest.yml의 path는 .exe 설치파일이어야 합니다.")

    return {
        "version": version,
        "installer_filename": installer_filename,
        "blockmap_filename": f"{installer_filename}.blockmap",
    }


def get_current_launcher_release():
    if not is_launcher_bucket_configured():
        return None

    client = _load_s3_client()
    settings = get_launcher_bucket_settings()

    try:
        response = client.get_object(
            Bucket=settings["bucket_name"],
            Key=LAUNCHER_RELEASE_LATEST_KEY,
        )
    except Exception:
        return None

    raw_text = response["Body"].read().decode("utf-8")
    manifest = parse_latest_yml_text(raw_text)
    manifest["latest_filename"] = "latest.yml"
    manifest["latest_key"] = LAUNCHER_RELEASE_LATEST_KEY
    return manifest


def get_launcher_asset_download_url(filename, *, expires_in=900):
    client = _load_s3_client()
    settings = get_launcher_bucket_settings()
    normalized_filename = _normalize_release_filename(filename)
    object_key = _build_object_key(normalized_filename)

    try:
        client.head_object(Bucket=settings["bucket_name"], Key=object_key)
    except Exception as exc:
        raise LauncherReleaseError("요청한 런처 파일을 bucket에서 찾지 못했습니다.") from exc

    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings["bucket_name"],
            "Key": object_key,
        },
        ExpiresIn=expires_in,
    )


def _delete_stale_launcher_release_files(client, bucket_name, *, installer_filename, blockmap_filename):
    keep_keys = {
        LAUNCHER_RELEASE_LATEST_KEY,
        _build_object_key(installer_filename),
        _build_object_key(blockmap_filename),
    }
    continuation_token = None
    stale_keys = []

    while True:
        request_kwargs = {
            "Bucket": bucket_name,
            "Prefix": f"{LAUNCHER_RELEASE_PREFIX}/",
        }
        if continuation_token:
            request_kwargs["ContinuationToken"] = continuation_token

        response = client.list_objects_v2(**request_kwargs)
        for item in response.get("Contents") or []:
            key = item.get("Key") or ""
            if key in keep_keys:
                continue
            if _is_cleanup_candidate_key(key):
                stale_keys.append(key)

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    deleted_count = 0
    for index in range(0, len(stale_keys), 1000):
        chunk = stale_keys[index:index + 1000]
        if not chunk:
            continue
        client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
        )
        deleted_count += len(chunk)

    return deleted_count


def upload_launcher_release_bundle(*, latest_yml_file, installer_file, blockmap_file):
    if not is_launcher_bucket_configured():
        raise LauncherReleaseError("런처 bucket 연결 정보가 아직 설정되지 않았습니다.")
    if not latest_yml_file or not installer_file or not blockmap_file:
        raise LauncherReleaseValidationError("latest.yml, 설치파일(.exe), blockmap 파일을 모두 올려 주세요.")

    latest_filename = _normalize_release_filename(latest_yml_file.name)
    if latest_filename.lower() != "latest.yml":
        raise LauncherReleaseValidationError("설명 파일 이름은 latest.yml이어야 합니다.")

    latest_bytes = latest_yml_file.read()
    latest_yml_file.seek(0)
    try:
        latest_text = latest_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LauncherReleaseValidationError("latest.yml은 UTF-8 텍스트 파일이어야 합니다.") from exc

    manifest = parse_latest_yml_text(latest_text)
    installer_filename = _normalize_release_filename(installer_file.name)
    blockmap_filename = _normalize_release_filename(blockmap_file.name)

    if installer_filename != manifest["installer_filename"]:
        raise LauncherReleaseValidationError("설치파일 이름이 latest.yml의 path와 다릅니다.")
    if blockmap_filename != manifest["blockmap_filename"]:
        raise LauncherReleaseValidationError("blockmap 파일 이름은 설치파일 이름 뒤에 .blockmap이 붙어야 합니다.")

    client = _load_s3_client()
    settings = get_launcher_bucket_settings()
    bucket_name = settings["bucket_name"]

    client.upload_fileobj(
        BytesIO(latest_bytes),
        bucket_name,
        LAUNCHER_RELEASE_LATEST_KEY,
        ExtraArgs={"ContentType": "text/yaml; charset=utf-8"},
    )

    installer_file.seek(0)
    client.upload_fileobj(
        installer_file.file,
        bucket_name,
        _build_object_key(installer_filename),
        ExtraArgs={"ContentType": "application/octet-stream"},
    )

    blockmap_file.seek(0)
    client.upload_fileobj(
        blockmap_file.file,
        bucket_name,
        _build_object_key(blockmap_filename),
        ExtraArgs={"ContentType": "application/octet-stream"},
    )

    deleted_count = _delete_stale_launcher_release_files(
        client,
        bucket_name,
        installer_filename=installer_filename,
        blockmap_filename=blockmap_filename,
    )

    manifest["latest_filename"] = "latest.yml"
    manifest["deleted_stale_file_count"] = deleted_count
    return manifest
