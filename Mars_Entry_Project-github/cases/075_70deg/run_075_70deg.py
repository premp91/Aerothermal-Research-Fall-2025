# Import pyCAPS module
import pyCAPS
import os
import json
import shutil
import numpy as np

# =============================================================================
# Boundary layer parameter helper functions
# =============================================================================

def skin_friction_coeff(Re_x: float, flow: str = "turbulent") -> float:
    """
    Estimate skin-friction coefficient Cf for flat plate.
    Args:
        Re_x : Reynolds number based on distance x from leading edge
        flow : 'laminar' or 'turbulent'
    Returns:
        Cf : skin-friction coefficient
    """
    if flow == "laminar":
        # Laminar flat plate
        return 1.328 / np.sqrt(Re_x)
    else:
        # Turbulent flat plate
        return 0.664 * Re_x**(-0.5) * np.sqrt(2)


def first_cell_height(y_plus: float, nu: float, U_inf: float, Re_x: float, flow: str = "turbulent") -> float:
    """
    Compute first cell height Δy1 from target y+.
    Δy1 = y+ * ν / u_tau,  where  u_tau = U_inf * sqrt(Cf/2)
    """
    Cf = skin_friction_coeff(Re_x, flow)
    u_tau = U_inf * np.sqrt(Cf / 2.0)
    return y_plus * nu / u_tau


def total_BL_thickness(dy1: float, N: int, r: float) -> float:
    """
    Compute total boundary-layer prism thickness from geometric growth.
    BL_Thickness = Δy1 * (r^N - 1)/(r - 1)   (if r ≠ 1), else N*Δy1
    """
    if r <= 1.0:
        raise ValueError("Growth ratio r must be > 1.")
    return dy1 * (r**N - 1.0) / (r - 1.0)

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

# Aflr4 inputs
aflr4.input.Mesh_Length_Factor = params.get("Mesh_Length_Factor")
aflr4.input.max_scale          = params.get("max_scale")
aflr4.input.ideal_min_scale    = params.get("min_scale")
aflr4.input.ff_cdfr            = params.get("ff_cdfr")

# Assign geometric groups
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

# =============================================================================
# Compute BL parameters for AFLR3
# =============================================================================

# Freestream inputs (use post shock condition)
U_inf = float(params.get("v2"))           # m/s
nu    = float(params.get("nu2"))             # m^2/s
x_ref = float(params.get("x_ref"))             # m
Re_x  = U_inf * x_ref / nu

# BL strategy: "lowRe" (y=1)
BL_Mode = params.get("BL_Mode").lower()
y_plus_target = 1.0 if BL_Mode == "lowre" else 50.0

# Geometric growth & layers
growth_ratio = float(params.get("BL_Growth_Ratio"))
N_layers     = int(params.get("BL_Max_Layers", 40))

if N_layers < 1:
    raise ValueError("BL_Max_Layers must be >= 1.")

# Compute dy1 and total thickness in m
dy1      = first_cell_height(y_plus_target, nu, U_inf, Re_x, flow="turbulent")
BL_total = total_BL_thickness(dy1, N_layers, growth_ratio)

if dy1 <= 0.0 or BL_total <= 0.0:
    raise ValueError("Computed BL parameters are non-positive. Check inputs.")

print(f"Strategy: {BL_Mode} | Re_x={Re_x:.3e}")
print(f"dy1 (first layer height) = {dy1:.3e} m")
print(f"Total BL thickness       = {BL_total:.3e} m")

# Optional normalization: set BL_Scale_Length in config.json; leave at 1.0 for meters.
BL_scale = float(params.get("BL_Scale_Length"))
BL_Initial_Spacing_in = dy1 / BL_scale
BL_Thickness_in       = BL_total / BL_scale

#######################################
##        Build volume mesh          ##
#######################################
print('\n==> Creating AFLR3 AIM')
aflr3 = capsProblem.analysis.create(aim="aflr3AIM", name="aflr3")

# Link AFLR4 surface mesh to AFLR3 (parent/child)
aflr3.input["Surface_Mesh"].link(aflr4.output["Surface_Mesh"])

# Boundary layer control
aflr3.input.BL_Initial_Spacing = BL_Initial_Spacing_in   # meters
aflr3.input.BL_Thickness       = BL_Thickness_in         # meters
aflr3.input.BL_Max_Layers      = N_layers

# Specify prism boundary layer elements
aflr3.input.Mesh_Gen_Input_String = "-blc"

# Define groups: mark real walls as Viscous so BL layers are generated
aflr3.input.Mesh_Sizing = {
    "blunt":    {"bcType": "Viscous"},
    "Farfield": {"bcType": "Farfield"}
}

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

# Iterations and CFL schedule
fun3d.input.Num_Iter = int(params.get("Num_Iter"))
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

########## Run FUN3D ##########
print("\n\nRunning FUN3D......")

# Write AIM-generated namelist first
fun3d.preAnalysis()

# Copy species files if it's generic gas
if params.get("Equation_Type", "").lower() in ("generic"): # Update directory as needed
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

    # ---- Reference_physical_properties ----
    f.write("&reference_physical_properties\n")
    f.write(f"  dim_input_type = '{params.get('dim_input_type')}'\n")  # string
    f.write(f"  gridlength_conversion = {float(params.get('gridlength_conversion'))}\n")
    f.write(f"  reynolds_number = {float(params.get('Re'))}\n")
    f.write(f"  velocity = {float(params.get('velocity'))}\n")
    f.write(f"  density = {float(params.get('density'))}\n")
    f.write(f"  temperature = {float(params.get('temperature'))}\n")
    f.write(f"  angle_of_attack = {float(params.get('Alpha'))}\n")
    f.write(f"  angle_of_yaw = {float(params.get('Beta'))}\n")
    f.write("/\n\n")

    # ---- Governing equations ----
    f.write("&governing_equations\n")
    f.write(f"  eqn_type = '{params.get('Equation_Type')}'\n")  # string
    f.write(f"  viscous_terms = '{params.get('Viscous')}'\n")  # string
    f.write(f"  chemical_kinetics = '{params.get('chemical_kinetics')}'\n")
    f.write(f"  thermal_energy_model = '{params.get('thermal_energy_model')}'\n")
    f.write(f"  prandtlnumber_molecular = {float(params.get('prandtlnumber_molecular'))}\n")
    f.write(f"  gas_radiation = '{params.get('gas_radiation')}'\n")  # string
    f.write(f"  rad_use_impl_lines = {fbool(params.get('rad_use_impl_lines'))}\n")
    f.write(f"  multi_component_diff = {fbool(params.get('multi_component_diff'))}\n")
    f.write("/\n\n")

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

    # ---- Turbulence model ----
    f.write("&turbulent_diffusion_models\n")
    f.write(f"  turbulence_model = '{params['Turbulence_Model']}'\n")
    f.write(f"  reynolds_stress_model = '{params.get('Reynolds_Stress_Model')}'\n")
    f.write(f"  turb_compress_model = '{params.get('Turb_Compress_Model')}'\n")
    f.write(f"  prandtlnumber_turbulent = {float(params.get('Prandtl_Turbulent'))}\n")
    f.write(f"  schmidtnumber_turbulent = {float(params.get('Schmidt_Turbulent'))}\n")
    f.write("/\n\n")

    # ---- Turbulence auxiliary options ----
    f.write("&turbulence\n")
    f.write(f"  use_least_squares_gradients = {fbool(params.get('Use_Least_Squares_Gradients'))}\n")
    f.write(f"  limit_crossd = {fbool(params.get('Limit_CrossD'))}\n")
    f.write("/\n\n")

    # ---- Linear solver control ----
    f.write("&linear_solver_control\n")
    f.write("  linear_projection = .true.\n")
    f.write("/\n\n")

# Path to nodet_mpi [...] Need to update
nodet = "/home/kevinytang/fun3d/fun3d_install/fun3d/FUN3D_90/nodet_mpi"
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
