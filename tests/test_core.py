"""camwall's core, without the network: python3 -m unittest discover tests"""

import json
import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

os.environ["CAMWALL_DATA"] = tempfile.mkdtemp(prefix="camwall-test-")

from app import catalogue as catalogue_module, devices, mine, paths, relay, sets, withdrawn  # noqa: E402
from app import settings as prefs  # noqa: E402


def a_list(module, cameras, state="IA"):
    return {"module": module, "source": {"name": module, "state": state, "covers": "", "site": ""},
            "fetched": "2026-11-08T00:00:00+00:00", "cameras": cameras, "origin": "shipped"}


def camera(cam_id, name, lat=41.6, lon=-93.6, image=None, video=None):
    cam = {"id": cam_id, "name": name, "lat": lat, "lon": lon}
    if image:
        cam["image"] = image
    if video:
        cam["video"], cam["video_type"] = video, "hls"
    return cam


class Settings(unittest.TestCase):
    def test_good_and_bad_values(self):
        self.assertEqual(prefs.update({"theme": "dark"})["theme"], "dark")
        for bad in ({"theme": "pink"}, {"units": "furlongs"}, {"muted": "yes"}, {"cycle": 7}, {"cycle": True},
                    {"home": {"label": "x", "lat": 100, "lon": 0, "state": "IA"}}, {"home": {"label": "x", "lat": 1, "lon": 1, "state": "ZZ"}},
                    {"quiet": {"from": "25:00", "to": "07:00"}}, {"nonsense": 1}, {"sources": {"BAD NAME": True}}):
            with self.assertRaises((ValueError, KeyError, TypeError), msg=bad):
                prefs.update(bad)

    def test_switching_one_source_keeps_the_others(self):
        prefs.update({"sources": {"a_one": True}})
        prefs.update({"sources": {"b_two": False}})
        self.assertEqual(prefs.get()["sources"], {"a_one": True, "b_two": False})
        prefs.update({"sources": {"a_one": None}})  # back to its default
        self.assertEqual(prefs.get()["sources"], {"b_two": False})

    def test_keys_are_kept_privately(self):
        prefs.set_key("ny_511ny", " abc123 ")
        self.assertEqual(prefs.keys()["ny_511ny"], "abc123")
        if os.name == "posix":  # (Windows has no such mode bits: the file is in the user's own folder)
            self.assertEqual(paths.KEYS.stat().st_mode & 0o777, 0o600)
        prefs.set_key("ny_511ny", None)
        self.assertNotIn("ny_511ny", prefs.keys())

    def test_the_map_uses_openstreetmap_unless_another_provider_is_set(self):
        self.assertEqual(prefs.tiles(), prefs.OSM)
        mine = {"url": "https://tiles.example.com/{z}/{x}/{y}.png?key=abc", "credit": " © Example ", "link": None}
        prefs.update({"tiles": mine})
        self.assertEqual(prefs.tiles(), {**mine, "credit": "© Example"})
        for bad in ({**mine, "url": "http://tiles.example.com/{z}/{x}/{y}.png"},
                    {**mine, "url": "https://tiles.example.com/tile.png"},
                    {**mine, "url": 'https://tiles.example.com/{z}/{x}/{y}.png"><script>'},
                    {**mine, "credit": ""}, {**mine, "link": "javascript:alert(1)"}):
            with self.assertRaises((ValueError, KeyError, TypeError), msg=bad):
                prefs.update({"tiles": bad})
        prefs.update({"tiles": None})
        self.assertEqual(prefs.tiles(), prefs.OSM)
        prefs.update({"tiles": {**mine, "url": "https://{s}.tiles.example.com/{z}/{x}/{y}.png"}})
        with self.assertRaises(ValueError):
            prefs.update({"tiles": {**mine, "url": "https://tiles.example.com:99999/{z}/{x}/{y}.png"}})
        prefs.update({"tiles": None})


class Shipped(unittest.TestCase):
    def test_every_source_loads_on_this_python(self):
        import importlib
        import sources
        for module in sources.modules():
            with self.subTest(module):
                code = importlib.import_module(f"sources.{module}")
                self.assertTrue(isinstance(code.SOURCE, dict) and callable(code.cameras))


    def test_no_restricted_source_is_shipped(self):
        import gzip
        import importlib
        for listed in (paths.DATA / "catalogue").glob("*.json.gz"):
            module = listed.name[:-len(".json.gz")]
            code = importlib.import_module(f"sources.{module}")
            self.assertFalse(code.SOURCE.get("restricted") or code.SOURCE.get("key"), module)
            self.assertTrue(getattr(code, "SHIPPED", True), module)
            self.assertFalse(json.loads(gzip.decompress(listed.read_bytes()))["source"].get("restricted"), module)
            self.assertNotIn(module, withdrawn._read(withdrawn.SHIPPED), module)


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.c = catalogue_module.Catalogue()

    def index(self, *lists):
        self.c.lists = {data["module"]: data for data in lists}
        self.c._index()

    def test_a_list_from_a_source_camwall_no_longer_has_isnt_used(self):
        gone = paths.CATALOGUE / "zz_gone.json"
        gone.parent.mkdir(parents=True, exist_ok=True)
        gone.write_text(json.dumps(a_list("zz_gone", [camera("1", "Somewhere", image="https://x/1.jpg")])))
        self.c.load()
        self.assertNotIn("zz_gone", self.c.lists)
        gone.unlink()

    def test_an_old_list_doesnt_promise_video_its_source_no_longer_gives(self):
        self.index(a_list("tn_franklin", [{**camera("1", "Main St", image="https://x/1.jpg"), "video_type": "hls"}]))
        self.assertEqual(self.c.media("tn_franklin/1", {}), 1)  # (a picture only)

    def test_same_picture_listed_once_under_the_bigger_source(self):
        self.index(a_list("big", [camera("1", "I-71 at A", image="https://x/1.jpg"), camera("2", "I-71 at B", image="https://x/2.jpg")]),
                   a_list("small", [camera("9", "Something else", image="https://x/1.jpg")]))
        self.assertEqual(self.c.view({})[0], {"small/9"})

    def test_picture_and_video_copies_are_linked(self):
        self.index(a_list("pics", [camera("1", "IH-45 @ Main", image="https://p/1.jpg"), camera("2", "x", image="https://p/2.jpg")]),
                   a_list("vids", [camera("a", "IH-45 @ Main", lat=41.6002, video="https://v/a.m3u8")]))
        self.assertEqual(self.c.view({}), ({"vids/a"}, {"pics/1": "vids/a"}))
        self.assertEqual(self.c.media("pics/1", {}), 3)
        self.assertEqual(self.c.part("pics/1", "video", {})["id"], "a")
        # with the video's source switched off, there's no video to be had through it
        off = {"sources": {"vids": False}}
        self.assertEqual(self.c.view(off), ({"vids/a"}, {}))
        self.assertEqual(self.c.media("pics/1", off), 1)
        self.assertEqual(self.c.part("pics/1", "video", off)["id"], "1")

    def test_a_camera_stays_listed_when_its_best_copy_is_switched_off(self):
        self.index(a_list("big", [camera("1", "I-71 at A", image="https://x/1.jpg"), camera("2", "B", image="https://x/2.jpg")]),
                   a_list("small", [camera("9", "I-71 at A", image="https://x/1.jpg")]))
        self.assertEqual(self.c.view({"sources": {"big": False}})[0], {"big/1"})

    def test_another_sources_views_with_that_name_are_all_kept_in_either_order(self):
        one = a_list("a_dot", [camera("1", "I-35 at Main", image="https://a/1.jpg")])
        two = a_list("b_city", [camera("n", "I-35 at Main", image="https://b/n.jpg"),
                                camera("s", "I-35 at Main", image="https://b/s.jpg")])
        for lists in ((one, two), (two, one)):
            self.index(*lists)
            self.assertEqual(self.c.view({})[0], {"a_dot/1"}, [data["module"] for data in lists])

    def test_one_sources_views_with_one_name_are_all_kept(self):
        self.index(a_list("one", [camera("n", "IA-28 at Main", image="https://x/n.jpg"), camera("s", "IA-28 at Main", image="https://x/s.jpg")]))
        self.assertEqual(self.c.view({})[0], set())

    def test_a_sources_unavailable_card_doesnt_merge_its_cameras(self):
        card = "https://x/novideo.jpg"
        self.index(a_list("one", [camera(str(n), f"Camera {n}", lat=30 + n, image=card) for n in range(4)]))
        self.assertEqual(self.c.view({})[0], set())

    def test_a_source_can_say_which_camera_is_the_same(self):
        copy = camera("c", "Other words", lat=40.0, image="https://y/c.jpg")
        copy["extra"] = {"same_as": "oh_big:1"}
        self.index(a_list("oh_big", [camera("1", "I-71 at A", image="https://x/1.jpg"), camera("2", "B", image="https://x/2.jpg")]),
                   a_list("oh_small", [copy]))
        self.assertEqual(self.c.view({})[0], {"oh_small/c"})

    def test_restricted_sources_are_off_until_switched_on(self):
        data = a_list("strict", [camera("1", "A", image="https://x/1.jpg")])
        data["source"]["restricted"] = "no apps"
        self.index(data)
        self.c._modules = {"strict": data["source"]}
        self.assertIsNone(self.c.get("strict/1", {"sources": {}}))
        self.assertIsNotNone(self.c.get("strict/1", {"sources": {"strict": True}}))

    def test_the_users_own_are_never_merged_with_public_ones(self):
        self.index(a_list("dot", [camera("1", "Front door", image="https://x/1.jpg")]))
        self.c.set_mine([{**camera("ab12cd34", "Front door"), "image": "mine://ab12cd34", "state": "IA"}], mine.SOURCE)
        self.assertEqual(self.c.view({})[0], set())


class Withdrawn(unittest.TestCase):
    def setUp(self):
        self.c = catalogue_module.Catalogue()
        data = a_list("zz_asked", [camera("1", "A", image="https://x/1.jpg")])
        self.c.lists, self.c._modules = {"zz_asked": data}, {"zz_asked": data["source"]}
        self.c._index()
        withdrawn._withdrawn = None
        self.addCleanup(setattr, withdrawn, "_withdrawn", None)
        self.addCleanup(withdrawn.KEPT.unlink, missing_ok=True)

    def fetched(self, body, status=200):
        return unittest.mock.patch.object(relay, "fetch", return_value=(status, {}, body))

    def test_a_withdrawn_source_is_off_whatever_the_user_chose(self):
        self.assertIsNotNone(self.c.get("zz_asked/1", {"sources": {"zz_asked": True}}))
        with self.fetched(b'{"withdrawn": {"zz_asked": "ZZ DOT asked"}}'):
            self.assertTrue(withdrawn.check())
        self.assertIsNone(self.c.get("zz_asked/1", {"sources": {"zz_asked": True}}))
        self.assertEqual(self.c.summary({"sources": {}}, {})[0]["withdrawn"], "ZZ DOT asked")

    def test_the_pages_list_changes_with_it(self):
        import gzip
        self.c.listing({"sources": {}})
        version = self.c.version
        with self.fetched(b'{"withdrawn": {"zz_asked": ""}}'):
            withdrawn.check()
        self.c.withdrawn_changed()
        self.assertEqual(json.loads(gzip.decompress(self.c.listing({"sources": {}})))["cameras"], [])
        self.assertGreater(self.c.version, version)

    def test_the_list_read_last_is_kept_and_a_bad_one_changes_nothing(self):
        with self.fetched(b'{"withdrawn": {"zz_asked": ""}}'):
            withdrawn.check()
        withdrawn._withdrawn = None  # (as when camwall starts again, offline)
        self.assertIn("zz_asked", withdrawn.current())
        for bad in (b"<html>", b'{"withdrawn": ["zz_asked"]}', b"[" * 200000, b"{}" + b" " * withdrawn.MAX_SIZE):
            with self.subTest(bad[:20]), self.fetched(bad), self.assertRaises(ValueError):
                withdrawn.check()
        with self.fetched(b"", 404), self.assertRaises(OSError):
            withdrawn.check()
        self.assertIn("zz_asked", withdrawn.current())

    def test_it_can_only_turn_sources_off(self):
        with self.fetched(b'{"withdrawn": {"../x": "", "zz_asked": 5}, "sources": {"zz_other": true}}'):
            withdrawn.check()
        self.assertEqual(withdrawn.current(), {"zz_asked": ""})


class Sets(unittest.TestCase):
    def test_validation(self):
        c = catalogue_module.Catalogue()
        c.lists = {"dot": a_list("dot", [camera("1", "A", image="https://x/1.jpg")])}
        c._modules = {"dot": c.lists["dot"]["source"]}
        c._index()
        ok = sets.save({"sets": [{"id": "home", "name": "Home", "cameras": ["dot/1"]}], "alerts": {"dot/1": ["fire", "police"]}}, c, {})
        self.assertEqual(ok["alerts"], {"dot/1": ["police", "fire"]})  # (in the usual order)
        for bad in ({"sets": [], "alerts": {}},
                    {"sets": [{"id": "Bad Id", "name": "x", "cameras": []}], "alerts": {}},
                    {"sets": [{"id": "a", "name": "x", "cameras": ["dot/nope"]}], "alerts": {}},
                    {"sets": [{"id": "a", "name": "x", "cameras": ["dot/1", "dot/1"]}], "alerts": {}},
                    {"sets": [{"id": "a", "name": "x", "cameras": []}], "alerts": {"dot/1": ["aliens"]}}):
            with self.assertRaises((ValueError, KeyError, TypeError), msg=bad):
                sets.save(bad, c, {})

    def test_no_alerts_where_the_terms_forbid_saving_pictures(self):
        c = catalogue_module.Catalogue()
        c.lists = {"dot": a_list("dot", [camera("1", "A", image="https://x/1.jpg")]),
                   "ma": a_list("ma", [camera("2", "B", lat=42.0, image="https://y/2.jpg")], state="MA")}
        c._modules = {"dot": c.lists["dot"]["source"], "ma": {**c.lists["ma"]["source"], "no_capture": "No capturing images"}}
        c._index()
        saved = sets.save({"sets": [{"id": "home", "name": "Home", "cameras": ["dot/1", "ma/2"]}],
                           "alerts": {"dot/1": ["fire"], "ma/2": ["fire"]}}, c, {})
        self.assertEqual(saved["alerts"], {"dot/1": ["fire"]})
        self.assertEqual(saved["cameras"]["ma/2"]["no_alerts"], "No capturing images")
        self.assertIsNone(saved["cameras"]["dot/1"]["no_alerts"])

    def test_a_sources_credit_and_disclaimer_go_with_its_cameras(self):
        c = catalogue_module.Catalogue()
        c.lists = {"or": a_list("or", [camera("1", "A", image="https://x/1.jpg")], state="OR")}
        c._modules = {"or": {**c.lists["or"]["source"], "credit": "ODOT", "disclaimer": "As is."}}
        c._index()
        saved = sets.save({"sets": [{"id": "home", "name": "Home", "cameras": ["or/1"]}], "alerts": {}}, c, {})
        self.assertEqual((saved["cameras"]["or/1"]["credit"], saved["cameras"]["or/1"]["disclaimer"]), ("ODOT", "As is."))
        self.assertEqual(c.detail("or/1", {})["source"]["credit"], "ODOT")

    def test_a_camera_no_longer_listed_stays(self):
        c = catalogue_module.Catalogue()
        c.lists = {"dot": a_list("dot", [camera("1", "A", image="https://x/1.jpg")])}
        c._modules = {"dot": c.lists["dot"]["source"]}
        c._index()
        sets.save({"sets": [{"id": "home", "name": "Home", "cameras": ["dot/1"]}], "alerts": {}}, c, {})
        c.lists = {}
        c._index()
        saved = sets.save({"sets": [{"id": "home", "name": "Home!", "cameras": ["dot/1"]}], "alerts": {}}, c, {})
        self.assertTrue(saved["cameras"]["dot/1"]["gone"])
        self.assertEqual(saved["cameras"]["dot/1"]["name"], "A")


class Relay(unittest.TestCase):
    def test_only_public_web_addresses(self):
        for url in ("http://127.0.0.1/", "http://localhost:8780/api/state", "http://192.168.1.1/", "http://10.0.0.1/",
                    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "file:///etc/passwd", "ftp://example.com/"):
            with self.assertRaises(relay.Refused, msg=url):
                relay.open_url(url)

    def test_playlists_are_rewritten_to_come_back(self):
        text = "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\nseg1.ts\nhttps://cdn.example.com/seg2.ts\n"
        out = relay.rewrite("dot/1", "https://v.example.com/live/index.m3u8", text)
        self.assertIn('URI="x?u=https%3A%2F%2Fv.example.com%2Flive%2Fkey.bin"', out)
        self.assertIn("x?u=https%3A%2F%2Fv.example.com%2Flive%2Fseg1.ts", out)
        self.assertTrue(relay.named("dot/1", "https://cdn.example.com/seg2.ts"))
        self.assertFalse(relay.named("dot/1", "https://evil.example.com/x"))
        self.assertFalse(relay.named("dot/2", "https://cdn.example.com/seg2.ts"))


class Pictures(unittest.TestCase):
    def test_a_picture_three_cameras_share_is_a_stand_in(self):
        pic = relay.Picture(0, b"", '"same"', None, "image/jpeg", None, None)
        relay._seen_with['"same"'] = {"https://a/1.jpg", "https://a/2.jpg"}
        self.assertFalse(relay.stand_in(pic))
        relay._seen_with['"same"'].add("https://a/3.jpg")
        self.assertTrue(relay.stand_in(pic))


class Certificates(unittest.TestCase):
    def test_reading_a_certificate(self):
        from sources import tls
        # a minimal certificate-shaped DER: SEQ { SEQ { [0]{INT 2}, INT 1, SEQ{}, issuer SEQ{a}, SEQ{}, subject SEQ{b} } }
        tbs_fields = b"\xa0\x03\x02\x01\x02" + b"\x02\x01\x01" + b"\x30\x00" + b"\x30\x01a" + b"\x30\x00" + b"\x30\x01b"
        tbs = b"\x30" + bytes([len(tbs_fields)]) + tbs_fields
        cert = b"\x30" + bytes([len(tbs)]) + tbs
        self.assertEqual(tls._issuer_and_subject(cert), (b"\x30\x01a", b"\x30\x01b"))
        uri = b"http://x.example/ca.crt"
        self.assertEqual(tls._issuers_url(b"junk" + tls.CA_ISSUERS + b"\x86" + bytes([len(uri)]) + uri), uri.decode())


class Pairing(unittest.TestCase):
    def test_a_code_pairs_one_device(self):
        code = devices.new_code()["code"]
        token = devices.pair(code, "Tablet")
        self.assertTrue(devices.check(token))
        self.assertFalse(devices.check("nope"))
        with self.assertRaises(PermissionError):
            devices.pair(code, "Again")
        stored = json.loads(devices.DEVICES.read_text())
        self.assertNotIn(token, json.dumps(stored))  # (only its hash)

    def test_wrong_codes_lock_even_a_new_code_for_a_while(self):
        devices.new_code()
        for _ in range(devices.MAX_WRONG):
            with self.assertRaises(PermissionError):
                devices.pair("x", "Guess")
        code = devices.new_code()["code"]
        with self.assertRaises(PermissionError):  # (a new code gives a guesser no more tries)
            devices.pair(code, "Real")
        devices._locked_until = time.monotonic()  # (the lock has run out)
        self.assertTrue(devices.check(devices.pair(code, "Real")))


class Tiles(unittest.TestCase):
    PNG = b"\x89PNG\r\n\x1a\n" + b"tile"

    def setUp(self):
        from app import tiles
        self.tiles, self.asked = tiles, []
        self.answer = (200, {}, self.PNG)
        patcher = unittest.mock.patch.object(relay, "fetch", lambda url: self.asked.append(url) or self.answer)
        patcher.start()
        self.addCleanup(patcher.stop)
        prefs.update({"tiles": None})

    def test_a_tile_is_fetched_once_then_kept(self):
        self.assertEqual(self.tiles.tile(3, 2, 1), (self.PNG, "image/png"))
        self.assertEqual(self.tiles.tile(3, 2, 1), (self.PNG, "image/png"))
        self.assertEqual(self.asked, ["https://tile.openstreetmap.org/3/2/1.png"])

    def test_only_tiles_that_exist_and_only_pictures(self):
        for z, x, y in ((20, 0, 0), (2, 4, 0), (2, 0, -1)):
            with self.assertRaises(ValueError):
                self.tiles.tile(z, x, y)
        self.answer = (200, {}, b"<html>not a tile</html>")
        with self.assertRaises(OSError):
            self.tiles.tile(4, 1, 1)

    def test_a_kept_tile_is_used_when_the_server_fails(self):
        self.tiles.tile(5, 1, 1)
        old = time.time() - self.tiles.KEEP - 60
        for file in self.tiles.CACHE.glob("*/5/1/1"):
            os.utime(file, (old, old))
        self.answer = (503, {}, b"")
        self.assertEqual(self.tiles.tile(5, 1, 1), (self.PNG, "image/png"))
        self.assertEqual(len(self.asked), 2)

    def test_each_provider_has_its_own_tiles(self):
        self.tiles.tile(6, 1, 1)
        prefs.update({"tiles": {"url": "https://tiles.example.com/{z}/{x}/{y}.png?key=k", "credit": "Example"}})
        self.tiles.tile(6, 1, 1)
        self.assertEqual(self.asked[-1], "https://tiles.example.com/6/1/1.png?key=k")
        self.assertEqual(len(self.asked), 2)


class TilesThroughTheServer(unittest.TestCase):
    def setUp(self):
        import http.server
        import threading
        from app import server, tiles
        self.tiles = tiles
        prefs.update({"tiles": {"url": "https://tiles.example.com/{z}/{x}/{y}.png?key=secret", "credit": "Example"}})
        png = (200, {}, b"\x89PNG\r\n\x1a\n" + b"tile")
        patcher = unittest.mock.patch.object(relay, "fetch", lambda url: png)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path, **headers):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request("GET", path, headers={"Host": f"127.0.0.1:{self.httpd.server_address[1]}", **headers})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_the_pages_get_the_credit_not_the_address(self):
        status, body = self.get("/api/map")
        self.assertEqual(json.loads(body), {"id": self.tiles.provider(), "credit": "Example", "link": None})
        self.assertNotIn(b"secret", body)

    def test_tiles_of_the_provider_in_use_only(self):
        self.assertEqual(self.get(f"/tiles/{self.tiles.provider()}/1/0/1")[0], 200)
        self.assertEqual(self.get(f"/tiles/{'0' * 16}/1/0/1")[0], 404)  # (a page from before the provider changed)

    def test_not_for_another_sites_page(self):
        tile = f"/tiles/{self.tiles.provider()}/1/1/1"
        self.assertEqual(self.get(tile, **{"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"})[0], 403)
        self.assertEqual(self.get(tile, **{"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "no-cors"})[0], 200)
        self.assertEqual(self.get("/cameras.html", **{"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"})[0], 200)


class Requests(unittest.TestCase):
    def test_a_request_hidden_in_a_refused_ones_body_isnt_run(self):
        import http.server
        import socket
        import threading
        from app import server
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            port = httpd.server_address[1]
            before = prefs.get()["cycle"]
            inner = json.dumps({"cycle": 300 if before != 300 else 15}).encode()
            hidden = (f"POST /api/settings HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\n"
                      f"Content-Length: {len(inner)}\r\n\r\n").encode() + inner
            for outer in ((f"POST /api/settings HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: http://evil.example\r\n"
                           f"Content-Type: text/plain\r\nContent-Length: {len(hidden)}\r\n\r\n").encode() + hidden,
                          (f"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                           f"Content-Length: {len(hidden)}\r\n\r\n").encode() + hidden):
                with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
                    conn.sendall(outer)
                    answers = b""
                    while chunk := conn.recv(65536):
                        answers += chunk
                self.assertEqual(answers.count(b"HTTP/1.1 "), 1, outer[:40])  # (one answer, then closed)
                self.assertEqual(prefs.get()["cycle"], before)
        finally:
            httpd.shutdown()
            httpd.server_close()


class MyCameras(unittest.TestCase):
    def test_login_in_a_pasted_address_is_kept_apart(self):
        camera, password = mine._checked({"name": "Door", "kind": "rtsp", "url": "rtsp://admin:p%40ss@192.168.1.5:554/live"})
        self.assertEqual((camera["url"], camera["username"], password), ("rtsp://192.168.1.5:554/live", "admin", "p@ss"))

    def test_bad_cameras(self):
        for bad in ({"name": "x", "kind": "rtsp", "url": "http://a/b"}, {"name": "x", "kind": "snapshot", "url": "rtsp://a/b"},
                    {"name": "", "kind": "rtsp", "url": "rtsp://a/b"}, {"name": "x", "kind": "tv", "url": "rtsp://a/b"},
                    {"name": "x", "kind": "mjpeg", "url": "http://a/b", "record": 24},
                    {"name": "x", "kind": "rtsp", "url": "rtsp://a/b", "record": 5}):
            with self.assertRaises((ValueError, KeyError), msg=bad):
                mine._checked(bad)

    def test_passwords_stay_out_of_logs_and_files(self):
        self.assertEqual(mine._mask("rtsp://admin:secret@1.2.3.4/x failed"), "rtsp://***@1.2.3.4/x failed")
        self.assertEqual(mine._with_login("rtsp://1.2.3.4:554/x", "a b", "p:@w"), "rtsp://a%20b:p%3A%40w@1.2.3.4:554/x")

    def test_recording_files_are_only_its_own(self):
        self.assertIsNone(mine.recording_file("ab12cd34", "../my_cameras.json"))
        self.assertIsNone(mine.recording_file("../x", "2026-11-08 02-31-45.mp4"))

    @unittest.mock.patch.object(mine.shutil, "which", lambda name: f"/usr/bin/{name}")  # (ffmpeg needn't be here)
    def test_recording_keeps_the_sound_only_when_asked(self):
        def maps(body):
            camera, password = mine._checked({"name": "Door", "kind": "rtsp", "url": "rtsp://192.168.1.5/live", **body})
            command = mine._ffmpeg(camera, password, 10, record=Path("/tmp/rec") if camera["record"] else None)
            return [command[i + 1] for i, arg in enumerate(command) if arg == "-map"]
        self.assertEqual(maps({"record": 2}), ["0:v:0", "0:v:0"])
        self.assertEqual(maps({"record": 2, "sound": True}), ["0:v:0", "0:v:0", "0:a:0?"])
        self.assertEqual(maps({"record": 0, "sound": True}), ["0:v:0"])  # (no recording, no sound)

    def test_a_tunnel_is_a_proxys_host_and_port(self):
        camera, _ = mine._checked({"name": "Door", "kind": "rtsp", "url": "rtsp://192.168.1.5/live", "tunnel": "127.0.0.1:1055"})
        self.assertEqual(camera["tunnel"], "127.0.0.1:1055")
        for bad in ("127.0.0.1", "socks5://127.0.0.1:1055", "127.0.0.1:0", "a b:1055"):
            with self.assertRaises(ValueError, msg=bad):
                mine._checked({"name": "Door", "kind": "rtsp", "url": "rtsp://192.168.1.5/live", "tunnel": bad})

    def test_a_camera_that_doesnt_answer_is_reached_through_its_tunnel(self):
        import socket
        import threading
        from app import tunnel
        camera = socket.create_server(("127.0.0.1", 0))   # stands in for the camera: says hello, then echoes
        proxy = socket.create_server(("127.0.0.1", 0))    # a SOCKS5 proxy that leads to it
        asked = []

        def camera_side():
            conn, _ = camera.accept()
            conn.sendall(b"hello")
            conn.sendall(conn.recv(100))
            conn.close()

        def proxy_side():
            conn, _ = proxy.accept()
            conn.recv(3)
            conn.sendall(b"\x05\x00")
            head = conn.recv(4)
            host = socket.inet_ntoa(conn.recv(4)) if head[3] == 1 else conn.recv(conn.recv(1)[0]).decode()
            port = int.from_bytes(conn.recv(2), "big")
            asked.append((host, port))
            far = socket.create_connection(("127.0.0.1", camera.getsockname()[1]))
            conn.sendall(b"\x05\x00\x00\x01" + bytes(4) + bytes(2))
            threading.Thread(target=tunnel._pipe, args=(conn, far), daemon=True).start()
            tunnel._pipe(far, conn)

        for side in (camera_side, proxy_side):
            threading.Thread(target=side, daemon=True).start()
        config = {"url": "rtsp://10.255.255.1:554/live0", "tunnel": f"127.0.0.1:{proxy.getsockname()[1]}"}
        route, url = mine._routed(config, direct=False)
        self.assertEqual(route, "tunnel")
        port = int(url.split("127.0.0.1:")[1].split("/")[0])
        with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
            self.assertEqual(s.recv(5), b"hello")
            s.sendall(b"ping")
            self.assertEqual(s.recv(4), b"ping")
        self.assertEqual(asked, [("10.255.255.1", 554)])
        self.assertEqual(mine._routed({"url": "rtsp://10.255.255.1/x"}), ("direct", "rtsp://10.255.255.1/x"))


class Ranges(unittest.TestCase):
    def test_range_pattern(self):
        from app.server import RANGE
        self.assertEqual(RANGE.fullmatch("bytes=10-20").groups(), ("10", "20"))
        self.assertEqual(RANGE.fullmatch("bytes=-500").groups(), ("", "500"))
        self.assertIsNone(RANGE.fullmatch("bytes=1-2,5-6"))


if __name__ == "__main__":
    unittest.main()
