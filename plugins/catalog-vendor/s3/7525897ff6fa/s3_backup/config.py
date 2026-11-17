"""Environment-based configuration for the s3 plugin.

Secrets (access key / secret key) are read from the process environment only
(typically ~/.duckwork/.env on a Duckwork host). Behavioral config (endpoint,
region, bucket, rules path) is also env-driven. Nothing sensitive is ever
written to the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_RULES_PATH = "~/.duckwork/s3-backup.rules.yaml"


@dataclass(frozen=True)
class Config:
    endpoint: str | None
    region: str | None
    bucket: str | None
    access_key: str | None
    secret_key: str | None
    rules_path: str

    @property
    def has_credentials(self) -> bool:
        return bool(self.access_key) and bool(self.secret_key)

    @property
    def is_usable(self) -> bool:
        return bool(self.bucket)

    def missing_storage_values(self) -> list[str]:
        values = (
            ("S3_BACKUP_ENDPOINT", self.endpoint),
            ("S3_BACKUP_REGION", self.region),
            ("S3_BACKUP_BUCKET", self.bucket),
            ("S3_BACKUP_ACCESS_KEY", self.access_key),
            ("S3_BACKUP_SECRET_KEY", self.secret_key),
        )
        return [name for name, value in values if not value]

    def require_storage(self) -> None:
        missing = self.missing_storage_values()
        if missing:
            raise RuntimeError(
                "S3 backup configuration is incomplete; set: " + ", ".join(missing)
            )


def load_config() -> Config:
    rules_path = os.environ.get("S3_BACKUP_RULES") or DEFAULT_RULES_PATH
    return Config(
        endpoint=os.environ.get("S3_BACKUP_ENDPOINT") or None,
        region=os.environ.get("S3_BACKUP_REGION") or None,
        bucket=os.environ.get("S3_BACKUP_BUCKET") or None,
        access_key=os.environ.get("S3_BACKUP_ACCESS_KEY") or None,
        secret_key=os.environ.get("S3_BACKUP_SECRET_KEY") or None,
        rules_path=os.path.expanduser(rules_path),
    )
