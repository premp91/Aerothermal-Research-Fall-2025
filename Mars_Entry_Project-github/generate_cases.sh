# This code will automatically generate cases based on the .STEP file in the step_files directory.
# Author: Kevin Tang

#!/bin/bash
# --- Configuration ---
# Auto-locate paths relative to the script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEP_DIR="$SCRIPT_DIR/step_files"
OUTPUT_DIR="$SCRIPT_DIR/cases"
TEMPLATE_CSM="$SCRIPT_DIR/templates/template.csm"
TEMPLATE_PY="$SCRIPT_DIR/templates/template.py"

mkdir -p "$OUTPUT_DIR" # If /cases doesn't exist

# Check if template files exist
if [ ! -f "$TEMPLATE_CSM" ]; then
    echo "Error: Template file $TEMPLATE_CSM not found"
    exit 1
fi
if [ ! -f "$TEMPLATE_PY" ]; then
    echo "Error: Template file $TEMPLATE_PY not found"
    exit 1
fi

# Loop over each STEP file (case-insensitive)
found_files=false
for filepath in "$STEP_DIR"/*.STEP "$STEP_DIR"/*.step; do
    [ -f "$filepath" ] || continue  # Skip if file doesn't exist
    found_files=true
    
    filename=$(basename "$filepath")       
    casename="${filename%.*}"             
    case_dir="$OUTPUT_DIR/$casename"
    mkdir -p "$case_dir"
    
    # --update-py mode: regenerate only the template.py script if change is made
    if [ "$1" == "--update-py" ]; then
        sed -e "s/__CSM_FILENAME__/$casename.csm/g" \
            -e "s/__PROBLEM_NAME__/$casename/g" \
            -e "s/__FUN3D_PROJECT__/$casename/g" \
            "$TEMPLATE_PY" > "$case_dir/run_$casename.py"
        echo "Updated Python script for $casename"
        continue
    fi
    
    # Copy the STEP file
    cp "$filepath" "$case_dir/"
    
    # Generate .csm file
    sed "s/__CASENAME__/$casename/g" "$TEMPLATE_CSM" > "$case_dir/$casename.csm"

    
    # Generate .py script
    # Full sed block for pyCAPS file
    sed -e "s/__CSM_FILENAME__/$casename.csm/g" \
        -e "s/__PROBLEM_NAME__/$casename/g" \
        -e "s/__FUN3D_PROJECT__/$casename/g" \
        "$TEMPLATE_PY" > "$case_dir/run_$casename.py"
        
    # Generate input files
    # Generate AIM parameters (config.json)
  cat > "$case_dir/config.json" <<EOF
{
  "Mesh_Length_Factor": 0.1,
  "max_scale": 0.5,
  "min_scale": 0.001,
  "abs_min_scale": 0.0001,
  "ff_cdfr": 1.5,
  "edgeWeight": 1.0,
  "blunt_scaleFactor": 1.0,
  "farfield_scaleFactor": 1.0,
  "dim_input_type": "dimensional-SI",
  "gridlength_conversion": 0.025,
  "Re": [...],
  "velocity": [...] [m/s],
  "Mach": [...],
  "density": [...] [kg/m^3],
  "temperature": [...],
  "temperature_units": "Kelvin",
  "Alpha": [...],
  "Beta": 0.0,
  "Equation_Type": "generic",
  "Viscous": "inviscid",
  "chemical_kinetics": "finite-rate",
  "thermal_energy_model": "non-equilb",
  "prandtlnumber_molecular": [...],
  "gas_radiation": "off",
  "rad_use_impl_lines": false,
  "multi_component_diff": false,
  "Num_Iter": 7500,
  "CFL_Schedule": [0.1, 10],
  "CFL_Schedule_Iter": [1, 100],
  "Restart_Read": "off",
  "Flux_Construction": "stvd",
  "Flux_Construction_LHS": "consistent",
  "Flux_Limiter": "minmod_gg",
  "Freeze_Limiter": 5000,
  "Re_min_vswch": 50,
  "Re_max_vswch": 500,
  "Adaptive_Shock_Sensor": ture,
  "First_Order_Iterations": 2500,
  "Overwrite_NML": true,
  "Use_Python_NML": true,
  "np": 10,
  "Species_Dir": "/home/kevinytang/Mars_Entry_Project-github/GasData"
}
EOF

done

if [ "$found_files" = false ]; then
    echo "Warning: No STEP files found in $STEP_DIR"
else
    echo "Case folders and files generated in $OUTPUT_DIR"
fi
