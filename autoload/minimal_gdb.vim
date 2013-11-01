let s:script_folder_path = fnamemodify(resolve(expand('<sfile>:p')), ':h')
let s:python_env_initialized = 0
let s:debug_session_is_active_cache_flag = 1
let s:max_bp_age = 48

"TODO make this script an ft plugin

function! s:EnsurePythonInitialization()
    if (s:python_env_initialized)
        return
    endif
    py import sys
    py import vim
    exe 'python sys.path.insert(0, "' . s:script_folder_path . '/../python")'
    py import mingdb
    let s:python_env_initialized = 1
    if pyeval('mingdb.DatabaseIsEmpty()')
        let s:debug_session_is_active_cache_flag = 0
    endif
endfunction

function minimal_gdb#toggle()
    if &modified
        echohl ErrorMsg | echo "Error. Buffer has unsaved changes. Cannot set the breakpoint. Please save the file and retry" | echohl None
        return
    endif
    let max_age = s:max_bp_age
    if exists("g:mingdb_bp_max_age")
        let max_age = g:mingdb_bp_max_age
    endif
    let lineno = line(".")
    let filename = expand("%:p")
    call s:EnsurePythonInitialization()
    py mingdb.ToggleBreakpoint(vim.eval('filename'), int(vim.eval('lineno')), int(vim.eval('max_age')))
    let s:debug_session_is_active_cache_flag = 1
    redraw!
endfunction

function minimal_gdb#delete_all()
    call s:EnsurePythonInitialization()
    py mingdb.DeleteAllBreakpoints()
    redraw!
endfunction

function minimal_gdb#show_breakpoints()
    if (!s:debug_session_is_active_cache_flag)
        return
    endif
    call s:EnsurePythonInitialization()
    let filename = expand("%:p")
    py mingdb.ShowBreakpointsInFile(vim.eval('filename'))
    redraw!
endfunction
