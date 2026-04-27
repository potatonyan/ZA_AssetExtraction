
<a id="orgaa21c50"></a>

# Asset Extraction automation
 `Usage: python build.py <input.cue> [output_folder]`
Run on legally acquired files.

**Mame-tools**: `chdman` used to combine `bincue` into `.chd` format:

-   `` chdman createcd -i "[INPUT_FILE].cue" -o "[OUTPUT_FILE].chd" ``
-   **Ensure** `.bin` is in the same location as the `.cue` file!
-   Probably could make this more flexible and just point to the dir, not specifically the .cue
-   Having it check for both `.bin/cue` files.

**python script**: `chd_to_dat.py`

-   `` `python chd_to_dat.py "[OUTPUT_FILE].chd" ``
-   Should output to same dir -> `[OUTPUT_FILE].dat`

**python script**: `ZAassetExtraction.py`

-   **Usage**: python ZAassetExtraction.py <input.dat> [output<sub>folder</sub>]
-   <span class="underline">da big one</span>
-   There will be Errors:
    -   `Malformed animation table: expected 148 bytes, found 146`
    -   `hasSprites false when sprite is present. Cell: s501`
    -   `Weapons folder places items incorrectly/is a mess`
-   Sprites created via cell have worse transparency than weapons in weapons folders

