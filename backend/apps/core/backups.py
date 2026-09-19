import hashlib
import json
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone


def _postgres_config():
    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.postgresql":
        raise CommandError("Database backups require the configured PostgreSQL database.")
    return database


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix != ".dump":
        raise CommandError("Backup must be an existing .dump file.")
    manifest_path = path.with_suffix(".json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != _sha256(path):
            raise CommandError("Backup checksum does not match its manifest.")
    try:
        subprocess.run(
            ["pg_restore", "--list", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise CommandError("PostgreSQL could not verify the backup archive.") from error
    return path


def create_database_backup():
    database = _postgres_config()
    backup_dir = Path(settings.BACKUP_DIR).resolve()
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    final_path = backup_dir / f"hotline-doc-{stamp}.dump"
    temporary_path = backup_dir / f".{final_path.name}.partial"
    environment = os.environ.copy()
    environment["PGPASSWORD"] = str(database.get("PASSWORD", ""))
    command = [
        "pg_dump",
        "--host",
        str(database.get("HOST") or "localhost"),
        "--port",
        str(database.get("PORT") or "5432"),
        "--username",
        str(database.get("USER") or ""),
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(temporary_path),
        str(database.get("NAME") or ""),
    ]
    try:
        subprocess.run(
            command,
            check=True,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(final_path)
        verify_backup(final_path)
    except (CommandError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise CommandError("PostgreSQL backup failed; credentials were not logged.") from error

    manifest = {
        "created_at": timezone.now().isoformat(),
        "filename": final_path.name,
        "sha256": _sha256(final_path),
        "size_bytes": final_path.stat().st_size,
        "format": "postgresql-custom",
    }
    manifest_path = final_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.chmod(manifest_path, 0o600)

    backups = sorted(backup_dir.glob("hotline-doc-*.dump"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old_backup in backups[settings.BACKUP_RETENTION_COUNT :]:
        old_backup.unlink(missing_ok=True)
        old_backup.with_suffix(".json").unlink(missing_ok=True)
    return final_path
