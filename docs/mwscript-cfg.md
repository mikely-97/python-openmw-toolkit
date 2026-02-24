# MWScript & openmw.cfg

## MWScript Reference

MWScript is the classic Morrowind scripting language. Scripts are stored in
`SCPT` records with source in `SCTX` and (optionally) compiled bytecode in `SCDT`.
OpenMW can compile source-only scripts on load.

```
Begin script_id

short local_var
float local_float

if ( GetItemCount "item_id" > 0 )
    MessageBox "You have the item!"
    set local_var to 1
endif

; Attach to NPC/CONT/DOOR via SCRI subrecord on those records
; Global scripts: listed in SCPT, auto-run via StartScripts mechanism

End
```

Common functions: `MessageBox`, `GetItemCount`, `AddItem`, `RemoveItem`,
`GetCurrentAIPackage`, `AITravel`, `AIFollow`, `AIWander`, `StartScript`,
`StopScript`, `SetGlobal`, `GetGlobal`, `MenuMode`, `OnActivate`,
`PCGetRace`, `PCGetClass`, `PCGetFaction`.

Stat modification (use these, NOT SetAttribute/SetSkill — those don't exist):
```
Player->ModAttribute Speed 70     ; adds 70 to Speed base value
Player->ModSkill Athletics 80     ; adds 80 to Athletics base value
```

## openmw.cfg Load Order

```ini
data="path/to/game_template"
data="path/to/my_addon_folder"

content=template.omwgame        ; base game (must come first)
content=my_addon.omwaddon       ; your addon
content=my_addon.omwscripts     ; your Lua scripts (separate line!)
```

- `data=` paths form the VFS; assets (meshes, textures) looked up here.
- `content=` entries load in order; later files override earlier ones.
- `.omwscripts` must be a **separate** `content=` entry from `.omwaddon`.

## Which OpenMW to use

**Use the Flatpak release** (`org.openmw.OpenMW`), not the system package.

The system package ships an `osgdb_dae.so` incompatible with OpenMW 0.50's VFS —
every `.dae` fails with `Extra content at the end of the document`. The Flatpak
bundles matching osg+collada-dom.

```bash
flatpak run --command=openmw org.openmw.OpenMW [args...]
```

Flatpak config: `~/.var/app/org.openmw.OpenMW/config/openmw/`

## Hub World openmw.cfg

```ini
encoding=win1252

data="/path/to/example-suite/game_template/data"
data="/path/to/example-suite/the_hub/data"
data="/path/to/example-suite/example_animated_creature/data"
data="/path/to/example-suite"
data="/path/to/python-openmw-toolkit/hub_world/data"

content=template.omwgame
content=the_hub.omwaddon
content=hub_world.omwaddon
content=hub_world.omwscripts
```

## Required settings.cfg for the Game Template

Add to `~/.config/openmw/settings.cfg`. Without these OpenMW crashes on new-game:
`Failed to start a new game: Resource 'meshes/base_anim.nif' not found`

```ini
[Models]
xbaseanim           = meshes/BasicPlayer.dae
baseanim            = meshes/BasicPlayer.dae
xbaseanim1st        = meshes/BasicPlayer.dae
baseanimkna         = meshes/BasicPlayer.dae
baseanimkna1st      = meshes/BasicPlayer.dae
xbaseanimfemale     = meshes/BasicPlayer.dae
baseanimfemale      = meshes/BasicPlayer.dae
baseanimfemale1st   = meshes/BasicPlayer.dae
xargonianswimkna    = meshes/BasicPlayer.dae
xbaseanimkf         = meshes/BasicPlayer.dae
xbaseanim1stkf      = meshes/BasicPlayer.dae
xbaseanimfemalekf   = meshes/BasicPlayer.dae
xargonianswimknakf  = meshes/BasicPlayer.dae
skyatmosphere       = meshes/sky_atmosphere.dae
skyclouds           = meshes/sky_clouds_01.osgt
skynight01          = meshes/sky_night_01.osgt

[Game]
default actor pathfind half extents = 15.656299591064453125 15.656299591064453125 69.1493988037109375
```
