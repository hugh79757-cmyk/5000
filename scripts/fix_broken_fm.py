#!/usr/bin/env python3
"""깨진 front matter에서 ---로 시작하는 잔해 줄 제거"""
import glob, os

CUAP = "/Users/twinssn/Projects/CUAP"
targets = ["baby-hugo", "fitness-hugo", "appliance-hugo", "interior-hugo", "laptop-hugo"]

for blog in targets:
    pattern = os.path.join(CUAP, blog, "content", "**", "index.md")
    files = glob.glob(pattern, recursive=True)
    fixed = 0
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        new_lines = []
        in_fm = False
        fm_count = 0
        modified = False

        for line in lines:
            if line.strip() == "---":
                fm_count += 1
                if fm_count == 1:
                    in_fm = True
                    new_lines.append(line)
                elif fm_count == 2:
                    in_fm = False
                    new_lines.append(line)
                else:
                    new_lines.append(line)
            elif in_fm and line.startswith("---"):
                # 잔해 줄 — 제거
                modified = True
                continue
            else:
                new_lines.append(line)

        if modified:
            with open(f, "w", encoding="utf-8") as fh:
                fh.writelines(new_lines)
            fixed += 1

    if fixed > 0:
        print(f"[{blog}] cleaned: {fixed}")

print("done")
