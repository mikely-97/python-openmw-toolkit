"""addon — High-level builder API for OpenMW addons.

Usage
-----
    from addon import AddonBuilder

    addon = AddonBuilder(description="My addon", masters=["template.omwgame"])
    addon.add_global("MyMod_Version", type="short", value=1)
    addon.save("mymod.omwaddon")
"""
from .builder import AddonBuilder

__all__ = ["AddonBuilder"]
