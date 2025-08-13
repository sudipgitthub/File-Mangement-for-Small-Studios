import hou

def launch_browser():
    try:
        from my_browser_tool import FileBrowser  # import your script
        FileBrowser()
    except Exception as e:
        print("Browser tool auto-load failed:", e)

# Run after Houdini fully loads
hou.ui.addEventLoopCallback(lambda: (launch_browser(), hou.ui.removeEventLoopCallback(_callback_id))[0])
