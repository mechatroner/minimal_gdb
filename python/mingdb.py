#!/usr/bin/env python

import sys
import os
import optparse
import errno
from os.path import dirname
import time
# future and builtins require: pip install future
from future.utils import iteritems, itervalues

#XXX Attention! there shouldn't be any unsaved changes in the file in which we want to set a breakpoint.

BREAKPOINTS_DB_PATH = os.path.join(dirname(dirname(os.path.realpath(__file__))), 'dbg_data' ,'breakpoints.db')
BREAKPOINTS_GDB_PATH = os.path.join(dirname(dirname(os.path.realpath(__file__))), 'dbg_data' ,'breakpoints.gdb')
MIN_GDB_SETTINGS_PATH = os.path.join(dirname(dirname(os.path.realpath(__file__))), 'dbg_data' ,'min_settings.gdb')
SCRIPT_SELF_PATH = os.path.realpath(__file__.rstrip('c'))
SETTINGS_SPELL = 'source %s' % MIN_GDB_SETTINGS_PATH
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
                line = line.rstrip()
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
    return max(itervalues(breakpoints))


def RestoreLineNumber(breakpoint):
    try:
        with open(breakpoint.File, 'r') as f:
            repeatNumber = 0
            for iLine, line in enumerate(f, start = 1):
                line = line.rstrip()
                if line == breakpoint.Line:
                    if repeatNumber == breakpoint.RepeatNumber:
                        return iLine
                    repeatNumber += 1
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
    return None


def DeleteAllBreakpoints(debug = False):
    breakpoints = ReadBreakpoints()
    for id in itervalues(breakpoints):
        ExecuteVimCommand('sign unplace %d' % id, debug)
    open(BREAKPOINTS_DB_PATH, 'w').close()


def ShowBreakpointsInFile(fileName, debug = False):
    breakpoints = ReadBreakpoints()
    breakpoints = dict((k, breakpoints[k]) for k in breakpoints.iterkeys() if k.File == fileName)
    #unplacing all breakpoints by ids, to make sure there are no duplicates
    for id in itervalues(breakpoints):
        ExecuteVimCommand('sign unplace %d' % id, debug)
    for bp, id in iteritems(breakpoints):
        lineNo = RestoreLineNumber(bp)
        if lineNo:
            ExecuteVimCommand('sign place %d line=%d name=mingdbtag file=%s' % (id, lineNo, bp.File), debug)


def CommitBreakpoints(breakpoints):
    with open(BREAKPOINTS_DB_PATH, 'w') as f:
        for bp, id in iteritems(breakpoints):
            entry = TEntry(id, bp)
            f.write(str(entry) + '\n')


def ExecuteVimCommand(cmd, debug):
    if debug:
        print(cmd)
    else:
        import vim
        vim.command(cmd)


def GetLineTextAndRepeatNumber(fileName, lineNo):
    with open(fileName) as f:
        content = f.readlines()
        lineText = content[lineNo - 1].rstrip()
        enumeratedContent = [(lineno, line.rstrip()) for lineno, line in enumerate(content, start = 1)]
        repeatedLines = [rl for rl in enumeratedContent if rl[1] == lineText]
        repeatNumber = repeatedLines.index((lineNo, lineText))
        return (lineText, repeatNumber)


def ToggleBreakpoint(fileName, lineNo, maxAgeInHours = 0, debug = False):
    assert (fileName.find('\t') == -1)
    lineText, repeatNumber = GetLineTextAndRepeatNumber(fileName, lineNo)
    newBreakpoint = TBreakpoint(time.time(), maxAgeInHours, fileName, repeatNumber, lineText)
    breakpoints = ReadBreakpoints()
    if newBreakpoint in breakpoints:
        oldBpId = breakpoints[newBreakpoint]
        del breakpoints[newBreakpoint]
        ExecuteVimCommand('sign unplace %d' % oldBpId, debug)
    else:
        newBpId = GetMaxId(breakpoints) + 1
        breakpoints[newBreakpoint] = newBpId
        ExecuteVimCommand('sign place %d line=%d name=mingdbtag file=%s' % (newBpId, lineNo, fileName), debug)
    EnsureDebugEnvironment()
    CommitBreakpoints(breakpoints)


def ExportBreakpoints():
    breakpoints = ReadBreakpoints()
    with open(BREAKPOINTS_GDB_PATH, 'w') as f:
        for bp, id in iteritems(breakpoints):
            lineNo = RestoreLineNumber(bp)
            if lineNo:
                f.write('break %s:%d\n' % (bp.File, lineNo))


def IsGdbInitPatched():
    try:
        with open(GDB_INIT_PATH, 'r') as f:
            for line in f:
                line = line.rstrip()
                if line == SETTINGS_SPELL:
                    return True
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
    return False


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
    if not IsGdbInitPatched():
        with open(MIN_GDB_SETTINGS_PATH, 'w') as f:
            f.write(GDB_SETTINGS_CONTENT % (SCRIPT_SELF_PATH, BREAKPOINTS_GDB_PATH))
        with open(GDB_INIT_PATH, 'a') as f:
            f.write('\n%s\n' % SETTINGS_SPELL)


def DatabaseIsEmpty():
    breakpoints = ReadBreakpoints()
    return (len(breakpoints) == 0)



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

    if options.breakpoint:
        ToggleBreakpoint(options.file, options.lineno, options.age, options.debug)
        return

    if options.delete:
        DeleteAllBreakpoints(options.debug)
        return

    if options.show:
        ShowBreakpointsInFile(options.file, options.debug)
        return

    if options.export:
        ExportBreakpoints()
        return

if __name__ == '__main__':
    main()
