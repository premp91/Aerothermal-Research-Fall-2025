# This code allows for changing the input parameters for alfr4 and fun3d
# Author: Kevin Tang

import json
import os

root = "cases"

for case in os.listdir(root):
    config_path = os.path.join(root, case, "config.json")
    if not os.path.isfile(config_path):
        continue
    with open(config_path, "r") as f:
        data = json.load(f)
    
    # Modify what you want
    data["Mach"] = 2.0

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)

print("Updated Mach number in all config.json files.")

