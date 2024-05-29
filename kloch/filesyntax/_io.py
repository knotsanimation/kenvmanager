import logging
import os
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import yaml

from ._profile import LauncherSerializedDict
from ._profile import EnvironmentProfile


LOGGER = logging.getLogger(__name__)


KENV_PROFILE_PATH_ENV_VAR: str = "KENV_PROFILE_PATHS"
"""
Name of the user-editable environment variable to add profile locations.
"""

_PROFILE_LOCATIONS_INTERNAL: List[Path] = []

KENV_PROFILE_MAGIC = "kloch_profile"
KENV_PROFILE_VERSION = 2


def is_file_environment_profile(file_path: Path) -> bool:
    """
    Return True if the given file is an Environment Profile.

    Args:
        file_path: filesystem path to an existing file
    """
    if not file_path.suffix == ".yml":
        return False

    with file_path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file)

    if not content:
        return False

    return content.get("__magic__", "").startswith(KENV_PROFILE_MAGIC)


def add_profile_location(location: Path):
    """
    Add a location where profile can be found.

    Locations added thorugh here are appended to the environment defined locations.

    Args:
        location: filesystem path to an existing directory.
    """
    global _PROFILE_LOCATIONS_INTERNAL
    if location in _PROFILE_LOCATIONS_INTERNAL:
        return
    _PROFILE_LOCATIONS_INTERNAL.append(location)


def get_profile_locations() -> List[Path]:
    """
    Get the user-defined directories where profile are stored.

    Returns:
         list of filesystem path to directory that might exist
    """
    locations = os.getenv(KENV_PROFILE_PATH_ENV_VAR)
    if not locations and not _PROFILE_LOCATIONS_INTERNAL:
        return []

    if locations:
        locations = [
            Path(location).absolute() for location in locations.split(os.pathsep)
        ]
        locations += _PROFILE_LOCATIONS_INTERNAL
    else:
        locations = list(_PROFILE_LOCATIONS_INTERNAL)

    return locations


def get_all_profile_file_paths(locations: Optional[List[Path]] = None) -> List[Path]:
    """
    Get all the environment-profile file paths as registred by the user.

    Args:
        locations: list of filesystem path to directory that might exist
    """
    locations = locations or get_profile_locations()
    return [
        path
        for location in locations
        for path in location.glob("*.yml")
        if is_file_environment_profile(path)
    ]


def _get_profile_identifier(file_path: Path) -> str:
    with file_path.open("r", encoding="utf-8") as file:
        asdict: Dict = yaml.safe_load(file)
    return asdict["identifier"]


def get_profile_file_path(
    profile_id: str,
    profile_locations: Optional[List[Path]] = None,
) -> List[Path]:
    """
    Get the filesystem location to the profile(s) with the given name.

    Args:
        profile_id: identifier that must match returned profiles.
        profile_locations:
            list of filesystem path to potential existing directories containing profiles.

    Returns:
        list of filesystem path to existing files . Might be empty.
    """
    profile_paths = get_all_profile_file_paths(locations=profile_locations)
    profiles: List[Path] = [
        path for path in profile_paths if _get_profile_identifier(path) == profile_id
    ]
    return profiles


def read_profile_from_file(
    file_path: Path,
    profile_locations: Optional[List[Path]] = None,
) -> EnvironmentProfile:
    """
    Generate an instance from a serialized file on disk.

    Raises error if the file is not built properly.

    Args:
        file_path:
            filesystem path to an existing valid profile file.
        profile_locations:
            list of filesystem path to potential existing directories containing profiles.
    """
    with file_path.open("r", encoding="utf-8") as file:
        asdict: Dict = yaml.safe_load(file)

    profile_version = int(asdict["__magic__"].split(":")[-1])
    if not profile_version == KENV_PROFILE_VERSION:
        raise SyntaxError(
            f"Cannot read profile with version <{profile_version}> while current "
            f"API version is <{KENV_PROFILE_VERSION}>."
        )
    del asdict["__magic__"]

    base_name: Optional[str] = asdict.get("base", None)
    if base_name:
        base_paths = get_profile_file_path(
            base_name,
            profile_locations=profile_locations,
        )
        if len(base_paths) >= 2:
            raise ValueError(
                f"Found multiple profile with identifier '{base_name}' "
                f"specified from profile '{file_path}': {base_paths}."
            )
        if not base_paths:
            raise ValueError(
                f"No profile found with identifier '{base_name}' "
                f"specified from profile '{file_path}'."
            )

        base_profile = read_profile_from_file(file_path=base_paths[0])
        asdict["base"] = base_profile

    launchers = LauncherSerializedDict(asdict["launchers"])
    asdict["launchers"] = launchers

    profile = EnvironmentProfile.from_dict(asdict)
    return profile


def read_profile_from_id(
    profile_id: str,
    profile_locations: Optional[List[Path]] = None,
) -> EnvironmentProfile:
    """
    Generate a profile instance from a serialized file on disk retrieved using the given identifier.

    Raises error if the profile file is not built properly.

    This a convenient function wrapping :func:`read_profile_from_file` and
    :func:`get_profile_file_path` and assuming that no profile with the same
    identifier exist in the locations.

    Args:
        profile_id: identifier that must match the profile.
        profile_locations:
            list of filesystem path to potential existing directories containing profiles.

    Returns:
        a profile instance
    """
    profile_paths = get_profile_file_path(
        profile_id=profile_id,
        profile_locations=profile_locations,
    )
    profile = read_profile_from_file(
        file_path=profile_paths[0],
        profile_locations=profile_locations,
    )
    return profile


def serialize_profile(
    profile: EnvironmentProfile,
    profile_locations: Optional[List[Path]] = None,
) -> str:
    """
    Convert the instance to a serialized dictionnary intended to be written on disk.
    """
    asdict = {"__magic__": f"{KENV_PROFILE_MAGIC}:{KENV_PROFILE_VERSION}"}
    asdict.update(profile.to_dict())

    base_profile: Optional[EnvironmentProfile] = asdict.get("base", None)
    if base_profile:
        base_path = get_profile_file_path(
            profile_id=base_profile.identifier,
            profile_locations=profile_locations,
        )
        if not base_path:
            raise ValueError(
                f"Base profile {base_profile.identifier} is not registred on disk."
            )
        asdict["base"] = base_profile.identifier

    # remove custom class wrapper
    asdict["launchers"] = dict(asdict["launchers"])

    return yaml.dump(asdict, sort_keys=False)


def write_profile_to_file(
    profile: EnvironmentProfile,
    file_path: Path,
    profile_locations: Optional[List[Path]] = None,
    check_valid_id: bool = True,
) -> Path:
    """
    Convert the instance to a serialized file on disk.

    Args:
        profile: profile instance to write to disk
        file_path:
            filesystem path to a file that might exist.
            parent location is expected to exist.
        check_valid_id:
            if True, ensure the identifier of the profile is unique among all ``profile_locations``
        profile_locations:
            list of filesystem path to potential existing directories containing profiles.
    """
    if check_valid_id:
        profile_paths = get_profile_file_path(
            profile_id=profile.identifier,
            profile_locations=profile_locations,
        )
        if profile_paths and file_path not in profile_paths:
            raise ValueError(
                f"Found multiple profile with identifier '{profile.identifier}'."
            )

    serialized = serialize_profile(profile, profile_locations=profile_locations)

    file_path.write_text(serialized)
    return file_path
