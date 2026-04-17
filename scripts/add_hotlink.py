#!/usr/bin/env python3
import os

CUAP = "/Users/twinssn/Projects/CUAP"
targets = ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]

for blog in targets:
    toml_path = os.path.join(CUAP, blog, "hugo.toml")
    with open(toml_path, "r") as f:
        content = f.read()
    if "hotlinkFeatureImage" not in content:
        content = content.replace(
            'enableSearch = true',
            'enableSearch = true\n  hotlinkFeatureImage = true'
        )
        with open(toml_path, "w") as f:
            f.write(content)
    print(f"[{blog}] hotlinkFeatureImage added")
