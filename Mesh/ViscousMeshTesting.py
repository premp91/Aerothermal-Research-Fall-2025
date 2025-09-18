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
        # Blasius laminar flat plate
        return 1.328 / np.sqrt(Re_x)
    else:
        # Turbulent flat plate (Schlichting / Prandtl-Schlichting)
        # NOTE: fixed sign bug here (use Re_x**(-0.2), not 1/Re_x**(-0.2))
        return 0.0592 * Re_x**(-0.2)


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
aflr4.input.min_scale          = params.get("min_scale")
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

# =============================================================================
# Compute BL parameters for AFLR3
# =============================================================================

# Freestream inputs (override in config.json if you have them there)
U_inf = float(params.get("U_inf", 200.0))           # m/s
nu    = float(params.get("nu", 1.5e-5))             # m^2/s
x_ref = float(params.get("x_ref", 2.0))             # m
Re_x  = U_inf * x_ref / nu

# BL strategy: "lowRe" (y+≈1) or "wallFunction" (y+≈50)
BL_Mode = params.get("BL_Mode", "lowRe").lower()
y_plus_target = 1.0 if BL_Mode == "lowre" else 50.0

# Geometric growth & layers (tweak in config.json)
growth_ratio = float(params.get("BL_Growth_Ratio", 1.20))   # 1.1–1.3 is typical
N_layers     = int(params.get("BL_Max_Layers", 40))

if N_layers < 1:
    raise ValueError("BL_Max_Layers must be >= 1.")

# Compute dy1 and total thickness in METERS
dy1      = first_cell_height(y_plus_target, nu, U_inf, Re_x, flow="turbulent")
BL_total = total_BL_thickness(dy1, N_layers, growth_ratio)

if dy1 <= 0.0 or BL_total <= 0.0:
    raise ValueError("Computed BL parameters are non-positive. Check inputs.")

print(f"Strategy: {BL_Mode} | Re_x={Re_x:.3e}")
print(f"dy1 (first layer height) = {dy1:.3e} m")
print(f"Total BL thickness       = {BL_total:.3e} m")

# Optional normalization: if your AFLR3 expects values normalized by a scale
# (e.g., capsMeshLength), set BL_Scale_Length in config.json; leave at 1.0 for meters.
BL_scale = float(params.get("BL_Scale_Length", 1.0))
BL_Initial_Spacing_in = dy1 / BL_scale
BL_Thickness_in       = BL_total / BL_scale

#######################################
##        Build volume mesh          ##
#######################################
print('\n==> Creating AFLR3 AIM')
aflr3 = capsProblem.analysis.create(aim="aflr3AIM", name="aflr3")
aflr3.input.Mesh_Format = "VTK"

# Link AFLR4 surface mesh to AFLR3 (parent/child)
aflr3.input["Surface_Mesh"].link(aflr4.output["Surface_Mesh"])

# Verbosity
aflr3.input.Mesh_Quiet_Flag = False

# ---- Boundary layer control ----
aflr3.input.BL_Initial_Spacing = BL_Initial_Spacing_in   # meters or normalized (see BL_Scale_Length)
aflr3.input.BL_Thickness       = BL_Thickness_in         # meters or normalized
aflr3.input.BL_Max_Layers      = N_layers

# Specify prism boundary layer elements
aflr3.input.Mesh_Gen_Input_String = "-blc"

# ---- Define groups: mark real walls as Viscous so BL layers are generated ----
aflr3.input.Mesh_Sizing = {
    "blunt":    {"bcType": "Viscous"},
    "Farfield": {"bcType": "Farfield"}
}

print("==> Running AFLR3 (pre/post-analysis)")
aflr3.runAnalysis()
aflr3.geometry.view()