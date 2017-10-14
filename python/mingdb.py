#!/usr/bin/env python

import sys
import os
import optparse
import errno
from os.path import dirname
import time

#XXX Attention! there shouldn't be any unsaved changes in the file in which we want to set a breakpoint.


_debug_mode = False


def iterkeys6(x):
    if sys.version_info[0] < 3:
        return x.iterkeys()
    return list(x.keys())

def iteritems6(x):
    if sys.version_info[0] < 3:
        return x.iteritems()
    return list(x.items())

def itervalues6(x):
    if sys.version_info[0] < 3:
        return x.itervalues()
    return list(x.values())


BREAKPOINTS_DB_PATH = os.path.join(dirname(dirname(os.path.abspath(__file__))), 'dbg_data' ,'breakpoints.db')
BREAKPOINTS_GDB_PATH = os.path.join(dirname(dirname(os.path.abspath(__file__))), 'dbg_data' ,'breakpoints.gdb')
MIN_GDB_SETTINGS_PATH = os.path.join(dirname(dirname(os.path.abspath(__file__))), 'dbg_data' ,'min_settings.gdb')
SCRIPT_SELF_PATH = os.path.abspath(__file__.rstrip('c'))
GDB_INIT_PATH = os.path.join(os.path.expanduser('~'), '.gdbinit')
BREAKPOINT_START_ID = 1000000

class TBreakpoint:
    def __init__(self, time, maxAgeInHours, file, repeatNumber, line):
        self.Time = time
        self.MaxAgeInHours = maxAgeInHours
        self.File = file
        self.RepeatNumber = repeatNumber
        self.Line = line

    def __hash__(self):
        return hash((self.File, self.RepeatNumber, self.Line))

    def __eq__(self, other):
        return (self.File, self.RepeatNumber, self.Line) == (other.File, other.RepeatNumber, other.Line)

    def __str__(self):
        return '\t'.join([str(self.Time), str(self.MaxAgeInHours), self.File, str(self.RepeatNumber), self.Line])

    def IsExpired(self):
        if self.MaxAgeInHours <= 0:
            return False
        age = time.time() - self.Time
        if age > self.MaxAgeInHours * 3600:
            return True
        return False


class TEntry:
    def __init__(self, id, breakpoint):
        self.Id = id
        self.Breakpoint = breakpoint


    @classmethod
    def from_string(cls, line):
        maxFieldNo = 5
        fields = line.split('\t', maxFieldNo)
        id = int(fields[0])
        time = float(fields[1])
        maxAgeInHours = int(fields[2])
        file = fields[3]
        repeatNumber = int(fields[4])
        line = fields[maxFieldNo]
        breakpoint = TBreakpoint(time, maxAgeInHours, file, repeatNumber, line)
        return cls(id, breakpoint)

    def __str__(self):
        return '\t'.join([str(self.Id), str(self.Breakpoint)])


def ReadBreakpoints():
    result = dict()
    try:
        with open(BREAKPOINTS_DB_PATH, 'r') as f:
            for line in f:
                line = line.rstrip('\n')
                entry = TEntry.from_string(line)
                if not entry.Breakpoint.IsExpired():
                    result[entry.Breakpoint] = entry.Id
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
    return result


def GetMaxId(breakpoints):
    if not len(breakpoints):
        return BREAKPOINT_START_ID
    return max(itervalues6(breakpoints))


def RestoreLineNumber(breakpoint):
    try:
        with open(breakpoint.File, 'r') as f:
            repeatNumber = 0
            for iLine, line in enumerate(f, start = 1):
                line = line.rstrip('\n')
                if line == breakpoint.Line:
                    if repeatNumber == breakpoint.RepeatNumber:
                        return iLine
                    repeatNumber += 1
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
    return None


def DeleteAllBreakpoints():
    breakpoints = ReadBreakpoints()
    for id in itervalues6(breakpoints):
        ExecuteVimCommand('sign unplace %d' % id)
    open(BREAKPOINTS_DB_PATH, 'w').close()


def ShowBreakpointsInFile(fileName):
    breakpoints = ReadBreakpoints()
    breakpoints = dict((k, breakpoints[k]) for k in iterkeys6(breakpoints) if k.File == fileName)
    #unplacing all breakpoints by ids, to make sure there are no duplicates
    for id in itervalues6(breakpoints):
        ExecuteVimCommand('sign unplace %d' % id)
    for bp, id in iteritems6(breakpoints):
        lineNo = RestoreLineNumber(bp)
        if lineNo:
            ExecuteVimCommand('sign place %d line=%d name=mingdbtag file=%s' % (id, lineNo, bp.File))


def CommitBreakpoints(breakpoints):
    with open(BREAKPOINTS_DB_PATH, 'w') as f:
        for bp, id in iteritems6(breakpoints):
            entry = TEntry(id, bp)
            f.write(str(entry) + '\n')


def ExecuteVimCommand(cmd):
    if _debug_mode:
        print(cmd)
    else:
        import vim
        vim.command(cmd)


def GetLineTextAndRepeatNumber(fileName, lineNo):
    with open(fileName) as f:
        content = f.readlines()
        lineText = content[lineNo - 1].rstrip('\n')
        enumeratedContent = [(lineno, line.rstrip('\n')) for lineno, line in enumerate(content, start = 1)]
        repeatedLines = [rl for rl in enumeratedContent if rl[1] == lineText]
        repeatNumber = repeatedLines.index((lineNo, lineText))
        return (lineText, repeatNumber)


def ToggleBreakpoint(fileName, lineNo, maxAgeInHours = 0):
    assert (fileName.find('\t') == -1)
    lineText, repeatNumber = GetLineTextAndRepeatNumber(fileName, lineNo)
    newBreakpoint = TBreakpoint(time.time(), maxAgeInHours, fileName, repeatNumber, lineText)
    breakpoints = ReadBreakpoints()
    if newBreakpoint in breakpoints:
        oldBpId = breakpoints[newBreakpoint]
        del breakpoints[newBreakpoint]
        ExecuteVimCommand('sign unplace %d' % oldBpId)
    else:
        newBpId = GetMaxId(breakpoints) + 1
        breakpoints[newBreakpoint] = newBpId
        ExecuteVimCommand('sign place %d line=%d name=mingdbtag file=%s' % (newBpId, lineNo, fileName))
    EnsureDebugEnvironment()
    CommitBreakpoints(breakpoints)


def ExportBreakpoints():
    breakpoints = ReadBreakpoints()
    with open(BREAKPOINTS_GDB_PATH, 'w') as f:
        for bp, id in iteritems6(breakpoints):
            lineNo = RestoreLineNumber(bp)
            if lineNo:
                f.write('break %s:%d\n' % (bp.File, lineNo))


def PatchGdbInit():
    lines = []
    try:
        with open(GDB_INIT_PATH, 'r') as f:
            lines = f.readlines()
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise

    settings_spell = 'source {}\n'.format(MIN_GDB_SETTINGS_PATH)
    if settings_spell in lines:
        return

    with open(GDB_INIT_PATH, 'w') as f:
        for line in lines:
            if line.find('source') != -1 and line.find('min_settings.gdb') != -1:
                continue
            f.write(line)
        f.write('\n')
        f.write(settings_spell)
        


GDB_SETTINGS_CONTENT = """
define syncbp
    delete
    set breakpoint pending on
    shell %s -e
    source %s
    set breakpoint pending off
end

syncbp
"""

def EnsureDebugEnvironment():
    with open(MIN_GDB_SETTINGS_PATH, 'w') as f:
        f.write(GDB_SETTINGS_CONTENT % (SCRIPT_SELF_PATH, BREAKPOINTS_GDB_PATH))
    PatchGdbInit()


def DatabaseIsEmpty():
    breakpoints = ReadBreakpoints()
    return (len(breakpoints) == 0)

def InitCacheFlag():
    if DatabaseIsEmpty():
        ExecuteVimCommand("let s:debug_session_is_active_cache_flag = 0")


def main():
    parser = optparse.OptionParser("%prog [options]")
    parser.add_option('-D', action='store_true', dest='debug', help='debug script', default=False)
    parser.add_option('-B', action='store_true', dest='breakpoint', help='toggle breakpoint', default=False)
    parser.add_option('-b', action='store', dest='database', help='breakpoints database')
    parser.add_option('-d', action='store_true', dest='delete', help='delete all breakpoints', default=False)
    parser.add_option('-s', action='store_true', dest='show', help='show breakpoints in file', default=False)
    parser.add_option('-f', action='store', dest='file', help='file name (in bp toggle mode)')
    parser.add_option('-n', action='store', dest='lineno', help='line no, 1-based (in bp toggle mode)', type='int')
    parser.add_option('-e', action='store_true', dest='export', help='export breakpoints', default=False)
    parser.add_option('-c', action='store_true', dest='check', help='check whether database is empty', default=False)
    parser.add_option('-m', action='store', dest='age', help='breakpoint max age (time to keep) in hours', type='int', default=0)
    (options, args) = parser.parse_args()

    if options.database:
        global BREAKPOINTS_DB_PATH
        BREAKPOINTS_DB_PATH = options.database

    if options.check:
        result = 'empty' if DatabaseIsEmpty() else 'full'
        print(result)
        return

    global _debug_mode
    _debug_mode = options.debug

    if options.breakpoint:
        ToggleBreakpoint(options.file, options.lineno, options.age)
        return

    if options.delete:
        DeleteAllBreakpoints()
        return

    if options.show:
        ShowBreakpointsInFile(options.file)
        return

    if options.export:
        ExportBreakpoints()
        return

if __name__ == '__main__':
    main()
