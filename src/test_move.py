"""Quick test: try to move one file into stage_for_delete."""
import os
from pathlib import Path

src = Path(r"C:\Users\windo\Pictures\Photos\62310965656__5E0FB9AD-1F43-472E-95BA-D0C302C46767.JPEG")
dst = Path(r"C:\Users\windo\Desktop\PhotoAudit\stage_for_delete\62310965656__5E0FB9AD-1F43-472E-95BA-D0C302C46767.JPEG")

print(f"Source exists : {src.exists()}")
print(f"Stage dir exists: {dst.parent.exists()}")

if src.exists() and dst.parent.exists():
    try:
        os.rename(str(src), str(dst))
        print("SUCCESS — file moved.")
    except Exception as e:
        print(f"FAILED — {e}")
else:
    print("Cannot test: source or destination directory missing.")
