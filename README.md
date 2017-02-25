#Minimal gdb

Minimal gdb is a lightweight vim -> gdb broker which uses .gdbinit mechanism to export breakpoints from vim into gdb session.

The plugin provides `<leader>b` shortcut which allows user to set breakpoints while in vim. Breakpoints are added to special file which is sourced from ~/.gdbinit (this source magic will be performed on the first run). When gdb starts all breakpoints are getting exported. If you add more breakpoints after gdb was started you have to execute `syncbp` command in gdb to reexport breakpoints from vim. `syncbp` is added to gdb via the same ~/.gdbinit magic. 

The plugin doesn't provide functionality for debugging in vim window. You have to start gdb session.

The main difference from other gdb vim plugins, is that Minimal gdb uses the .gdbinit file for breakpoint export and doesn't provide functionality for debugging inside vim window.

####A typical use case looks like this:
1. Set some breakpoints in vim, they will be highlighted in the 'sign' column
2. Run gdb, which will automatically export the breakpoints from step 1.
3. Set some more breakpoints
4. Export them in gdb by using `synbp` command, or by restarting the debugger (the former is easier).

##INSTALLATION:
Copy the files to your .vim folder or use Vundle.
The script will configure everything when you set a first breakpoint.

##COMMANDS:
###In vim:
* `MinGDBToggleBP` or `<leader>b` - toggles a breakpoint.
* `MinGDBDeleteAll` - delete all breakpoints
* `MinGDBRefreshFile` - refresh breakpoints positions in a vim file. Use this in case something went wrong.

###In gdb:
* `synbp` - export new breakpoints from vim, which were set after gdb session has started.


##REQUIREMENTS:
* gdb
* python 2.7, or 3.xx
* vim compiled with python and signs features.

