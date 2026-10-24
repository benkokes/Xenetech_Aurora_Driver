# Capture reference jobs on the working XP computer

For the prepared CorelDRAW 11 square-and-text comparison, follow
[XP-REFERENCE-TEST.md](XP-REFERENCE-TEST.md). The package is already in the
host Downloads folder as `Aurora-XP-Reference`, shared with XP as
`Z:\Aurora-XP-Reference`.

The target is direct printing from Windows 11 applications, including preservation
of vector cutting and raster engraving. The working XP driver supplies the
reference output for comparison.

## Collect the installed settings

Copy `collect-xp-info.cmd` to a writable folder on the XP computer and run it
while signed in as the user who normally prints to the Aurora. It creates a
new `capture-...` folder beside itself. Return that folder to this project.

The script reads the relevant registry settings and copies the installed graphics
and UI DLLs, when present in the usual XP location. It does not change settings,
install anything, or communicate with the laser. Missing keys are recorded; they
are not a reason to change the existing configuration. The connection and printer
reports include local machine names and network addresses.

`jobserver-hotwatch.txt` should identify an `InBox` path. The archived XP driver
reads `HKCU\Software\ExtraTech\JOBSERVER\HotWatch\InBox` and creates its output
file there directly. A normal Windows "Print to file" capture must not be assumed
to intercept that output.

## Collect job files without running them

The working XP diagnostics confirm an inbox of `C:\xfiles\etherin\` and an
output folder of `C:\xfiles\jbs\`. First check the output folder for existing
saved jobs; copying representative files may avoid generating new examples.
Also obtain a copy of the configured connection database:
`C:\Documents and Settings\All Users.WINDOWS\Documents\laserDB20240317.dbi`.
Do not import or flash that file.

1. Disconnect the laser's Ethernet cable for the capture session. Locate the
   inbox and copy any existing files to a separate backup folder **before
   exiting JobServer**. The collected settings have `EmptyOnExit=1`, so exiting
   may clear the inbox. Do not delete existing jobs or change registry settings.
2. Exit JobServer and any other Xenetech utilities monitoring the inbox. Leave
   the installed driver and its settings in place. Confirm the watcher stays
   closed while generating the following files.
3. In the same artwork application you normally use, create a page with a small
   rectangle positioned 1 inch from each of the application's upper-left page
   edges. Record page size, rectangle dimensions, orientation, and the exact
   outline width. Use the outline width that your existing workflow recognizes
   as vector cutting. Disable automatic start in the print settings.
4. Print with the existing driver. Record the settings and copy the newly created
   inbox file to a separate folder as `01-vector-baseline`, retaining its original
   filename/extension in accompanying notes. Do not infer the extension from the
   installer; use whatever the installed driver creates.
5. Repeat with just one change per output: move the rectangle 1 inch right;
   change vector speed only; change vector power only; change PPI only. Record
   the old and new values, including their displayed units.
6. Make a raster baseline with a small black filled square, then a grayscale
   ramp. Record physical size, resolution, dithering, power, and speed. Preserve
   original bitmap pixels and the editable artwork files as well as the output.
7. Keep all captured test jobs outside the watched inbox before restoring the
   network connection or restarting the job sender. Preserve pre-existing jobs
   separately if needed. This avoids accidentally queueing the captures for
   execution.

If the driver refuses to generate files while JobServer is closed, stop after
collecting diagnostics and report the error. Do not change registry values to
force it, and do not reconnect the machine merely to obtain a file.

Network captures are a later step. The file format should be established first;
the communication component appears to use multiple channels and a handshake.
