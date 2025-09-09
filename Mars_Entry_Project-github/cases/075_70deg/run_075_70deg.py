# Import pyCAPS module
import pyCAPS
import os
import json
import shutil

def fbool(x: bool) -> str:
    return ".true." if bool(x) else ".false."

#######################################
##        Load input parameters      ##
#######################################
with open("config.json", "r") as f:
    params = json.load(f)

#######################################
##        Build Geometry             ##
#######################################
filename = "075_70deg.csm"
print(f'\n==> Loading geometry from file "{filename}"...')
capsProblem = pyCAPS.Problem(problemName="075_70deg",
                             capsFile=filename,
                             outLevel=1)

#######################################
##        Build surface mesh         ##
#######################################
print('\n==> Creating AFLR4 AIM')
aflr4 = capsProblem.analysis.create(aim="aflr4AIM", name="aflr4")

# Hypersonic-friendly defaults; can be overridden in config.json
aflr4.input.Mesh_Length_Factor = params.get("Mesh_Length_Factor")
aflr4.input.max_scale          = params.get("max_scale")
aflr4.input.ideal_min_scale    = params.get("min_scale")
aflr4.input.ff_cdfr            = params.get("ff_cdfr")  # push farfield way out

# Local controls + farfield tag
aflr4.input.Mesh_Sizing = {
    "blunt":    {"edgeWeight": params.get("edgeWeight"),
                 "scaleFactor": params.get("blunt_scaleFactor")},
    "Farfield": {
        "bcType": "Farfield",
        "scaleFactor": params.get("farfield_scaleFactor")
    }
}

print('\n==> Running AFLR4 (pre/post-analysis)')
aflr4.runAnalysis()

#######################################
##        Build volume mesh          ##
#######################################
print('\n==> Creating AFLR3 AIM')
aflr3 = capsProblem.analysis.create(aim="aflr3AIM", name="aflr3")

# Link AFLR4 surface mesh to AFLR3 (parent/child)
aflr3.input["Surface_Mesh"].link(aflr4.output["Surface_Mesh"])

# Optional: verbosity and BL (keep inviscid for now)
aflr3.input.Mesh_Quiet_Flag = False
aflr3.input.Mesh_Sizing = {"Farfield": {"bcType": "Farfield"}}

print("==> Running AFLR3 (pre/post-analysis)")
aflr3.runAnalysis()

#######################################
##         Using FUN3D AIM          ##
#######################################
print('\n==> Creating FUN3D AIM')
fun3d = capsProblem.analysis.create(aim="fun3dAIM", name="fun3d")

# Project name & mesh link
fun3d.input.Proj_Name = params.get("Proj_Name", "075_70deg")
fun3d.input["Mesh"].link(aflr3.output["Volume_Mesh"])

# Namelist generation from Python
fun3d.input.Use_Python_NML = params.get("Use_Python_NML", True)
fun3d.input.Overwrite_NML  = params.get("Overwrite_NML", True)

# MPI procs
np = int(os.environ.get("FUN3D_MPI_PROCS", str(params.get("np", 4))))

########## Run FUN3D ##########
print("\n\nRunning FUN3D......")

# Write AIM-generated namelist first
fun3d.preAnalysis()

# Copy species files if it's generic gas
if params.get("Equation_Type", "").lower() in ("generic"):
    species_dir = params.get("Species_Dir")
    if species_dir and os.path.isdir(species_dir):
        print(f"==> Copying species files from {species_dir}")
        for fname in ["tdata", "species_thermo_data", "species_transp_data_0", "kinetic_data"]:
            src = os.path.join(species_dir, fname)
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(fun3d.analysisDir, fname))
            else:
                print(f"  (warn) missing: {src}")
    else:
        print("  (info) Species_Dir not set or not found; skipping species copy.")

# ---- Patch extra blocks into fun3d.nml ----
nml_path = os.path.join(fun3d.analysisDir, "fun3d.nml")
with open(nml_path, "a") as f:
    # ----Reference_physical_properties
    f.write("\&reference_physical_properties\n")
    f.write(f"  dim_input_type = '{params.get('dim_input_type')}'\n")
    f.write(f"  gridlength_conversion = '{params.get('gridlength_conversion')}'\n") # Modify according to capsMeshLength * Mesh_Length_Factor
    f.write(f"  reynolds_number = '{params.get('Re')}'\n")
    f.write(f"  velocity = '{params.get('velocity')}'\n")
    f.write(f"  density = '{params.get('density')}'\n")
    f.write(f"  temperature = '{params.get('temperature')}'\n")
    f.write(f"  angle_of_attack = '{params.get('Alpha')}'\n")
    f.write(f"  angle_of_yaw = '{params.get('Beta')}'\n")
    f.write("/\n\n")
    
    # ---- Governing equations ----
    f.write("\n&governing_equations\n")
    f.write(f"  eqn_type = '{params.get('Equation_Type')}'\n")
    f.write(f"  viscous_terms = '{params.get('Viscous')}'\n")
    f.write(f"  chemical_kinetics = '{params.get('chemical_kinetics')}'\n")
    f.write(f"  thermal_energy_model = '{params.get('thermal_energy_model')}'\n")
    f.write(f"  prandtlnumber_molecular = '{params.get('prandtlnumber_molecular')}'\n")
    f.write(f"  gas_radiation = '{params.get('gas_radiation')}'\n")
    f.write(f"  rad_use_impl_lines = {fbool(params.get('rad_use_impl_lines'))}\n")
    f.write(f"  multi_component_diff = {fbool(params.get('multi_component_diff'))}\n")
    f.write("/\n\n")

    # Iterations and CFL schedule
    fun3d.input.Num_Iter = params.get("Num_Iter")
    fun3d.input.CFL_Schedule = params.get("CFL_Schedule")
    fun3d.input.CFL_Schedule_Iter = params.get("CFL_Schedule_Iter")
    fun3d.input.Restart_Read = params.get("Restart_Read")

    # Boundary conditions (example)
    fun3d.input.Boundary_Condition = {
        "blunt": {
            "bcType": "Inviscid",
            "wallTemperature": -1  # adiabatic wall
        },
        "Farfield": {
            "bcType": "Freestream",
            "machNumber": params.get("Mach"),
            "totalTemperature": 1.0,
            "staticPressure": 1.0
        }
    }

    # ---- Inviscid flux method ----
    f.write("&inviscid_flux_method\n")
    f.write(f"  flux_construction = '{params['Flux_Construction']}'\n")
    f.write(f"  flux_construction_lhs = '{params['Flux_Construction_LHS']}'\n")
    f.write(f"  flux_limiter = '{params['Flux_Limiter']}'\n")
    f.write(f"  re_min_vswch = {float(params['Re_min_vswch'])}\n")
    f.write(f"  re_max_vswch = {float(params['Re_max_vswch'])}\n")
    f.write(f"  adaptive_shock_sensor = {fbool(params.get('Adaptive_Shock_Sensor'))}\n")
    f.write(f"  first_order_iterations = {int(params['First_Order_Iterations'])}\n")
    f.write("/\n\n")

    # Linear solver control
    f.write("&linear_solver_control\n")
    f.write("  linear_projection = .true.\n")
    f.write("/\n\n")

# Path to nodet_mpi
nodet = "/home/kevinytang/fun3d/fun3d_install/bin/nodet_mpi"
cmd = f"mpirun -np {np} {nodet} --animation_freq -1 --volume_animation_freq -1"

# Freeze limiter (optional)
freeze_limiter = params.get("Freeze_Limiter")
if freeze_limiter:
    cmd += f" --freeze_limiter {freeze_limiter}"

print("Command:", cmd)
fun3d.system(cmd)

# Post-analysis
fun3d.postAnalysis()
print("\nDone. Check Info.out, fun3d.nml, and mapbc.dat.")
