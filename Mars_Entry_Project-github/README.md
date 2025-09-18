CAPS Batch Case Generator & Runner
==================================

This project automates the generation, setup, and execution of CFD-ready geometries using CAPS, AFLR4/AFLR3, and FUN3D. It supports batch processing of .STEP geometries and allows easy, consistent modification of input parameters.

Directory Structure
-------------------

```text
project_root/
  generate_cases.sh
  update_config.py
  Pre-processing/
    EquilibriumFlowMatlab_v2.0.3 [free-stream solver]
    FreeStream.m
  Post-processing/
    Residual/
      Residual.m
      ResidualSummary.xlsx
  HelpfulDoc\
    ForHypersonics.pdf
    fun3dInstall.txt
  GasData/
    tdata
    kinetic_data
    species_thermo_data
    species_transp_data_0
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
1. Use the desired altitude with the standard atmospheric model to find T and p
  
2. Run pre-analysis script "FreeStream.m" to get density, mole fractions, viscosity, cp, thermal conductivity, velocity, and Prandtl number. Also obtain kinematic viscosity and velocity post shock for boundary layer control inputs.
  
3. Place your `.STEP` files in the `step_files/` folder.

4. Move to the main folder.

```bash
cd ~/Mars_Entry_Project
```

5. Update the directory to GasData in template.py. Input gas species based on the pre-analysis script.

6. Generate case folders. 

```bash
./generate_cases.sh
```

How to Run a Case
-----------------

1. Open ESP 1.27 shell environment

2. Change the tdata file according to the free-stream composition

3. Access the desired case

```bash
cd [desired/case/directory]
```
4. Input the variables from pre-processing into the config.json.
  4a. Calculate grid length conversion: (capMeshLength(from .csm) * meshLengthFactor(from config.json) ) / Diameter of spacecraft
   
5. Open the python file in the web GUI 

```bash
serveESP [filename].py
```

6. Click 'save and run'

This runs:
- AFLR4 surface meshing
- AFLR3 volume meshing
- FUN3D setup and execution

Running Hypersonic Cases in FUN3D with CAPS
-------------------------------------------
Hypersonic flows (Mach > 3) can cause strong shocks, expansions, and entropy/vacuum issues.
The NASA fun3d training tutorial (Session 6, Supersonic/Hypersonic Perfect Gas) lays out best practices.

1. Geometry and Mesh Setup

Push the farfield boundary far away (3–5× body radius minimum).

Use finer mesh near the bow shock and leading edges.

In config.json (AFLR4/AFLR3 settings):

```json
"Mesh_Length_Factor": 0.1,
"blunt_scaleFactor": 0.2,
"farfield_scaleFactor": 3.0,
"ff_cdfr": 3.0
```

2. FUN3D Physics Inputs

Use generic gas model:

```json
"Equation_Type": "generic",
```

Inviscid runs:

Flux schemes & limiter (patched into fun3d.nml via Python script):

```json
"Flux_Construction": "dldfss",
"Flux_Limiter": "hvanalbada"
```

3. Two-Step Iterative Strategy

Hypersonic cases almost always require a two-stage run:

• Step 1 — First-Order Startup

Change the inviscid inputs:

```json
"Num_Iter": 7500,
"First_Order_Iterations": 2500,
"Restart_Read": "off",
"CFL_Schedule": [0.1, 15],
"CFL_Schedule_Iter": [1, 100]
"Freeze_Limiter": 0,
```

Run:

```bash
python run_[Your_case].py
```

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
- For the program to work on WSL, change the template.py: 1. change min_scale to ideal_min_scale. 2. Comment out abs_min_scale. 3. Comment out aflr4.geometry.view(). 4. Change the path to nodet_mpi. 

Appendix: Install FUN3D
-----------------------

1. Prerequisites: make sure you have development tools installed
   
```bash
sudo apt update
sudo apt install build-essential gfortran gcc g++ cmake make git wget curl python3 python3-pip mpich libmpich-dev
```

3. Download the FUN3D tar.
4. Run install_fun3d.sh after updating the download location.
5. Reload environment:

```bash
source ~/.bashrc
```

7. Check installation:

```bash
which nodet_mpi
```
