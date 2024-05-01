"""
We define a simple config system that can handle the merging of 2 configs.

The config allow to describe how to build a software environment using a
package manager.
"""
import copy
import dataclasses
from typing import Any
from typing import Optional

from ._merging import refacto_dict
from ._merging import deepmerge_dicts
from ._merging import MergeRule
from kenvmanager.managers import get_package_manager_class
from kenvmanager.managers import PackageManagerBase


class PackageManagersSerialized(dict[str, dict]):
    """
    A PackageManager serialized as a dict structure.

    The dict structure include tokens that need to be resolved.
    """

    def __add__(
        self,
        other: "PackageManagersSerialized",
    ) -> "PackageManagersSerialized":
        if not isinstance(other, PackageManagersSerialized):
            raise TypeError(
                f"Cannot concatenate object of type {type(other)} with {type(self)}"
            )

        def key_resolve(key: str):
            return key.removeprefix("+=")

        def merge_rule(key: str):
            return MergeRule.append if key.startswith("+=") else MergeRule.override

        new_content = deepmerge_dicts(
            over_content=other,
            base_content=self,
            key_resolve_callback=key_resolve,
            merge_rule_callback=merge_rule,
        )
        return PackageManagersSerialized(new_content)

    def get_resolved(self) -> dict[str, dict]:
        """
        Get the dict structure with all tokens resolved.

        Without tokens, the returned object is not a PackageManagersProfile instance anymore.
        """

        def process_pair(key: str, value: str):
            new_key = key.removeprefix("+=")
            return new_key, value

        new_content = refacto_dict(
            src_dict=self,
            callback=process_pair,
            recursive=True,
        )
        return new_content

    def unserialize(self) -> list[PackageManagerBase]:
        """
        Unserialize the dict structure to PackageManager instances.
        """
        managers: list[PackageManagerBase] = []
        content = self.get_resolved()
        for manager_name, manager_config in content.items():
            manager_class = get_package_manager_class(manager_name)
            if not manager_class:
                raise ValueError(
                    f"No manager class registred with the name <{manager_name}>"
                )
            manager = manager_class.from_dict(manager_config)
            managers.append(manager)

        return managers


@dataclasses.dataclass
class EnvironmentProfile:
    identifier: str
    version: str
    base: Optional["EnvironmentProfile"]
    managers: PackageManagersSerialized

    @classmethod
    def from_dict(cls, serialized: dict) -> "EnvironmentProfile":
        """
        Generate a profile instance from a serialized dict object.
        """
        identifier: str = serialized["identifier"]
        version: str = serialized["version"]
        base: Optional["EnvironmentProfile"] = serialized.get("base", None)
        managers: PackageManagersSerialized = serialized["managers"]

        return EnvironmentProfile(
            identifier=identifier,
            version=version,
            base=base,
            managers=managers,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert a profile instance to a serialized dict object.
        """
        serialized = {
            "identifier": self.identifier,
            "version": self.version,
        }
        if self.base:
            serialized["base"] = self.base

        serialized["managers"] = copy.deepcopy(self.managers)
        return serialized

    def get_merged_profile(self):
        managers = self.managers
        if self.base:
            managers = self.base.get_merged_profile().managers + managers

        return EnvironmentProfile(
            identifier=self.identifier,
            version=self.version,
            base=None,
            managers=managers,
        )
