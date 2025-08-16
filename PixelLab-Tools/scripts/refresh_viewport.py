import hou
import os
import shutil
import stat
import ctypes

def try_delete_path(path):
    """Attempt to delete a file or directory, handle locked files gracefully."""
    try:
        os.chmod(path, stat.S_IWRITE)
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        print(f"✅ Deleted: {path}")
    except PermissionError:
        print(f"⚠️ Locked (in use): {path}")
        # Mark for deletion on next reboot
        try:
            ctypes.windll.kernel32.MoveFileExW(path, None, 4)
            print(f"🕒 Scheduled for deletion on reboot: {path}")
        except Exception as e:
            print(f"❌ Could not schedule for deletion: {e}")
    except Exception as e:
        print(f"❌ Failed to delete {path}: {e}")

def reset_to_build_and_clean_cache():
    try:
        # === [1] Switch to Build Desktop ===
        hou.hscript("desktop -l Build")
        print("🔁 Switched to Build desktop.")

        # === [2] Recook All Nodes ===
        hou.hscript("opcook -F /")
        print("🧮 Recooked all nodes.")

        # === [3] Clear OpenGL Cache ===
        hou.hscript("glcache -c")
        print("🧹 Cleared OpenGL cache.")

        # === [4] Clear Cache Folders ===
        cache_dirs = [
            os.environ.get("HOUDINI_TEMP_DIR", ""),
            os.path.join(hou.getenv("HOUDINI_USER_PREF_DIR"), "cache"),
            os.path.join(hou.getenv("HOUDINI_USER_PREF_DIR"), "flipbook"),
            os.path.join(hou.getenv("HOUDINI_USER_PREF_DIR"), "geo"),
        ]

        for cache_dir in cache_dirs:
            if cache_dir and os.path.exists(cache_dir):
                for item in os.listdir(cache_dir):
                    path = os.path.join(cache_dir, item)
                    try_delete_path(path)

        print("🧼 Cleaned Houdini user cache folders.")

        # === [5] Clear DOP simulation cache ===
        try:
            hou.hscript("dopcachenode -c")
            print("🌪️ Cleared DOP simulation cache.")
        except hou.OperationFailed:
            print("⚠️ No DOP caches to clear.")

        # === [6] Frame Bump for Evaluation ===
        current_frame = hou.frame()
        hou.setFrame(current_frame + 1)
        hou.setFrame(current_frame)
        print("🎞️ Forced scene re-evaluation.")

        # === [7] Redraw Viewports ===
        for pane in hou.ui.curDesktop().paneTabs():
            if pane.type() == hou.paneTabType.SceneViewer:
                viewport = pane.curViewport()
                try:
                    viewport.frameBoundingBox()
                    viewport.draw()
                except Exception as vp_err:
                    print(f"⚠️ Viewport redraw error: {vp_err}")
        print("🖥️ Viewports redrawn.")

        # === [8] UI Refresh ===
        hou.ui.triggerUpdate()
        print("✅ UI update triggered.")

        print("\n🎉 Houdini has been reset to Build, all caches cleared, and the viewport refreshed.")

    except Exception as e:
        print(f"❌ Error during full UI + cache reset: {e}")

# Run the full cleanup and refresh
reset_to_build_and_clean_cache()
