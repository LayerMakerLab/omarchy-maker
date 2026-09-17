// node tests/model.test.js — checks the Printers widget logic without a shell.
const fs = require("fs")
const path = require("path")
const dir = path.join(__dirname, "../plugins/printers")
const jsName = /import "([^"]+\.js)" as Model/.exec(fs.readFileSync(path.join(dir, "BarWidget.qml"), "utf8"))[1]
const src = fs.readFileSync(path.join(dir, jsName), "utf8").replace(/^\.pragma library\s*$/m, "")
const names = [...src.matchAll(/^function (\w+)\(/gm)].map(m => m[1])
const M = new Function(src + "\nreturn {" + names.join(",") + "}")()

let pass = 0, fail = 0
function eq(what, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  ok ? pass++ : fail++
  console.log((ok ? "  ok   " : "  FAIL ") + what + (ok ? "" : `\n       got  ${JSON.stringify(got)}\n       want ${JSON.stringify(want)}`))
}

eq("normalizeUrl adds http and drops the slash", M.normalizeUrl("voron.local:7125/"), "http://voron.local:7125")
eq("normalizeUrl refuses credentials", M.normalizeUrl("http://user:pw@voron:7125"), "")
eq("normalizeUrl refuses a path", M.normalizeUrl("http://voron:7125/printer"), "")
eq("default web UI drops Moonraker's port", M.defaultWebUrl("http://voron.local:7125"), "http://voron.local")

const cfg = M.parseConfig(JSON.stringify({ printers: [
  { name: "Voron", url: "voron.local:7125" },
  { name: "Voron", url: "dupe:7125" },
  { name: "", url: "x:1" },
  { name: "K1", url: "http://192.168.1.60:7125", apiKey: "abc", webUrl: "http://192.168.1.60:4408" }
] }))
eq("parseConfig keeps valid, unique printers", cfg.printers.map(p => p.name), ["Voron", "K1"])
eq("parseConfig keeps the web UI override", cfg.printers[1].webUrl, "http://192.168.1.60:4408")
eq("parseConfig reports broken JSON", M.parseConfig("{").error, "printers.json is not valid JSON")

const printing = JSON.stringify({ result: { eventtime: 1, status: {
  webhooks: { state: "ready", state_message: "Printer is ready" },
  print_stats: { filename: "parts/cube.gcode", state: "printing", print_duration: 600, total_duration: 650, info: { current_layer: 45, total_layer: 100 } },
  virtual_sdcard: { progress: 0.40 }, display_status: { progress: 0.42 },
  extruder: { temperature: 214.6, target: 215 }, heater_bed: { temperature: 59.8, target: 60 }
} } })
const st = M.parseStatus(200, printing)
eq("parseStatus reads state, file and progress", [st.state, st.filename, st.progress], ["printing", "parts/cube.gcode", 0.42])
eq("parseStatus reads layers and temps", [st.currentLayer, st.totalLayer, M.formatTemp(st.extruder, st.extruderTarget), M.formatTemp(st.bed, st.bedTarget)], [45, 100, "215/215°", "60/60°"])
eq("time left from the slicer estimate", M.timeLeft(st, { estimated_time: 4200 }), 3600)
eq("time left from progress without an estimate", M.timeLeft(st, null), 829)
eq("no time left when idle", M.timeLeft({ state: "standby" }, { estimated_time: 10 }), null)
eq("klippy not ready", M.parseStatus(200, JSON.stringify({ result: { status: { webhooks: { state: "shutdown", state_message: "MCU shutdown" } } } })), { state: "klippy", message: "MCU shutdown" })
eq("moonraker error body", M.parseStatus(503, JSON.stringify({ error: { code: 503, message: "Klippy Host not connected" } })).state, "klippy")
eq("unauthorized asks for a key", M.parseStatus(401, JSON.stringify({ error: { code: 401, message: "Unauthorized" } })).message, "Needs an API key (maker printer add ... --api-key)")
eq("no answer is offline", M.parseStatus(0, "").state, "offline")
eq("thumbnail next to a file in a folder", M.thumbnailUrl({ url: "http://v:7125" }, "parts/cube.gcode", { thumbnails: [{ width: 32, relative_path: ".thumbs/cube-32x32.png" }, { width: 300, relative_path: ".thumbs/cube-300x300.png" }] }), "http://v:7125/server/files/gcodes/parts/.thumbs/cube-300x300.png")
eq("finished after printing", M.transition("printing", "complete"), "finished")
eq("failed after paused", M.transition("paused", "error"), "failed")
eq("nothing after idle", M.transition("standby", "complete"), "")
const bam = M.parseConfig(JSON.stringify({ printers: [
  { name: "Jr.", type: "bambu", host: "192.168.1.50", serial: "TEST-SERIAL", accessCode: "abcd1234", fingerprint: "ab" },
  { name: "Bad", type: "bambu", host: "192.168.1.9; rm -rf /", serial: "x", accessCode: "1", fingerprint: "f" },
  { name: "NoCode", type: "bambu", host: "192.168.1.8", serial: "x", fingerprint: "f" }
] }))
eq("Bambu printers need host, serial, code and fingerprint", bam.printers.map(p => p.name), ["Jr."])
eq("Bambu printers have no web link", bam.printers[0].webUrl, "")
const bl = M.parseBambuLine(JSON.stringify({ state: "printing", filename: "skeleton-forgeplate_plate_2", progress: 0.42, remainingSeconds: 1500, currentLayer: 289, totalLayer: 689, extruder: 220, extruderTarget: 220, bed: 65, bedTarget: 65, chamber: 5 }))
eq("maker-bambu line parsed", [bl.state, bl.filename, bl.currentLayer, bl.totalLayer], ["printing", "skeleton-forgeplate_plate_2", 289, 689])
eq("printer's own time left wins", M.timeLeft(bl, { estimated_time: 99999 }), 1500)
eq("junk line ignored", M.parseBambuLine("not json"), null)
eq("formatDuration", [M.formatDuration(3725), M.formatDuration(125), M.formatDuration(9)], ["1h 02m", "2m", "9s"])
eq("bar shows the most advanced print and the count", M.barSummary([
  { status: { state: "printing", progress: 0.2 } }, { status: { state: "printing", progress: 0.73 } }, { status: { state: "standby", progress: 0 } }
]), { text: "73% +1", running: 2, attention: false })
eq("an old failure does not light the bar", M.barSummary([{ printer: { name: "V" }, status: { state: "error", progress: 0 } }], {}), { text: "", running: 0, attention: false })
eq("a failure seen by the widget does", M.barSummary([{ printer: { name: "V" }, status: { state: "error", progress: 0 } }], { V: 1 }), { text: "", running: 0, attention: true })
eq("a paused print needs attention", M.barSummary([{ printer: { name: "V" }, status: { state: "paused", progress: 0.5 } }], {}).attention, true)

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
