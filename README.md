# File-Mangement-for-Small-Studios
Some Automation and Pipeline tool for houdini 20+ python 3.7 

Description: (HOUDINI_PACKAGE_DIR = /some_root_directory)

Set an environment variable HOUDINI_PACKAGE_DIR to point to the root directory (e.g., /some_root_directory/).
The PixelLab.json file, located in the root directory alongside PixelLab-Tools, uses this variable to define paths inside the package.
Inside PixelLab-Tools, the MainMenuCommon.xml file configures menus for Houdini.
The subfolders ffmpeg, otls, and scripts contain respective tools, libraries, and scripts used by the PixelLab tools.
This setup allows Houdini to correctly load and access the PixelLab tools and their dependencies.
<img width="337" height="332" alt="Screenshot 2025-08-11 093639" src="https://github.com/user-attachments/assets/bc5a57e5-ca40-4380-b4fc-ffba93a08c09" />

After sussecfully setting up the path and Enviroment variable you will find two new menu called Pixel Lab and Flipbook lab like this ~

<img width="336" height="302" alt="Screenshot 2025-08-11 100928" src="https://github.com/user-attachments/assets/3cfcb21c-ef9e-468e-86bd-8521bf7441af" />

Here is some working principles called Houdini Lab tool ~

Home Page:
Serves as the main dashboard providing quick access to key project information and workflow tools. It includes sections for camera listing, grouped nodes by parent type, and cache tree visualization. The page supports refreshing content to keep data current. It acts as a central hub to navigate and manage scene elements efficiently within Houdini
<img width="1096" height="678" alt="Screenshot 2025-08-11 094340" src="https://github.com/user-attachments/assets/fd040371-b0c1-479d-a71a-1a389de3e466" />

Flipbook Page:
Provides an interactive viewer for image sequences (flipbooks) generated within Houdini. It scans a specified flipbook directory for image sequences, listing them with details like frame ranges and total frames. Users can select sequences to preview, and control playback with play, pause, stop, and navigation buttons. The interface updates dynamically and integrates smoothly with Houdini workflows for quick visual feedback on rendered sequences.

Browser Navigator:
A multi-level dropdown browser lets users navigate project directories hierarchically (Project Type → Project → Shots → Sequence → Shot → Task). It displays the current path, folder contents, and allows browsing, selecting, and opening folders or files directly. Double-clicking supports loading Houdini scenes (.hip), Alembic (.abc), or other geometry files into Houdini nodes.

Deadline Job Monitor:
Integrates with Thinkbox Deadline render farm software to load, filter (by user, date, and search), and manage jobs in real-time with optional auto-refresh. Displays comprehensive job info including progress bars, statuses, frame ranges, priorities, submission times, and output paths. Users can suspend, resume, delete jobs, and view detailed job metadata via context menus or selection

thanks happy houdining ...........................
