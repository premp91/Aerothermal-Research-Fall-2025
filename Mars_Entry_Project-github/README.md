CAPS Batch Case Generator & Runner
==================================

This project automates the generation, setup, and execution of CFD-ready geometries using CAPS, AFLR4/AFLR3, and FUN3D. It supports batch processing of .STEP geometries and allows easy, consistent modification of input parameters.

Directory Structure
-------------------

```text
project_root/
  generate_cases.sh
  update_config.py
  templates/
    template.csm
    template.py
  step_files/
  cases/
    <casename>/
      <casename>.STEP
      <casename>.csm
      config.json
      run_<casename>.py
```

Getting Started
---------------

1. Place your `.STEP` files in the `step_files/` folder.

2. Move to the main folder.

```bash
cd ~/Mars_Entry_Project
```

3. Generate case folders. 

```bash
./generate_cases.sh
```

Note: each `.STEP` file becomes a case folder in `cases/`.

How to Run a Case
-----------------

1. Open ESP 1.27 shell environment

2. Access the desired case

```bash
cd [desired/case/directory]
```

3. Open the python file in the web GUI 

```bash
serveESP [filename].py
```

4. Click 'save and run'

This runs:
- AFLR4 surface meshing
- AFLR3 volume meshing
- FUN3D setup and execution

Modify Input Parameters
-----------------------

Each case has its own `config.json`. Example:

```json
{
  "Mach": 1.0,
  "Alpha": 30.0,
  "Mesh_Length_Factor": 0.5,
  "CFL_Schedule": [0.5, 3.0]
}
```

To change parameters across all cases, update the values in 'update_config.py'. Then, use:

```bash
python3 update_config.py
```

Viewing Results
---------------
The fun3d result can be found inside the case folder:
```bash
[folder with case name]/Scratch/fun3d
```

Regenerating Files
------------------

Update only the run Python scripts:

```bash
./generate_cases.sh --update-py
```

This uses the current `template.py` and updates `run_<casename>.py` in all case folders. It does not touch STEP, CSM, or config files.

To fully regenerate all case files (destructive):

```bash
rm -rf cases/
./generate_cases.sh
```

Purpose of Key Files
--------------------

File / Folder            | Purpose
------------------------ | -----------------------------------------------------
generate_cases.sh        | Main case generator; applies templates to each .STEP
update_config.py         | Modify config.json fields across all cases
template.py              | Reusable pyCAPS script with placeholders
template.csm             | Base geometry import logic with tagged attributes
config.json              | Case-specific inputs (Mach, Alpha, mesh controls)
run_<case>.py            | Executable script to run meshing + FUN3D using pyCAPS

Tips
----

- Keep template logic generic; let config.json handle values like Mach, Alpha, iterations.
- Version-control your `templates/`, not your `cases/`.
- Validate `.json` with `jq`: `jq . cases/<casename>/config.json`
