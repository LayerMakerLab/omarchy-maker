"""maker-meshy's mesh handling and settings, offline: nothing here talks to Meshy.
    python3 -m unittest tests/test_maker_meshy.py
"""
import importlib.machinery
import importlib.util
import io
import json
import math
import os
import re
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("maker_meshy", os.path.join(ROOT, "bin", "maker-meshy"))
_spec = importlib.util.spec_from_loader("maker_meshy", _loader)
meshy = importlib.util.module_from_spec(_spec)
_loader.exec_module(meshy)

# a closed box, 2 triangles per side, standing on z = 0 and centred on x/y like Meshy's origin_at "bottom"
CORNERS = [(x, y, z) for x in (-1, 1) for y in (-2, 2) for z in (0, 6)]
SIDES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def box_triangles(scale=1.0, corners=CORNERS):
    tris = []
    for a, b, c, d in SIDES:
        for t in ((a, b, c), (a, c, d)):
            tris.append([corners[i][k] * scale for i in t for k in range(3)])
    return tris


def write_text(path, text):
    with open(path, "w") as out:
        out.write(text)


def write_binary(path, tris):
    with open(path, "wb") as out:
        out.write(b"test".ljust(80, b" ") + struct.pack("<I", len(tris)))
        for t in tris:
            out.write(struct.pack("<12fH", 0, 0, 0, *t, 0))


class Meshes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_closed_box_is_watertight(self):
        write_binary(self.path("box.stl"), box_triangles())
        self.assertEqual(meshy.edge_report(self.path("box.stl")), (0, 0))

    def test_missing_side_leaves_open_edges(self):
        write_binary(self.path("open.stl"), box_triangles()[:-2])
        open_edges, crowded = meshy.edge_report(self.path("open.stl"))
        self.assertEqual((open_edges, crowded), (4, 0))

    def test_extra_face_on_an_edge_is_non_manifold(self):
        tris = box_triangles()
        write_binary(self.path("fin.stl"), tris + [tris[0]])
        self.assertGreater(meshy.edge_report(self.path("fin.stl"))[1], 0)

    def test_millimetres_stay_millimetres(self):
        write_binary(self.path("mm.stl"), box_triangles(10))           # 20 x 40 x 60
        size, why = meshy.to_millimetres(self.path("mm.stl"), self.path("out.stl"))
        self.assertEqual(size, [20.0, 40.0, 60.0])
        self.assertEqual(why, "Meshy's real-world size")

    def test_metres_become_millimetres(self):
        write_binary(self.path("m.stl"), box_triangles(0.01))          # 0.02 x 0.04 x 0.06 "metres"
        size, _why = meshy.to_millimetres(self.path("m.stl"), self.path("out.stl"))
        self.assertEqual(size, [20.0, 40.0, 60.0])

    def test_too_big_shrinks_to_fit(self):
        write_binary(self.path("big.stl"), box_triangles(50))          # 100 x 200 x 300
        size, why = meshy.to_millimetres(self.path("big.stl"), self.path("out.stl"))
        self.assertEqual(max(size), meshy.FIT_MM)
        self.assertIn("shrunk to fit", why)

    def test_height_sets_z(self):
        write_binary(self.path("h.stl"), box_triangles(50))
        size, why = meshy.to_millimetres(self.path("h.stl"), self.path("out.stl"), height=60)
        self.assertEqual(size[2], 60.0)
        self.assertEqual(why, "60 mm tall")

    def test_output_sits_on_the_bed_centred(self):
        shifted = [(x + 7, y - 3, z + 2) for x, y, z in CORNERS]
        write_binary(self.path("off.stl"), box_triangles(10, shifted))
        meshy.to_millimetres(self.path("off.stl"), self.path("out.stl"))
        lo, hi = meshy.bounds(meshy.read_stl(self.path("out.stl")))
        self.assertAlmostEqual(lo[2], 0.0, places=3)
        self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3)
        self.assertAlmostEqual(lo[1] + hi[1], 0.0, places=3)

    def test_y_up_mesh_is_stood_on_z(self):
        y_up = [(x, z, -y) for x, y, z in CORNERS]                     # tall along Y, bottom at y = 0
        write_binary(self.path("yup.stl"), box_triangles(10, y_up))
        size, _why = meshy.to_millimetres(self.path("yup.stl"), self.path("out.stl"))
        self.assertEqual(size, [20.0, 40.0, 60.0])
        self.assertEqual(meshy.edge_report(self.path("out.stl")), (0, 0))

    def test_z_up_mesh_is_left_alone(self):
        tris = box_triangles(10)
        floats = [v for t in tris for v in [0, 0, 0] + t]
        lo, hi = meshy.bounds(floats)
        self.assertFalse(meshy.stand_up(floats, lo, hi))

    def test_ascii_stl_reads(self):
        with open(self.path("ascii.stl"), "w") as out:
            out.write("solid t\n")
            for t in box_triangles(10):
                out.write(" facet normal 0 0 0\n  outer loop\n")
                for i in range(0, 9, 3):
                    out.write("   vertex %g %g %g\n" % tuple(t[i:i + 3]))
                out.write("  endloop\n endfacet\n")
            out.write("endsolid t\n")
        size, _why = meshy.to_millimetres(self.path("ascii.stl"), self.path("out.stl"))
        self.assertEqual(size, [20.0, 40.0, 60.0])


def box_bytes(tris):
    return b"test".ljust(80, b" ") + struct.pack("<I", len(tris)) + b"".join(struct.pack("<12fH", 0, 0, 0, *t, 0) for t in tris)


class AgainstAFakeMeshy(unittest.TestCase):
    """generate() from request to model.stl against tests/fake_meshy.py: no credits, no network."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import fake_meshy
        self.fake_meshy = fake_meshy
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (meshy.API, meshy.OUT_ROOT, meshy.POLL_START, os.environ.get("MESHY_API_KEY"))
        meshy.OUT_ROOT, meshy.POLL_START = self.tmp.name, 0.01
        os.environ["MESHY_API_KEY"] = fake_meshy.KEY

    def tearDown(self):
        meshy.API, meshy.OUT_ROOT, meshy.POLL_START, key = self.saved
        if key is None:
            os.environ.pop("MESHY_API_KEY", None)
        else:
            os.environ["MESHY_API_KEY"] = key
        self.tmp.cleanup()
        sys.path.remove(os.path.join(ROOT, "tests"))

    def serve(self, **kwargs):
        fake = self.fake_meshy.FakeMeshy(**kwargs).start()
        self.addCleanup(fake.stop)
        meshy.API = fake.url
        return fake

    def test_open_mesh_is_repaired_and_sized(self):
        fake = self.serve(model=box_bytes(box_triangles(10)[:-2]), repaired=box_bytes(box_triangles(10)))
        with redirect_stdout(io.StringIO()):
            record = meshy.generate("text", "a test box", {"quiet": True, "height": 40})
        self.assertTrue(record["repaired"] and record["watertight"])
        self.assertEqual(record["size_mm"][2], 40.0)
        self.assertEqual(record["edges"], {"open": 4, "shared_by_3_or_more": 0})
        self.assertTrue(os.path.isfile(record["model"]) and record["model"].endswith("/a-test-box/a-test-box.stl"))
        self.assertEqual(meshy.edge_report(record["model"]), (0, 0))
        posted = {path: body for method, path, body in fake.calls if method == "POST"}
        self.assertEqual(posted["/openapi/v2/text-to-3d"]["mode"], "preview")
        self.assertEqual(posted["/openapi/v2/text-to-3d"]["origin_at"], "bottom")
        self.assertIn("stl", posted["/openapi/v2/text-to-3d"]["target_formats"])
        self.assertEqual(posted["/openapi/v1/print/repair"]["model_url"], fake.url + "/files/model.stl")

    def test_closed_mesh_skips_the_paid_repair(self):
        fake = self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        with redirect_stdout(io.StringIO()):
            record = meshy.generate("text", "a closed box", {"quiet": True})
        self.assertFalse(record["repaired"])
        self.assertTrue(record["watertight"])
        self.assertNotIn("/openapi/v1/print/repair", [path for _m, path, _b in fake.calls])

    def test_pictures_go_as_data_uris_without_texture(self):
        fake = self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        picture = os.path.join(self.tmp.name, "front.png")
        with open(picture, "wb") as out:
            out.write(self.fake_meshy.tiny_png())
        with redirect_stdout(io.StringIO()):
            meshy.generate("image", [picture], {"quiet": True})
        body = next(b for m, p, b in fake.calls if p == "/openapi/v1/image-to-3d")
        self.assertTrue(body["image_url"].startswith("data:image/png;base64,"))
        self.assertIs(body["should_texture"], False)

    def test_failed_repair_keeps_the_mesh_as_made(self):
        fake = self.serve(model=box_bytes(box_triangles(10)[:-2]))
        fake.files.pop("repaired.stl")                                  # the repaired file never arrives
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            record = meshy.generate("text", "a box whose repair fails", {"quiet": True})
        self.assertFalse(record["repaired"])
        self.assertFalse(record["watertight"])
        self.assertIn("error", record["repair"])
        self.assertTrue(os.path.isfile(record["model"]))

    def test_long_descriptions_get_short_names(self):
        fake = self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        prompt = "a very detailed medieval stone lantern with moss growing between the bricks and a little door"
        with redirect_stdout(io.StringIO()):
            record = meshy.generate("text", prompt, {"quiet": True})
        self.assertLessEqual(len(record["name"]), 41)
        self.assertTrue(record["name"].endswith("\u2026"))
        self.assertEqual(record["prompt"], prompt)

    def test_a_cut_off_job_is_finished_later(self):
        self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        with redirect_stdout(io.StringIO()):
            record = meshy.begin("text", "a box left behind", {"quiet": True, "height": 30})   # the process died here
            self.assertEqual(meshy.unfinished(), [record["folder"]])
            done = meshy.finish(record["folder"], {"quiet": True})
        self.assertEqual(done["size_mm"][2], 30.0)                                          # the height it began with
        self.assertIn("meshy_builds", done["timings"])
        self.assertEqual(meshy.unfinished(), [])
        self.assertFalse(os.path.exists(os.path.join(record["folder"], ".working")))

    def test_a_job_being_finished_is_left_alone(self):
        self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        with redirect_stdout(io.StringIO()):
            record = meshy.begin("text", "a busy box", {"quiet": True})
        busy = meshy.job_lock(record["folder"])
        self.addCleanup(busy.close)
        self.assertEqual(meshy.unfinished(), [])
        with self.assertRaises(meshy.Stop):
            meshy.finish(record["folder"], {"quiet": True})

    def test_a_job_meshy_failed_is_not_offered_again(self):
        self.serve(model=box_bytes(box_triangles(10)), fail=True)
        with redirect_stdout(io.StringIO()), self.assertRaises(meshy.Failed):
            meshy.generate("text", "a box meshy refuses", {"quiet": True})
        self.assertEqual(meshy.unfinished(), [])
        folder = os.path.join(self.tmp.name, "a-box-meshy-refuses")
        with open(os.path.join(folder, "meshy.json")) as handle:
            self.assertIn("test server said no", json.load(handle)["failed"])

    def test_jobs_are_followed_over_the_stream(self):
        fake = self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        with redirect_stdout(io.StringIO()):
            meshy.generate("text", "a streamed box", {"quiet": True})
        gets = [p for m, p, b in fake.calls if m == "GET" and p.startswith("/openapi/v2/text-to-3d/")]
        self.assertTrue(gets[0].endswith("/stream"))                                # followed over the stream
        self.assertEqual(len([p for p in gets if re.match(r"^/openapi/v2/text-to-3d/text-\d+$", p)]), 1)   # fetched once, not polled

    def test_without_a_stream_jobs_are_polled(self):
        fake = self.serve(model=box_bytes(box_triangles(10)), watertight=True)
        fake.streams = False
        with redirect_stdout(io.StringIO()):
            record = meshy.generate("text", "a polled box", {"quiet": True})
        self.assertTrue(record["watertight"])
        gets = [p for m, p, b in fake.calls if m == "GET" and re.match(r"^/openapi/v2/text-to-3d/text-\d+$", p)]
        self.assertGreaterEqual(len(gets), 2)                                           # polled until done

    def test_wrong_key_stops_with_a_clear_message(self):
        self.serve(model=box_bytes(box_triangles(10)))
        os.environ["MESHY_API_KEY"] = "not-the-key"
        with self.assertRaises(meshy.Stop) as stopped:
            meshy.call("GET", "/openapi/v1/balance")
        self.assertIn("refused the API key", str(stopped.exception))



class WhichWayUp(unittest.TestCase):
    """The orientation search: it reads areas off the mesh, so every case here is a shape with known ones."""

    @staticmethod
    def slab(lo, hi):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        out = []
        for a, b, c, d in SIDES:
            for tri in ((a, b, c), (a, c, d)):
                out.extend([0.0, 0.0, 0.0] + [v for i in tri for v in corners[i]])
        return out

    def orient(self, floats):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = os.path.join(tmp, "in.stl"), os.path.join(tmp, "out.stl")
            meshy.write_stl(source, floats)
            found = meshy.orient_file(source, target)
            found["bytes"] = os.path.getsize(target) if os.path.exists(target) else 0
            return found

    def test_a_post_with_a_shelf_is_laid_down(self):
        found = self.orient(self.slab((0, 0, 0), (10, 10, 40)) + self.slab((10, 0, 30), (40, 10, 40)))
        self.assertIn("turned", found["turn"])
        self.assertGreater(found["as_it_is"]["overhang"], 2.0)          # the shelf hangs in the air
        self.assertLess(found["best"]["overhang"], 0.1)                 # laid down, nothing hangs
        self.assertGreater(found["best"]["base"], found["as_it_is"]["base"])
        self.assertGreater(found["bytes"], 0)

    def test_a_box_that_already_lies_flat_is_left_alone(self):
        found = self.orient(self.slab((0, 0, 0), (40, 30, 5)))
        self.assertEqual(found["turn"], "already the right way up")
        self.assertEqual(found["bytes"], 0)                             # nothing written when nothing turns
        self.assertLess(found["best"]["overhang"], 0.1)

    def test_a_way_up_it_would_fall_over_from_is_refused(self):
        # a wide plate on a thin spike: balanced on the spike there is less overhang, but it cannot stand
        floats = self.slab((-15, -15, 10), (15, 15, 14)) + self.slab((-1, -1, 0), (1, 1, 10))
        scores = [meshy.score_down(*meshy.facet_table(floats)[:3], down) for down in
                  ((0, 0, -1), (0, 0, 1))]
        on_the_spike, on_the_plate = scores                             # (0, 0, -1) rests on the spike's tip
        self.assertFalse(on_the_spike["stands"], "4 mm2 of spike is not something to stand a print on")
        self.assertTrue(on_the_plate["stands"])
        self.assertIs(meshy.rank(scores)[0], on_the_plate)

    def test_the_turn_puts_the_chosen_side_against_the_plate(self):
        for down in ((0, 0, 1), (1, 0, 0), (0, -1, 0), (0.6, 0.0, 0.8)):
            length = sum(v * v for v in down) ** 0.5
            unit = tuple(v / length for v in down)
            matrix = meshy.rotation_to_down(unit)
            turned = [sum(matrix[row][col] * unit[col] for col in range(3)) for row in range(3)]
            self.assertAlmostEqual(turned[2], -1.0, places=6, msg=str(down))

    def test_overhang_is_measured_against_the_threshold(self):
        floats = self.slab((0, 0, 0), (20, 20, 10))
        normals, areas, verts = meshy.facet_table(floats)
        flat = meshy.score_down(normals, areas, verts, (0, 0, -1))
        self.assertLess(flat["overhang"], 0.1)                          # a box has no overhang either way up
        self.assertAlmostEqual(flat["base"], 4.0, places=1)             # 20 x 20 mm on the plate is 4 cm2
        self.assertAlmostEqual(flat["height"], 10.0, places=3)


    def test_a_description_also_asks_for_a_shape_that_prints_without_support(self):
        asked = meshy.printable_prompt("a small cute turtle figurine")
        self.assertTrue(asked.startswith("a small cute turtle figurine, "))
        self.assertIn("own solid base", asked)
        self.assertLessEqual(len(asked), 800)

    def test_a_description_that_already_says_it_is_left_as_typed(self):
        for words in ("a dragon, printable for FDM", "a bracket with no supports", "a vase for 3d printing"):
            self.assertEqual(meshy.printable_prompt(words), words)

    def test_a_long_description_still_fits_meshys_limit(self):
        asked = meshy.printable_prompt("a " + "very " * 300 + "long description")
        self.assertLessEqual(len(asked), 800)
        self.assertIn("own solid base", asked)


class CuttingIntoParts(unittest.TestCase):
    """Cutting, capping and socketing, checked on a box where every number is known."""

    @staticmethod
    def box(lo, hi):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        out = []
        for a, b, c, d in SIDES:
            for tri in ((a, b, c), (a, c, d)):
                out.extend([0.0, 0.0, 0.0] + [v for i in tri for v in corners[i]])
        return out

    def split(self, floats, heights, **options):
        tmp = tempfile.mkdtemp()
        source = os.path.join(tmp, "in.stl")
        meshy.write_stl(source, floats)
        return meshy.split_file(source, heights, os.path.join(tmp, "parts"), **options)

    def test_two_parts_that_add_up_and_both_hold_water(self):
        found = self.split(self.box((-20, -15, 0), (20, 15, 40)), [18.0])
        names = [p["name"] for p in found["parts"]]
        self.assertEqual(names, ["part1", "part2"])
        self.assertEqual([p["size"][2] for p in found["parts"]], [18.0, 22.0])
        for part in found["parts"]:
            self.assertEqual(part["open_edges"], 0, part["name"])       # every part is closed
            self.assertGreater(part["volume_cm3"], 0, part["name"])     # and not inside out
            self.assertEqual(part["sockets"], 2)
        hole = math.pi * found["socket_radius"] ** 2 * found["socket_depth"] / 1000.0
        self.assertAlmostEqual(found["parts"][0]["volume_cm3"], 40 * 30 * 18 / 1000.0 - 2 * hole, delta=0.1)
        self.assertAlmostEqual(found["parts"][1]["volume_cm3"], 40 * 30 * 22 / 1000.0 - 2 * hole, delta=0.1)

    def test_three_parts_from_two_cuts_and_the_middle_gets_both_ends(self):
        found = self.split(self.box((-20, -15, 0), (20, 15, 60)), [20.0, 40.0])
        self.assertEqual([p["size"][2] for p in found["parts"]], [20.0, 20.0, 20.0])
        self.assertEqual([p["sockets"] for p in found["parts"]], [2, 4, 2])
        for part in found["parts"]:
            self.assertEqual(part["open_edges"], 0, part["name"])

    def test_the_dowel_fits_its_socket_with_the_play_we_tested(self):
        found = self.split(self.box((-20, -15, 0), (20, 15, 40)), [18.0])
        self.assertAlmostEqual(found["socket_radius"] - meshy.PIN_MM[0] / 2, meshy.PIN_PLAY, places=6)
        pin = meshy.read_stl(found["dowel"])
        lo, hi = meshy.bounds(pin)
        self.assertAlmostEqual(hi[2] - lo[2], meshy.PIN_MM[1], places=3)     # as long as it says
        self.assertLessEqual(hi[0] - lo[0], meshy.PIN_MM[0] + 1e-6)         # and no wider
        self.assertGreater(meshy.volume_of(pin), 0)

    def test_a_cut_where_there_is_nothing_says_so(self):
        with self.assertRaises(meshy.Stop):
            self.split(self.box((-20, -15, 0), (20, 15, 40)), [60.0])

    def test_sockets_land_inside_the_cut_face_with_meat_around_them(self):
        ring = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
        spots, _ring = meshy.pin_places([ring], 2, 3.3)
        self.assertEqual(len(spots), 2)
        for spot in spots:
            self.assertTrue(meshy.room_at(spot, [ring], 3.3 + 1.5))
        self.assertGreater(math.dist(spots[0], spots[1]), 3 * 3.3)

    def test_a_socket_narrower_than_the_face_is_all_it_takes(self):
        thin = [(-4, -4), (4, -4), (4, 4), (-4, 4)]      # 8 mm across: a 6.6 mm socket would break out
        spots, _ring = meshy.pin_places([thin], 2, 3.3)
        self.assertEqual(spots, [])



class Settings(unittest.TestCase):
    def test_key_file_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.path.join(tmp, "env")
            saved, saved_env = meshy.KEY_FILE, os.environ.pop("MESHY_API_KEY", None)
            meshy.KEY_FILE = env
            try:
                for line in ("MESHY_API_KEY=msy_abc", "export MESHY_API_KEY='msy_abc'", '  MESHY_API_KEY="msy_abc"\n'):
                    write_text(env, "# Meshy\n" + line + "\n")
                    self.assertEqual(meshy.api_key(), "msy_abc")
                write_text(env, "# nothing here\n")
                with self.assertRaises(meshy.Stop):
                    meshy.api_key()
            finally:
                meshy.KEY_FILE = saved
                if saved_env is not None:
                    os.environ["MESHY_API_KEY"] = saved_env

    def test_folder_names(self):
        self.assertEqual(meshy.slug("A small cartoon Owl, on a round base!"), "a-small-cartoon-owl-on-a")
        with tempfile.TemporaryDirectory() as tmp:
            saved = meshy.OUT_ROOT
            meshy.OUT_ROOT = tmp
            try:
                first, second = meshy.new_folder("owl"), meshy.new_folder("owl")
            finally:
                meshy.OUT_ROOT = saved
            self.assertEqual([os.path.basename(first), os.path.basename(second)], ["owl", "owl-2"])


if __name__ == "__main__":
    unittest.main()
