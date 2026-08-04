from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass

import keyring

from logging_setup import get_logger

logger = get_logger("secrets")

LEGACY_SERVICE = "ScriptorDB"


def _service(workspace_id: str | None) -> str:
    if workspace_id:
        return f"scriptordb:{workspace_id}"
    return LEGACY_SERVICE


def get_api_key(provider: str, workspace_id: str | None = None) -> str | None:
    value = keyring.get_password(_service(workspace_id), provider)
    if value is None and workspace_id is not None:
        value = keyring.get_password(LEGACY_SERVICE, provider)
    return value


def save_api_key(provider: str, key: str, workspace_id: str | None = None) -> None:
    keyring.set_password(_service(workspace_id), provider, key)


def _safe_delete(service: str, provider: str) -> None:
    try:
        keyring.delete_password(service, provider)
    except Exception:
        pass


def delete_api_key(provider: str, workspace_id: str | None = None) -> None:
    _safe_delete(_service(workspace_id), provider)
    if workspace_id is not None:
        _safe_delete(LEGACY_SERVICE, provider)


def has_api_key(provider: str, workspace_id: str | None = None) -> bool:
    return get_api_key(provider, workspace_id) is not None


MYSQL_PASSWORD_USERNAME = "mysql_password"


def get_mysql_password(workspace_id: str) -> str | None:
    service = _service(workspace_id)
    logger.debug("Reading MySQL password from keyring: service=%s", service)
    password = keyring.get_password(service, MYSQL_PASSWORD_USERNAME)
    logger.debug("MySQL password %s for service=%s", "found" if password is not None else "not found", service)
    return password


def save_mysql_password(workspace_id: str, password: str) -> None:
    keyring.set_password(_service(workspace_id), MYSQL_PASSWORD_USERNAME, password)


def delete_mysql_password(workspace_id: str) -> None:
    _safe_delete(_service(workspace_id), MYSQL_PASSWORD_USERNAME)


def has_mysql_password(workspace_id: str) -> bool:
    return get_mysql_password(workspace_id) is not None


BROWSER_PROFILE_SERVICE_SUFFIX = ":browser_profile"
BROWSER_PROFILE_VERSION = 2
BROWSER_PROFILE_MAX_CHUNK_CHARS = 1800
BROWSER_PROFILE_MAX_TOTAL_BYTES = 1024 * 1024
BROWSER_PROFILE_MAX_CHUNK_COUNT = (
    ((BROWSER_PROFILE_MAX_TOTAL_BYTES // 3) + 1) * 4 // BROWSER_PROFILE_MAX_CHUNK_CHARS + 2
)
BROWSER_PROFILE_ENCODING = "base64"


class BrowserProfileStorageError(Exception):
    pass


class BrowserProfileWriteError(BrowserProfileStorageError):
    pass


class BrowserProfileCorruptedError(BrowserProfileStorageError):
    pass


class BrowserProfileTooLargeError(BrowserProfileStorageError):
    pass


def _profile_service(workspace_id: str) -> str:
    return _service(workspace_id) + BROWSER_PROFILE_SERVICE_SUFFIX


def _profile_get_password(service: str, username: str) -> str | None:
    try:
        return keyring.get_password(service, username)
    except Exception as e:
        raise BrowserProfileStorageError(
            f"Keyring read failed for '{username}': {e}"
        ) from e


def _profile_encode_payload(storage_state: object) -> bytes:
    return json.dumps(storage_state, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _profile_chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _profile_parse_meta(value: str) -> dict | None:
    try:
        obj = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if "version" not in obj:
        return None
    if obj.get("version") != BROWSER_PROFILE_VERSION:
        raise BrowserProfileCorruptedError(
            "Browser profile metadata has an unsupported version"
        )
    if (
        isinstance(obj.get("generation"), str)
        and isinstance(obj.get("chunk_count"), int)
        and isinstance(obj.get("sha256"), str)
    ):
        return obj
    raise BrowserProfileCorruptedError("Browser profile metadata is malformed")


def _profile_read_meta(service: str, profile_name: str) -> dict | None:
    value = _profile_get_password(service, profile_name)
    if value is None:
        return None
    return _profile_parse_meta(value)


def _profile_cleanup_generation(
    service: str, profile_name: str, generation: str, chunk_count: int
) -> None:
    for i in range(chunk_count):
        _safe_delete(service, f"{profile_name}:{generation}:{i}")


def save_browser_profile(workspace_id: str, profile_name: str, storage_state: object) -> None:
    service = _profile_service(workspace_id)
    raw = _profile_encode_payload(storage_state)
    if len(raw) > BROWSER_PROFILE_MAX_TOTAL_BYTES:
        raise BrowserProfileTooLargeError(
            f"Browser profile '{profile_name}' exceeds the size limit "
            f"({len(raw)} > {BROWSER_PROFILE_MAX_TOTAL_BYTES} bytes)"
        )
    b64 = base64.b64encode(raw).decode("ascii")
    chunks = _profile_chunk_text(b64, BROWSER_PROFILE_MAX_CHUNK_CHARS)
    generation = uuid.uuid4().hex[:12]

    try:
        old_meta = _profile_read_meta(service, profile_name)
    except BrowserProfileStorageError:
        old_meta = None

    try:
        for i, chunk in enumerate(chunks):
            keyring.set_password(service, f"{profile_name}:{generation}:{i}", chunk)
        meta = json.dumps(
            {
                "version": BROWSER_PROFILE_VERSION,
                "generation": generation,
                "chunk_count": len(chunks),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "encoding": BROWSER_PROFILE_ENCODING,
            },
            separators=(",", ":"),
        )
        keyring.set_password(service, profile_name, meta)
    except Exception as e:
        _profile_cleanup_generation(service, profile_name, generation, len(chunks))
        raise BrowserProfileWriteError(
            f"Failed to save browser profile '{profile_name}': {e}"
        ) from e

    if old_meta and old_meta.get("generation") != generation:
        _profile_cleanup_generation(
            service, profile_name, old_meta["generation"], old_meta["chunk_count"]
        )


def get_browser_profile(workspace_id: str, profile_name: str) -> dict | None:
    service = _profile_service(workspace_id)
    value = _profile_get_password(service, profile_name)
    if value is None:
        return None

    meta = _profile_parse_meta(value)
    if meta is None:
        try:
            obj = json.loads(value)
        except json.JSONDecodeError as e:
            raise BrowserProfileCorruptedError(
                f"Browser profile '{profile_name}' is not valid JSON"
            ) from e
        if not isinstance(obj, dict):
            raise BrowserProfileCorruptedError(
                f"Browser profile '{profile_name}' is not a storage state object"
            )
        return obj

    generation = meta["generation"]
    chunk_count = meta["chunk_count"]
    if chunk_count > BROWSER_PROFILE_MAX_CHUNK_COUNT:
        raise BrowserProfileCorruptedError(
            f"Browser profile '{profile_name}' metadata is malformed"
        )
    chunks: list[str] = []
    for i in range(chunk_count):
        chunk = _profile_get_password(service, f"{profile_name}:{generation}:{i}")
        if chunk is None:
            raise BrowserProfileCorruptedError(
                f"Browser profile '{profile_name}' is missing chunk {i}"
            )
        chunks.append(chunk)

    try:
        raw = base64.b64decode("".join(chunks), validate=True)
    except (ValueError, TypeError) as e:
        raise BrowserProfileCorruptedError(
            f"Browser profile '{profile_name}' contains invalid base64 data"
        ) from e

    if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
        raise BrowserProfileCorruptedError(
            f"Browser profile '{profile_name}' failed checksum validation"
        )

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BrowserProfileCorruptedError(
            f"Browser profile '{profile_name}' payload is not valid JSON"
        ) from e
    if not isinstance(obj, dict):
        raise BrowserProfileCorruptedError(
            f"Browser profile '{profile_name}' payload is not a storage state object"
        )
    return obj


def delete_browser_profile(workspace_id: str, profile_name: str) -> None:
    service = _profile_service(workspace_id)
    value = _profile_get_password(service, profile_name)
    if value is None:
        return
    try:
        meta = _profile_parse_meta(value)
    except BrowserProfileStorageError:
        meta = None
    if meta is not None:
        _profile_cleanup_generation(
            service, profile_name, meta["generation"], meta["chunk_count"]
        )
    _safe_delete(service, profile_name)


def has_browser_profile(workspace_id: str, profile_name: str) -> bool:
    try:
        return get_browser_profile(workspace_id, profile_name) is not None
    except BrowserProfileStorageError:
        return False


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    list_models_path: str
    model_prefix: str


SUPPORTED_PROVIDERS: dict[str, ProviderConfig] = {
    "openrouter": ProviderConfig(
        base_url="https://openrouter.ai/api/v1",
        list_models_path="/models",
        model_prefix="openrouter:",
    ),
    "nim": ProviderConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        list_models_path="/models",
        model_prefix="openai:",
    ),
    "together": ProviderConfig(
        base_url="https://api.together.xyz/v1",
        list_models_path="/models",
        model_prefix="openai:",
    ),
}
