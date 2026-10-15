import { execFileSync } from 'node:child_process';

// CDP key dispatch goes to the renderer and does not exercise Chromium's native
// fullscreen Escape handling. The optional Xvfb lane sends an OS key instead.
// Requires an isolated headed Chromium run, Python 3, X11, and libXtst.
export function pressNativeOverviewEscape() {
  if (!process.env.DISPLAY)
    throw new Error('Native Escape needs an X11 display');
  execFileSync('python3', [
    '-c',
    `
import ctypes
import ctypes.util
x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
xtst = ctypes.CDLL(ctypes.util.find_library('Xtst'))
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XKeysymToKeycode.restype = ctypes.c_uint
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
display = x11.XOpenDisplay(None)
if not display:
    raise RuntimeError('Unable to open isolated X11 display')
try:
    key = x11.XKeysymToKeycode(display, x11.XStringToKeysym(b'Escape'))
    if not key:
        raise RuntimeError('Escape keycode unavailable')
    xtst.XTestFakeKeyEvent(display, key, 1, 0)
    xtst.XTestFakeKeyEvent(display, key, 0, 0)
    x11.XFlush(display)
finally:
    x11.XCloseDisplay(display)
`,
  ]);
}
