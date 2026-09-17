"""maker-orca's screen reading, checked against Tesseract output from real OrcaSlicer 2.4.2 captures.
    python3 -m unittest tests/test_maker_orca.py
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "orca")
_loader = importlib.machinery.SourceFileLoader("maker_orca", os.path.join(ROOT, "bin", "maker-orca"))
_spec = importlib.util.spec_from_loader("maker_orca", _loader)
orca = importlib.util.module_from_spec(_spec)
_loader.exec_module(orca)
META = json.load(open(os.path.join(FIXTURES, "meta.json")))


def write_text(path, text):
    with open(path, "w") as out:
        out.write(text)


def fixture_lines(name):
    info = META[name]
    words = orca.parse_tsv(open(os.path.join(FIXTURES, name + ".tsv")).read(), info["dx"], info["dy"], info["scale"])
    return words, orca.lines(words)


class ReadingLists(unittest.TestCase):
    def entries(self, name):
        _words, found = fixture_lines(name)
        column = orca.list_column(found, META[name]["box_left"])
        self.assertIsNotNone(column)
        return orca.list_entries(found, column)

    def test_printer_list(self):
        entries = self.entries("printer-list")
        kinds = [kind for kind, _text, _y in entries]
        self.assertEqual(kinds[0], "header")
        self.assertIn("header", kinds[1:])
        names = ["A1", "Jr.", "Jr. - z", "P1S", "Bambu Lab P1S"]
        read = [orca.best_match(text, names) for kind, text, _y in entries if kind == "item"]
        self.assertEqual([r for r in read if r], names)       # "Al" is A1, "Jr-z" is "Jr. - z"

    def test_list_ends_at_its_action_rows(self):
        kinds = [kind for kind, _t, _y in self.entries("printer-list")]
        self.assertEqual(kinds[-1], "action")
        self.assertNotIn("item", kinds[kinds.index("action"):])

    def test_rows_sit_one_step_apart(self):
        ys = [y for _kind, _text, y in self.entries("printer-list")]
        for a, b in zip(ys, ys[1:]):
            self.assertAlmostEqual((b - a) / orca.ROW_STEP, round((b - a) / orca.ROW_STEP), delta=0.25)

    def test_plate_types_read_whole(self):
        entries = self.entries("plate-list")
        read = [orca.best_match(text, orca.PLATE_TYPES) for kind, text, _y in entries if kind == "item"]
        self.assertEqual(read, list(orca.PLATE_TYPES))          # "Engineering Plate", not "Engineering"


class ListNoise(unittest.TestCase):
    def test_a_speck_above_the_list_does_not_end_it(self):
        found = [{"text": "\u2014", "x": 426, "y": 187}]
        found += [{"text": name, "x": 415, "y": 206 + 28 * n} for n, name in enumerate(orca.PLATE_TYPES)]
        found += [{"text": "wu", "x": 404, "y": 363}]
        entries = orca.list_entries(found, 416)
        self.assertEqual([text for _kind, text, _y in entries], list(orca.PLATE_TYPES))


class MenuOrder(unittest.TestCase):
    def test_a_name_comes_before_longer_names_starting_with_it(self):
        names = ["0.20mm Standard @BBL X1C - abs", "ASA 0.2", "0.20mm Standard @BBL X1C", "0.2 mm petg"]
        ordered = orca.by_name(names)
        self.assertLess(ordered.index("0.20mm Standard @BBL X1C"), ordered.index("0.20mm Standard @BBL X1C - abs"))


class Tabs(unittest.TestCase):
    def test_every_tab_found_left_to_right(self):
        words, _found = fixture_lines("tabs")
        tabs = orca.find_tabs(words)
        order = sorted(tabs, key=tabs.get)
        self.assertEqual(order, ["home", "prepare", "preview", "device", "project", "calibration"])


class Matching(unittest.TestCase):
    def test_letter_case_breaks_ties(self):
        self.assertEqual(orca.best_match("Bambu PLA", ["Bambu pla", "Bambu PLA", "Bambu PLA Basic"]), "Bambu PLA")

    def test_spaces_and_dots_lost_by_ocr(self):
        self.assertEqual(orca.best_match("ASA 0.220", ["ASA 0.2", "ASA 0.2 2.0", "PLA+"]), "ASA 0.2 2.0")

    def test_half_hidden_row_is_nothing(self):
        self.assertIsNone(orca.best_match("pase", ["Base", "Bass", "PETG HF"]))

    def test_vendor_group_is_no_preset(self):
        self.assertIsNone(orca.best_match("Bambu", ["Bambu PLA", "Bambu PETG", "Bambu Matte"]))

    def test_classify(self):
        self.assertEqual(orca.classify("User presety —098m ——", 10)[0], "header")
        self.assertEqual(orca.classify("-- Create printer --", 10)[0], "action")
        self.assertEqual(orca.classify("Bambu PLA", 10)[0], "item")


class KeysMatchTheBindings(unittest.TestCase):
    CHORDS = (("SPACE", "menu"), ("I", "open"), ("M", "meshy"), ("P", "pick printer"), ("F", "pick filament"),
              ("S", "pick process"), ("B", "pick plate"), ("G", "print"), ("T", "prep"), ("K", "kit"), ("V", "speeds"),
              ("BRACKETLEFT", "plate prev"), ("BRACKETRIGHT", "plate next"), ("H", "hint"))
    SHOWN = {"SPACE": "Space", "BRACKETLEFT": "[", "BRACKETRIGHT": "]"}

    def test_cheat_sheet_and_hyprland_bindings_agree(self):
        lua = open(os.path.join(ROOT, "hypr", "maker.lua")).read()
        for key, action in self.CHORDS:
            self.assertRegex(lua, r'o\.bind\("CTRL \+ ALT \+ %s", "[^"]+", orca\("%s", "%s"\)\)' % (re.escape(key), re.escape(key), re.escape(action)))
            self.assertIn("Ctrl+Alt+%s" % self.SHOWN.get(key, key), orca.KEYS)
        self.assertRegex(lua, r'o\.bind\("CTRL \+ ALT \+ O", "[^"]+", open_orca\)')
        self.assertIn("Ctrl+Alt+O", orca.KEYS)
        self.assertEqual(len(re.findall(r'"Home", "Prepare", "Preview", "Device", "Project", "Calibration"', lua)), 1)
        self.assertIn("Ctrl+Alt+1..6", orca.KEYS)

    def test_one_rule_control_alt_and_no_mode(self):
        lua = open(os.path.join(ROOT, "hypr", "maker.lua")).read()
        self.assertNotIn("define_submap", lua)      # no mode: Orca's own single keys (m, r, s, f, 1-9) are never swallowed
        self.assertNotIn("SUPER + ALT", lua)         # one rule to remember: Control + Alt is Orca
        self.assertNotIn("hl.timer", lua)            # nothing times out
        self.assertEqual(len(re.findall(r'o\.bind\("CTRL \+ ALT \+ Q"', lua)), 0)   # Esc closes pop-ups, not q
        # Orca keeps Esc: the binding is non-consuming and only hands it on to a pop-up behind the main window
        self.assertRegex(lua, r'hl\.bind\("ESCAPE", escape_to_popup, \{ non_consuming = true')
        self.assertIn("Esc", orca.KEYS)
        for orcas_own in ("Ctrl+R", "Ctrl+Shift+G", "Ctrl+P"):
            self.assertIn(orcas_own, orca.KEYS)      # Orca's own shortcuts are listed, not duplicated
        self.assertNotIn("KeysAside", open(os.path.join(ROOT, "bin", "maker-orca")).read())

    def test_chords_stay_with_orca_and_apps_keep_their_workspaces(self):
        lua = open(os.path.join(ROOT, "hypr", "maker.lua")).read()
        # with another app in front the chord is handed on untouched (Blender has Ctrl+Alt+Space and Ctrl+Alt+S itself)
        self.assertIn('if active and active.class ~= orca_class then', lua)
        self.assertIn('hl.dispatch(hl.dsp.send_shortcut({ mods = "CTRL ALT", key = key }))', lua)
        # no tiling for the maker apps: each main window has a workspace of its own, dialogs float
        for cls, ws in (("orca-slicer", "10"), ("bambu-studio", "7"), ("blender", "9"), ("OpenSCAD|org.openscad.openscad", "8")):
            self.assertRegex(lua, r'o\.window\(\{ class = "\^\(%s\)\$"[^}]*\}, \{ workspace = "%s" \}\)' % (re.escape(cls), ws))
        # Blender's pop-ups are matched on the titles they are created with, before Blender renames them
        self.assertRegex(lua, r'initial_title = "\^\(Preferences\|Image Editor\|File Browser\)\$" \}, \{ float = true, center = true, size = \{ \d+, \d+ \} \}')
        # the menu is the place that needs no memory: the other apps are in it
        self.assertIn('("Blender", "blender", "blender", ["blender"])', open(os.path.join(ROOT, "bin", "maker-orca")).read())


def orca_unescape(text):
    """Orca's unescape_strings_cstyle (libslic3r/Config.cpp), as the running Orca reads a handed-over command line."""
    out, i = [], 0
    while True:
        while i < len(text) and text[i] in " \t":
            i += 1
        if i == len(text):
            return out
        buf = []
        if text[i] == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                c = text[i]
                if c == "\\":
                    i += 1
                    c = {"r": "\r", "n": "\n"}.get(text[i], text[i])
                buf.append(c)
                i += 1
            if i == len(text):
                raise ValueError("unterminated quote")
            i += 1
        else:
            while i < len(text) and text[i] != ";":
                buf.append(text[i])
                i += 1
        out.append("".join(buf))
        while i < len(text) and text[i] in " \t":
            i += 1
        if i == len(text):
            return out
        if text[i] != ";":
            raise ValueError("junk after a quoted string")
        i += 1


class HandingFilesToOrca(unittest.TestCase):
    def test_orca_reads_back_every_path(self):
        paths = ["/home/me/owl.stl", "/home/me/Meshy Models/big owl.3mf", 'odd"name\\x.stl', "semi;colon.stl"]
        self.assertEqual(orca_unescape(orca.orca_message(paths)), ["orca-slicer"] + paths)

    def test_plain_paths_stay_plain(self):
        self.assertEqual(orca.orca_message(["/a/b.stl"]), "orca-slicer;/a/b.stl")


class PrintWindow(unittest.TestCase):
    def test_status_words(self):
        self.assertEqual(orca.status_words("PrintStatusReadyToGo"), "ready to go")
        self.assertEqual(orca.status_words("PrintStatusNozzleTypeMismatch"), "nozzle type mismatch")

    def test_waits_past_passing_statuses(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
            handle.write("show_status: update_status: 7(PrintStatusReading)\n")
        self.addCleanup(os.remove, handle.name)
        log = orca.OrcaLog()
        log.path, log.offset = handle.name, 0
        self.assertEqual(orca.settled_status(log, 0), ("PrintStatusReading", False))
        with open(handle.name, "a") as more:
            more.write("show_status: update_status: 4(PrintStatusInvalidPrinter)\nshow_status: update_status: 58(PrintStatusReadyToGo)\n")
        self.assertEqual(orca.settled_status(log, 0), ("PrintStatusReadyToGo", True))

    def test_plate_state_from_the_log(self):
        import tempfile
        line = "update_slice_print_status m_slice_select 1: can_slice= 1, can_print 1, enable_slice %d, enable_print %d \n"
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
            handle.write(line % (1, 0))
        self.addCleanup(os.remove, handle.name)
        saved = orca.OrcaLog.__init__
        def at_file(log):
            log.path, log.offset = handle.name, os.path.getsize(handle.name)
        orca.OrcaLog.__init__ = at_file
        try:
            self.assertEqual(orca.plate_state(), (True, False))
            since = orca.OrcaLog()
            self.assertIsNone(orca.plate_state(since))
            with open(handle.name, "a") as more:
                more.write(line % (0, 0) + line % (0, 1))
            self.assertEqual(orca.plate_state(since), (False, True))
        finally:
            orca.OrcaLog.__init__ = saved

    def test_printable_count_from_the_log(self):
        import tempfile
        line = "update_print_volume_state, print_volume {0, 0, 0} to {256, 256, 250}, got %d printable istances\n"
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
            handle.write(line % 1 + "Undo / Redo snapshot reloaded.\n" + line % 0)
        self.addCleanup(os.remove, handle.name)
        saved = orca.OrcaLog.__init__
        def at_file(log):
            log.path, log.offset = handle.name, os.path.getsize(handle.name)
        orca.OrcaLog.__init__ = at_file
        try:
            self.assertEqual(orca.printable_on_plate(), 0)
            with open(handle.name, "a") as more:
                more.write(line.replace("{0, 0, 0} to {256, 256, 250}", "{307.2, 0, 0} to {563.2, 256, 250}") % 2)
            self.assertEqual(orca.printable_on_plate(), 2)
            with open(handle.name, "a") as more:
                more.write("load_model_objects:7185, after add_objects_to_list\n")      # imported, not counted yet
            self.assertIsNone(orca.printable_on_plate())
        finally:
            orca.OrcaLog.__init__ = saved

    def test_log_since_mark(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
            handle.write("on_selection_changedfor send task, current printer id = OLD\n")
        self.addCleanup(os.remove, handle.name)
        log = orca.OrcaLog()
        log.path = handle.name
        log.mark()
        self.assertIsNone(log.last(r"current printer id = (\w+)"))
        with open(handle.name, "a") as more:
            more.write("on_selection_changedfor send task, current printer id = NEW\n")
        self.assertEqual(log.last(r"current printer id = (\w+)").group(1), "NEW")


class Plates(unittest.TestCase):
    # Preview's column: the stats item, then plates 1-3 about 110 px apart; plate 2 selected
    BLOCKS = [(100, 210), (222, 330), (336, 446), (452, 560)]
    BOX = (489, 336, 597, 446)

    def test_next_and_previous_wrap(self):
        self.assertEqual(orca.plate_target(self.BOX, self.BLOCKS, 3, "next"), (2, (452, 560)))
        self.assertEqual(orca.plate_target(self.BOX, self.BLOCKS, 3, "prev"), (0, (222, 330)))
        last = (489, 452, 597, 560)
        self.assertEqual(orca.plate_target(last, self.BLOCKS, 3, "next"), (0, (222, 330)))

    def test_never_clicks_the_stats_item_or_guesses(self):
        first = (489, 222, 597, 330)
        self.assertEqual(orca.plate_target(first, self.BLOCKS, 3, "prev")[0], 2)     # wraps past the stats item
        with self.assertRaises(orca.Stop):
            orca.plate_target(self.BOX, self.BLOCKS[:3], 3, "next")                   # a plate out of view
        with self.assertRaises(orca.Stop):
            orca.plate_target((489, 600, 597, 700), self.BLOCKS, 3, "next")          # selection not in the column


class MeshyMenu(unittest.TestCase):
    def test_last_height_comes_first(self):
        self.assertEqual(orca.size_rows("60 mm tall")[0][0], "60 mm tall")
        self.assertEqual([r[0] for r in orca.size_rows(None)], [r[0] for r in orca.SIZES])
        self.assertEqual(sorted(r[0] for r in orca.size_rows("120 mm tall")), sorted(r[0] for r in orca.SIZES))

    def test_height_arguments(self):
        self.assertEqual(orca.size_args("80 mm tall"), ["--height", "80"])
        self.assertEqual(orca.size_args("Meshy's size"), [])
        self.assertEqual(orca.size_args(None), [])

    def test_last_choices_are_remembered(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saved = orca.MESHY_LAST
            orca.MESHY_LAST = os.path.join(tmp, "sub", "meshy-last.json")
            try:
                self.assertEqual(orca.meshy_last(), {})
                orca.meshy_last(text="a stone lantern")
                orca.meshy_last(size="40 mm tall")
                self.assertEqual(orca.meshy_last(), {"text": "a stone lantern", "size": "40 mm tall"})
            finally:
                orca.MESHY_LAST = saved


class Models(unittest.TestCase):
    def test_same_names_get_numbers(self):
        options, by_label = orca.unique_labels([("/a/owl/model.stl", "owl", "Meshy"), ("/b/owl/model.stl", "owl", "Meshy"), ("/c/cat.stl", "cat.stl", "x")])
        self.assertEqual([o[0] for o in options], ["owl", "owl (2)", "cat.stl"])
        self.assertEqual(by_label["owl (2)"], "/b/owl/model.stl")

    def test_meshy_models_first_then_newest(self):
        import tempfile, time as _time
        with tempfile.TemporaryDirectory() as tmp:
            meshy, downloads = os.path.join(tmp, "meshy"), os.path.join(tmp, "Downloads")
            os.makedirs(os.path.join(meshy, "owl")), os.makedirs(os.path.join(downloads, "deep", "er"))
            owl = os.path.join(meshy, "owl", "model.stl")
            write_text(owl, "solid\n")
            write_text(os.path.join(meshy, "owl", "meshy.json"), json.dumps({"name": "owl", "model": owl, "size_mm": [10, 20, 30]}))
            new, old = os.path.join(downloads, "new.3mf"), os.path.join(downloads, "deep", "er", "old.STL")
            for path, age in ((new, 10), (old, 1000)):
                write_text(path, "x")
                os.utime(path, (_time.time() - age, _time.time() - age))
            write_text(os.path.join(downloads, "notes.txt"), "x")
            saved = orca.MESHY_OUT, orca.MODEL_FOLDERS, orca.ORCA_CONFIG
            orca.MESHY_OUT, orca.MODEL_FOLDERS, orca.ORCA_CONFIG = meshy, (downloads, meshy), tmp
            try:
                rows = orca.recent_models()
            finally:
                orca.MESHY_OUT, orca.MODEL_FOLDERS, orca.ORCA_CONFIG = saved
            self.assertEqual([label for _p, label, _s in rows], ["owl", "new.3mf", "old.STL"])
            self.assertEqual(rows[0][2], "Meshy · 10 × 20 × 30 mm")


class PreparingForAPrint(unittest.TestCase):
    """The Process settings panel, read from real captures of Orca's Strength and Support tabs."""

    def rows(self, name):
        _words, found = fixture_lines(name)
        rows = {}
        for line in found:
            if line["right"] < orca.PANEL_LABEL_RIGHT and re.search(r"[A-Za-z]", line["text"]):
                rows.setdefault(orca.squash(line["text"]), round(line["y"]))
        return rows

    def test_tabs_read_even_when_greyed_out(self):
        words, _found = fixture_lines("process-tabs")
        tabs = {}
        for word in words:
            name = orca.best_match(word["text"], list(orca.PANEL_TABS), cutoff=0.8)
            if name and name.lower() not in tabs:
                tabs[name.lower()] = round(word["x"] + word["w"] / 2)
        self.assertEqual(sorted(tabs), ["multimaterial", "others", "quality", "speed", "strength", "support"])
        self.assertEqual(sorted(tabs.values()), list(tabs[name] for name in
                                                    ["quality", "strength", "speed", "support", "multimaterial", "others"]))

    def test_settings_are_found_by_their_label(self):
        rows = self.rows("strength-panel")
        for label in ("Sparse infill density", "Sparse infill pattern", "Top surface pattern"):
            self.assertIn(orca.squash(label), rows, label)
        self.assertNotIn(orca.squash("Cross Hatch"), rows)     # values live right of the labels, not among them

    def test_support_settings_are_found_while_they_are_greyed_out(self):
        rows = self.rows("support-panel")
        for label in ("Enable support", "Type", "Threshold angle", "On build plate only"):
            self.assertIn(orca.squash(label), rows, label)

    def test_a_ticked_box_is_teal_and_an_empty_one_is_grey(self):
        class FakeShot:
            def __init__(self, teal):
                self.teal = teal

            def pixel(self, dx, dy):
                inside = abs(dx - orca.PANEL_CHECK_X) <= 6 and abs(dy - 466) <= 6
                if not (self.teal and inside):
                    return (45, 45, 49)
                return (134, 203, 196) if abs(dx - orca.PANEL_CHECK_X) <= 1 else (0, 148, 134)

        saved = orca.Shot, orca.cursor, orca.move_cursor
        try:
            orca.cursor = lambda: (2000, 500)          # the pointer is off the settings: nothing to move
            orca.move_cursor = lambda *a: None
            for teal in (True, False):
                orca.Shot = lambda *a, teal=teal, **k: FakeShot(teal)
                self.assertEqual(orca.panel_ticked({"at": [0, 0], "size": [1416, 850]}, 466), teal)
        finally:
            orca.Shot, orca.cursor, orca.move_cursor = saved

    def test_the_patterns_we_print_are_taken_and_others_are_not(self):
        for ours in ("Cross Hatch", "Gyroid", "Adaptive Cubic"):
            self.assertTrue(orca.best_match(ours, list(orca.TEST_PATTERNS), cutoff=0.9), ours)
        for other in ("Grid", "Honeycomb", "Rectilinear", "Lightning", "Cubic"):   # "Grid" is 0.8 like "Gyroid"
            self.assertFalse(orca.best_match(other, list(orca.TEST_PATTERNS), cutoff=0.9), other)

    def test_orcas_floating_regions_warning_is_told_from_the_estimate(self):
        warning = ("Warning: It seems object a-small-cute-turtle-figurine-standing.stl has floating regions. "
                   "Please re-orient the object or enable support generation.")
        self.assertTrue(orca.FLOATING.search(warning))
        self.assertFalse(orca.FLOATING.search("Total estimation Total Filament: 5.19 m 15.72g"))

    def test_the_support_row_of_the_legend_is_read_and_the_interface_row_is_not(self):
        def row(text, y):
            words, x = [], 900
            for piece in text.split(" "):
                words.append({"text": piece, "x": x, "y": y, "w": 9 * len(piece), "h": 14})
                x += 9 * len(piece) + 60                      # the legend's columns sit far apart
            return words

        class FakeShot:
            def __init__(self, support="Support 1m16s 2.7 0.12m 0.35g"):
                self.support = support

            def words(self, *a, **k):
                return (row(self.support, 352)
                        + row("Support interface 3s 0.1 0.00m 0.01g", 376)
                        + row("Total Filament: 438m 13.269", 652))   # Tesseract turns the total's g into a 9

        saved = orca.Shot
        try:
            orca.Shot = lambda *a, **k: FakeShot()
            self.assertEqual(orca.support_weight({"at": [0, 0], "size": [1416, 850]}), 0.35)
            # the reading that started this: 3.91 g came back as "391g", and 1.29 m of filament is about 3.8 g
            orca.Shot = lambda *a, **k: FakeShot("Support 9m50s 5.1 1.29m 391g")
            self.assertEqual(orca.support_weight({"at": [0, 0], "size": [1416, 850]}), 3.91)
            orca.Shot = lambda *a, **k: FakeShot("Support 2m10s 1.1 0.40m 1.19g")
            self.assertEqual(orca.support_weight({"at": [0, 0], "size": [1416, 850]}), 1.19)
        finally:
            orca.Shot = saved

    def test_no_support_row_means_no_supports(self):
        class FakeShot:
            def words(self, *a, **k):
                return [{"text": "Travel", "x": 900, "y": 352, "w": 50, "h": 14}]

        saved = orca.Shot
        try:
            orca.Shot = lambda *a, **k: FakeShot()
            self.assertIsNone(orca.support_weight({"at": [0, 0], "size": [1416, 850]}))
        finally:
            orca.Shot = saved

    def test_critical_regions_goes_back_before_supports_are_switched_off(self):
        labels = [label for _tab, label in orca.PREP_SETTINGS]
        self.assertLess(labels.index("Support critical regions only"), labels.index("Enable support"),
                        "Orca hides that row once supports are off")

    def test_a_test_print_is_ten_percent_in_a_pattern_we_print(self):
        self.assertEqual(orca.TEST_INFILL, 10)
        self.assertEqual(orca.TEST_PATTERNS[0], "Gyroid")



class ThePlateMenu(unittest.TestCase):
    """Orca's right-click menu on the plate, read from a real capture. Anything that has to reach every plate
    goes through it: the keys only ever reach the plate in front of you."""

    def rows(self, name="plate-menu"):
        _words, found = fixture_lines(name)
        return orca.menu_items(found)

    def test_every_row_we_use_is_read(self):
        rows = self.rows()
        for item in ("Select All", "Select All Plates", "Delete All", "Arrange", "Delete Plate"):
            self.assertIn(item, rows, item)

    def test_delete_all_and_delete_plate_are_different_rows(self):
        rows = self.rows()
        self.assertGreater(abs(rows["Delete All"]["y"] - rows["Delete Plate"]["y"]), 10)

    def test_select_all_is_not_select_all_plates(self):
        rows = self.rows()
        self.assertGreater(abs(rows["Select All"]["y"] - rows["Select All Plates"]["y"]), 10)

    def test_a_few_stray_words_are_not_a_menu(self):
        strays = [{"text": "Delete All", "x": 10, "right": 80, "y": 20},
                  {"text": "Arrange", "x": 10, "right": 60, "y": 50}]
        self.assertEqual(orca.menu_items(strays), {})


if __name__ == "__main__":
    unittest.main()


class PrinterControls(unittest.TestCase):
    """The Device page's home and bed buttons are found from what Tesseract reads there (Orca 2.4.2, 1440 x 900,
    the words below are the real ones from 2026-09-17: "Bed" itself never comes through)."""

    def words(self, *items):
        return [{"text": t, "x": x, "y": y, "w": w, "h": h, "conf": 90} for t, x, y, w, h in items]

    REAL = (("-X", 1080, 264, 18, 14), ("X", 1245, 264, 11, 14), ("Y", 1164, 183, 12, 14), ("-Y", 1162, 346, 17, 14),
            ("T10", 1058, 410, 32, 14), ("Ta", 1114, 410, 20, 14), ("To", 1191, 410, 20, 14), ("110", 1243, 410, 28, 14))

    def test_home_is_the_middle_of_the_axis_pad(self):
        spots = orca.controls_from_words(self.words(*self.REAL))
        self.assertAlmostEqual(spots["home"][0], 1170, delta=2)      # the column of the Y labels
        self.assertAlmostEqual(spots["home"][1], 271, delta=1)       # the row of the X labels

    def test_bed_row_is_centred_between_the_two_10_buttons(self):
        spots = orca.controls_from_words(self.words(*self.REAL))
        self.assertAlmostEqual(spots["bed"][0], (1074 + 1257) / 2.0, delta=1)
        self.assertAlmostEqual(spots["bed"][1], 417, delta=1)

    def test_bed_row_falls_back_to_the_home_button_when_the_10s_are_missing(self):
        spots = orca.controls_from_words(self.words(*self.REAL[:4]))
        self.assertAlmostEqual(spots["bed"][1], spots["home"][1] + 147)

    def test_no_axis_labels_means_no_controls(self):
        with self.assertRaises(orca.Stop):
            orca.controls_from_words(self.words(("Camera", 300, 100, 60, 14), ("T10", 1058, 410, 32, 14)))


class SendSwitches(unittest.TestCase):
    """The print window's Timelapse and Auto Bed Leveling switches: each is an On and an Off label on the row
    that starts with its name (words as Tesseract returned them on 2026-09-17)."""

    ROW = [{"text": "Timelapse", "x": 16, "y": 548, "w": 60, "h": 14}, {"text": "On", "x": 266, "y": 548, "w": 16, "h": 14},
           {"text": "Off", "x": 310, "y": 548, "w": 18, "h": 14}, {"text": "Auto", "x": 356, "y": 548, "w": 28, "h": 14},
           {"text": "Bed", "x": 390, "y": 548, "w": 24, "h": 14}, {"text": "Leveling", "x": 420, "y": 548, "w": 48, "h": 14},
           {"text": "On", "x": 606, "y": 548, "w": 16, "h": 14}, {"text": "Off", "x": 650, "y": 548, "w": 18, "h": 14},
           {"text": "Send", "x": 606, "y": 608, "w": 34, "h": 14}]

    def test_each_switch_takes_the_first_on_and_off_after_its_label(self):
        on, off = orca.switch_labels(self.ROW, "Timelapse")
        self.assertEqual((on["x"], off["x"]), (266, 310))
        on, off = orca.switch_labels(self.ROW, "Leveling")
        self.assertEqual((on["x"], off["x"]), (606, 650))

    def test_on_is_placed_from_off_when_tesseract_drops_it(self):
        row = [w for w in self.ROW if w["text"] != "On"]
        on, off = orca.switch_labels(row, "Timelapse")
        self.assertEqual(on["x"], 310 - orca.ON_LEFT_OF_OFF)
        self.assertEqual(off["x"], 310)

    def test_a_missing_row_is_none(self):
        self.assertIsNone(orca.switch_labels(self.ROW[:1], "Timelapse"))
        self.assertIsNone(orca.switch_labels(self.ROW, "Flow"))

    def test_the_green_side_is_the_one_that_is_on(self):
        class Pixels:
            def pixel(self, x, y):              # green under On (x 266-282), gray under Off, dark on the text row
                return (1, 103, 91) if x < 300 and 565 <= y <= 567 else (76, 76, 85)   # a thin line, like Orca's
        on, off = orca.switch_labels(self.ROW, "Timelapse")
        self.assertTrue(orca.switch_is_on(Pixels(), on, off))
        self.assertFalse(orca.switch_is_on(Pixels(), off, on))
