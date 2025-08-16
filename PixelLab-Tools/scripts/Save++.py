import os
import re
import hou

def save_incremental_hip():
    # Get current hip file path
    current_path = hou.hipFile.path()

    # If file hasn't been saved yet, start at v001
    if current_path == "untitled.hip":
        default_dir = hou.getenv("HIP")
        new_path = os.path.join(default_dir, "untitled_v001.hip")
        hou.hipFile.save(new_path)
        print(f"File saved as {new_path}")
        return

    dir_path = os.path.dirname(current_path)
    base_name = os.path.basename(current_path)

    # Look for v### pattern in file name
    match = re.search(r"(v)(\d{3})(?=\.hip)", base_name, re.IGNORECASE)
    if match:
        # Increment version
        prefix = match.group(1)
        version_num = int(match.group(2)) + 1
        new_base = re.sub(r"(v)(\d{3})(?=\.hip)",
                          f"{prefix}{version_num:03d}", base_name)
    else:
        # If no version found, start at v001
        name, ext = os.path.splitext(base_name)
        new_base = f"{name}_v001{ext}"

    new_path = os.path.join(dir_path, new_base)

    # Save the hip file
    hou.hipFile.save(new_path.replace("\\", "/"))
    print(f"File saved as {new_path}")

# Run the function
save_incremental_hip()
