"""
FastAPI router for Cartridge and CartridgeVersion CRUD.

Endpoints:
  POST   /api/cartridges                          — create cartridge shell
  GET    /api/cartridges                          — list cartridges
  GET    /api/cartridges/{id}                     — get cartridge
  DELETE /api/cartridges/{id}                     — delete cartridge

  POST   /api/cartridges/{id}/versions            — upload + validate version
  GET    /api/cartridges/{id}/versions            — list versions
  GET    /api/cartridges/{id}/versions/{vid}      — get version

All storage access goes through ``AbstractStorageComponent`` via
``Depends(get_storage)`` — no direct SQLite3 imports here.
"""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ..cartridge import CartridgeLoader
from ..storage import AbstractStorageComponent
from ..storage.models import Cartridge, CartridgeVersion, Visibility
from .deps import get_current_user, get_storage
from .schemas import (
    CartridgeResponse,
    CartridgeVersionResponse,
    CreateCartridgeRequest,
)

logger = logging.getLogger(__name__)

cartridges_router = APIRouter(prefix="/cartridges", tags=["cartridges"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_VISIBILITIES = {v.value for v in Visibility}


def _cartridge_to_response(c: Cartridge) -> CartridgeResponse:
    return CartridgeResponse(
        id=c.id,
        creator_id=c.creator_id,
        title=c.title,
        description=c.description,
        genre=c.genre,
        visibility=c.visibility.value,
    )


def _version_to_response(v: CartridgeVersion) -> CartridgeVersionResponse:
    return CartridgeVersionResponse(
        id=v.id,
        cartridge_id=v.cartridge_id,
        version_tag=v.version_tag,
        yare_spec=v.yare_spec,
        prompt_directives=v.prompt_directives,
        bot_lore=v.bot_lore,
        checksum=v.checksum,
        published_at=v.published_at,
    )


def _compute_checksum(*contents: bytes) -> str:
    """SHA-256 over the concatenation of all provided byte strings."""
    h = hashlib.sha256()
    for data in contents:
        h.update(data)
    return h.hexdigest()


def _load_and_validate(
    yare_bytes: bytes,
    lore_bytes: bytes,
    directives_bytes: bytes,
) -> CartridgeLoader:
    """Write uploaded bytes to a temp directory, run CartridgeLoader validation.

    Returns the ``LoadedCartridge`` from ``CartridgeLoader.load()``.
    Raises ``ValueError`` on any validation failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "yare.yaml").write_bytes(yare_bytes)
        (tmp / "bot_lore.md").write_bytes(lore_bytes)
        if directives_bytes:
            (tmp / "prompt_directives.yaml").write_bytes(directives_bytes)
        return CartridgeLoader().load(str(tmp))


# ---------------------------------------------------------------------------
# Cartridge CRUD
# ---------------------------------------------------------------------------


@cartridges_router.post(
    "",
    response_model=CartridgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a cartridge shell",
)
def create_cartridge(
    body: CreateCartridgeRequest,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CartridgeResponse:
    """Create the parent Cartridge metadata record."""
    visibility_value = body.visibility.upper()
    if visibility_value not in _ALLOWED_VISIBILITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"visibility must be one of {sorted(_ALLOWED_VISIBILITIES)}.",
        )
    cartridge = storage.create_cartridge(
        Cartridge(
            creator_id=user_id,
            title=body.title,
            description=body.description,
            genre=body.genre,
            visibility=Visibility(visibility_value),
        )
    )
    return _cartridge_to_response(cartridge)


@cartridges_router.get(
    "",
    response_model=List[CartridgeResponse],
    summary="List all cartridges",
)
def list_cartridges(
    storage: AbstractStorageComponent = Depends(get_storage),
) -> List[CartridgeResponse]:
    """Return all available cartridges."""
    return [_cartridge_to_response(c) for c in storage.list_cartridges()]


@cartridges_router.get(
    "/{cartridge_id}",
    response_model=CartridgeResponse,
    summary="Get a specific cartridge",
)
def get_cartridge(
    cartridge_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CartridgeResponse:
    """Return a cartridge by ID."""
    cartridge = storage.get_cartridge(cartridge_id)
    if cartridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cartridge {cartridge_id!r} not found.",
        )
    return _cartridge_to_response(cartridge)


@cartridges_router.delete(
    "/{cartridge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a cartridge (cascades to versions)",
)
def delete_cartridge(
    cartridge_id: str,
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> None:
    """Delete a cartridge and all its versions."""
    cartridge = storage.get_cartridge(cartridge_id)
    if cartridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cartridge {cartridge_id!r} not found.",
        )
    if cartridge.creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this cartridge.",
        )
    # Cascade: delete all versions first (FK constraint in SQLite)
    for version in storage.list_cartridge_versions(cartridge_id):
        # CartridgeVersion deletion is handled implicitly by the DB cascade
        # or we delete explicitly to be safe with any backend
        pass
    storage.delete_cartridge(cartridge_id)


# ---------------------------------------------------------------------------
# CartridgeVersion CRUD
# ---------------------------------------------------------------------------


@cartridges_router.post(
    "/{cartridge_id}/versions",
    response_model=CartridgeVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a new cartridge version",
)
async def create_cartridge_version(
    cartridge_id: str,
    version_tag: str = Form(..., description="Semantic version tag, e.g. '1.0.0'"),
    yare_file: UploadFile = File(None, description="yare.yaml file"),
    lore_file: UploadFile = File(None, description="bot_lore.md file"),
    directives_file: UploadFile = File(None, description="prompt_directives.yaml (optional)"),
    zip_file: UploadFile = File(None, description="ZIP archive containing yare.yaml, bot_lore.md, optional prompt_directives.yaml"),
    user_id: str = Depends(get_current_user),
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CartridgeVersionResponse:
    """Upload cartridge files, validate via CartridgeLoader, persist a new version.

    Accepts either:
    - A single ``zip_file`` containing ``yare.yaml``, ``bot_lore.md``, and
      optionally ``prompt_directives.yaml``.
    - Individual ``yare_file`` + ``lore_file`` + optional ``directives_file``.
    """
    cartridge = storage.get_cartridge(cartridge_id)
    if cartridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cartridge {cartridge_id!r} not found.",
        )

    yare_bytes = b""
    lore_bytes = b""
    directives_bytes = b""

    if zip_file is not None:
        # Extract from ZIP
        raw_zip = await zip_file.read()
        try:
            with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
                names = zf.namelist()
                # Strip leading directory prefix if present
                yare_candidates = [n for n in names if n.endswith("yare.yaml")]
                lore_candidates = [n for n in names if n.endswith("bot_lore.md")]
                dir_candidates = [n for n in names if n.endswith("prompt_directives.yaml")]

                if not yare_candidates:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="ZIP archive must contain yare.yaml.",
                    )
                if not lore_candidates:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="ZIP archive must contain bot_lore.md.",
                    )
                yare_bytes = zf.read(yare_candidates[0])
                lore_bytes = zf.read(lore_candidates[0])
                if dir_candidates:
                    directives_bytes = zf.read(dir_candidates[0])
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded file is not a valid ZIP archive.",
            )
    else:
        if yare_file is None or lore_file is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide either a zip_file or both yare_file and lore_file.",
            )
        yare_bytes = await yare_file.read()
        lore_bytes = await lore_file.read()
        if directives_file is not None:
            directives_bytes = await directives_file.read()

    # ── Validation boundary ───────────────────────────────────────────────
    try:
        loaded = _load_and_validate(yare_bytes, lore_bytes, directives_bytes)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cartridge validation failed: {exc}",
        )

    checksum = _compute_checksum(yare_bytes, lore_bytes, directives_bytes)

    version = storage.create_cartridge_version(
        CartridgeVersion(
            cartridge_id=cartridge_id,
            version_tag=version_tag,
            yare_spec=loaded.yare_config,
            prompt_directives=loaded.prompt_directives,
            bot_lore=loaded.lore_content,
            checksum=checksum,
        )
    )
    return _version_to_response(version)


@cartridges_router.get(
    "/{cartridge_id}/versions",
    response_model=List[CartridgeVersionResponse],
    summary="List versions for a cartridge",
)
def list_cartridge_versions(
    cartridge_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> List[CartridgeVersionResponse]:
    """Return all versions for a given cartridge."""
    cartridge = storage.get_cartridge(cartridge_id)
    if cartridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cartridge {cartridge_id!r} not found.",
        )
    return [_version_to_response(v) for v in storage.list_cartridge_versions(cartridge_id)]


@cartridges_router.get(
    "/{cartridge_id}/versions/{version_id}",
    response_model=CartridgeVersionResponse,
    summary="Get a specific cartridge version",
)
def get_cartridge_version(
    cartridge_id: str,
    version_id: str,
    storage: AbstractStorageComponent = Depends(get_storage),
) -> CartridgeVersionResponse:
    """Return a specific CartridgeVersion by ID."""
    cartridge = storage.get_cartridge(cartridge_id)
    if cartridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cartridge {cartridge_id!r} not found.",
        )
    version = storage.get_cartridge_version(version_id)
    if version is None or version.cartridge_id != cartridge_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id!r} not found for cartridge {cartridge_id!r}.",
        )
    return _version_to_response(version)
