"""wlrctl-wheel.py WLRCTL_SOURCE_DIR — add a discrete mouse-wheel action to wlrctl: `wlrctl pointer wheel NOTCHES` (negative scrolls up)."""
import sys

root = sys.argv[1]
p = root + "/include/pointer.h"
s = open(p).read()
if "POINTER_ACTION_WHEEL" not in s:
    s = s.replace("\tPOINTER_ACTION_SCROLL,", "\tPOINTER_ACTION_SCROLL,\n\tPOINTER_ACTION_WHEEL,", 1)
    open(p, "w").write(s)

p = root + "/pointer.c"
s = open(p).read()
if "#include <unistd.h>" not in s:                     # usleep between notches
    s = s.replace("#include <stdlib.h>", "#include <stdlib.h>\n#include <unistd.h>", 1)
if "POINTER_ACTION_WHEEL" not in s:
    s = s.replace('\t\t{"scroll", POINTER_ACTION_SCROLL},', '\t\t{"scroll", POINTER_ACTION_SCROLL},\n\t\t{"wheel",  POINTER_ACTION_WHEEL},', 1)
    s = s.replace("\tcase POINTER_ACTION_UNSPEC:\n\t\tdie(", """\tcase POINTER_ACTION_WHEEL:
\t\tif (argc < 2) die("wheel needs NOTCHES (negative scrolls up)\\n");
\t\tparse_fixed(argv[1], &cmd->dy);
\t\tbreak;
\tcase POINTER_ACTION_UNSPEC:
\t\tdie(""", 1)
    s = s.replace("\tcase POINTER_ACTION_UNSPEC:\n\t\t// Unreachable", """\tcase POINTER_ACTION_WHEEL: {
\t\t/* Discrete notches, like a real mouse wheel. Toolkits turn these into wheel events; some popups
\t\t * ignore the smooth finger scrolling that `scroll` sends. */
\t\tint notches = wl_fixed_to_int(cmd->dy), dir = notches < 0 ? -1 : 1;
\t\tfor (int i = 0; i < abs(notches); i++) {
\t\t\tzwlr_virtual_pointer_v1_axis_source(cmd->device, WL_POINTER_AXIS_SOURCE_WHEEL);
\t\t\tzwlr_virtual_pointer_v1_axis_discrete(cmd->device, timestamp(), WL_POINTER_AXIS_VERTICAL_SCROLL,
\t\t\t\twl_fixed_from_int(15 * dir), dir);
\t\t\tzwlr_virtual_pointer_v1_frame(cmd->device);
\t\t\twl_display_flush(state->display);
\t\t\tusleep(40000);
\t\t}
\t\tbreak;
\t}
\tcase POINTER_ACTION_UNSPEC:
\t\t// Unreachable""", 1)
    open(p, "w").write(s)
missing = [needle for needle in ('{"wheel",', "case POINTER_ACTION_WHEEL:\n\t\tif (argc", "case POINTER_ACTION_WHEEL: {", "#include <unistd.h>") if needle not in s]
if missing:
    sys.exit("patch did not apply: %s" % missing)
print("wheel action added")
