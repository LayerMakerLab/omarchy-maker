.pragma library
// Pure helpers for the Printers widget: config parsing, Moonraker responses, formatting.
// The file name carries the plugin version on purpose: the Omarchy shell reloads plugin QML when
// files change but keeps imported JavaScript cached by URL, so a new version needs a new name.
// No QML types here so the logic can be tested with node.

function parseConfig(text) {
  var parsed
  try { parsed = JSON.parse(text || "{}") } catch (e) { return { printers: [], error: "printers.json is not valid JSON" } }
  var list = Array.isArray(parsed) ? parsed : (parsed && Array.isArray(parsed.printers) ? parsed.printers : [])
  var printers = []
  var seen = {}
  for (var i = 0; i < list.length; i++) {
    var p = list[i] || {}
    var name = String(p.name || "").trim()
    if (!name || seen[name]) continue
    var type = String(p.type || "moonraker")
    if (type === "bambu") {
      // watched over the local network by maker-bambu; no web interface to link to
      var host = String(p.host || "").trim()
      if (!/^[A-Za-z0-9.:-]+$/.test(host) || !p.serial || !p.accessCode || !p.fingerprint) continue
      seen[name] = true
      printers.push({ name: name, type: "bambu", host: host, serial: String(p.serial), accessCode: String(p.accessCode), fingerprint: String(p.fingerprint), url: "", apiKey: "", webUrl: "" })
      continue
    }
    var url = normalizeUrl(p.url)
    if (!url) continue
    seen[name] = true
    printers.push({
      name: name,
      type: "moonraker",
      url: url,
      apiKey: String(p.apiKey || ""),
      webUrl: normalizeUrl(p.webUrl) || defaultWebUrl(url)
    })
  }
  return { printers: printers, error: "" }
}

// http(s) only, no credentials in the URL, no path/query; trailing slash dropped.
function normalizeUrl(value) {
  var s = String(value || "").trim()
  if (!s) return ""
  if (!/^https?:\/\//i.test(s)) s = "http://" + s
  var m = /^(https?):\/\/([^\/?#@\s]+)\/?$/i.exec(s)
  return m ? m[1].toLowerCase() + "://" + m[2] : ""
}

// Mainsail/Fluidd normally sit on the same host without Moonraker's port.
function defaultWebUrl(url) {
  var m = /^(https?:\/\/[^\/:]+)(:\d+)?$/.exec(url)
  return m ? m[1] : url
}

var QUERY = "/printer/objects/query?print_stats&virtual_sdcard&display_status&extruder&heater_bed&webhooks"

function queryUrl(printer) { return printer.url + QUERY }
function metadataUrl(printer, filename) { return printer.url + "/server/files/metadata?filename=" + encodeURIComponent(filename) }

function thumbnailUrl(printer, filename, metadata) {
  var thumbs = metadata && Array.isArray(metadata.thumbnails) ? metadata.thumbnails : []
  if (!thumbs.length) return ""
  var best = thumbs[0]
  for (var i = 1; i < thumbs.length; i++) {
    var t = thumbs[i]
    // the biggest one that is still a sensible size for the panel
    if ((t.width || 0) > (best.width || 0) && (t.width || 0) <= 400) best = t
  }
  if (!best.relative_path) return ""
  var dir = String(filename || "").indexOf("/") >= 0 ? filename.substring(0, filename.lastIndexOf("/") + 1) : ""
  return printer.url + "/server/files/gcodes/" + encodeURI(dir + best.relative_path)
}

// Moonraker answers {"result": {...}} on success and {"error": {...}} otherwise.
function parseStatus(httpStatus, text) {
  var body = null
  try { body = JSON.parse(text || "") } catch (e) { body = null }
  if (httpStatus === 0) return { state: "offline", message: "No answer" }
  if (!body) return { state: "offline", message: "HTTP " + httpStatus }
  if (body.error) {
    var msg = String(body.error.message || ("HTTP " + httpStatus))
    if (httpStatus === 401 || httpStatus === 403) return { state: "offline", message: "Needs an API key (maker printer add ... --api-key)" }
    return { state: "klippy", message: msg }
  }
  var status = body.result && body.result.status ? body.result.status : null
  if (!status) return { state: "offline", message: "Unexpected answer" }
  var ps = status.print_stats || {}
  var sd = status.virtual_sdcard || {}
  var ds = status.display_status || {}
  var ex = status.extruder || {}
  var bed = status.heater_bed || {}
  var hooks = status.webhooks || {}
  if (hooks.state && hooks.state !== "ready") return { state: "klippy", message: String(hooks.state_message || hooks.state) }
  var progress = typeof ds.progress === "number" && ds.progress > 0 ? ds.progress : (typeof sd.progress === "number" ? sd.progress : 0)
  var info = ps.info || {}
  return {
    state: String(ps.state || "standby"),
    message: String(ps.message || ""),
    filename: String(ps.filename || ""),
    progress: Math.max(0, Math.min(1, progress)),
    printDuration: Number(ps.print_duration || 0),
    totalDuration: Number(ps.total_duration || 0),
    currentLayer: info.current_layer === null || info.current_layer === undefined ? null : Number(info.current_layer),
    totalLayer: info.total_layer === null || info.total_layer === undefined ? null : Number(info.total_layer),
    extruder: num(ex.temperature), extruderTarget: num(ex.target),
    bed: num(bed.temperature), bedTarget: num(bed.target)
  }
}

function num(v) { return typeof v === "number" && isFinite(v) ? v : null }

function parseMetadata(httpStatus, text) {
  if (httpStatus !== 200) return null
  try { var body = JSON.parse(text); return body && body.result ? body.result : null } catch (e) { return null }
}

// One status line from maker-bambu (already in this file's status shape).
function parseBambuLine(text) {
  var st
  try { st = JSON.parse(text) } catch (e) { return null }
  if (!st || typeof st.state !== "string") return null
  return {
    state: st.state,
    message: String(st.message || ""),
    filename: String(st.filename || ""),
    progress: typeof st.progress === "number" ? Math.max(0, Math.min(1, st.progress)) : 0,
    printDuration: 0,
    totalDuration: 0,
    remainingSeconds: typeof st.remainingSeconds === "number" ? st.remainingSeconds : null,
    currentLayer: typeof st.currentLayer === "number" ? st.currentLayer : null,
    totalLayer: typeof st.totalLayer === "number" ? st.totalLayer : null,
    extruder: num(st.extruder), extruderTarget: num(st.extruderTarget),
    bed: num(st.bed), bedTarget: num(st.bedTarget),
    chamber: num(st.chamber)
  }
}

// Seconds left: what the printer says when it says, else the slicer's estimate, else extrapolated.
function timeLeft(status, metadata) {
  if (!status || (status.state !== "printing" && status.state !== "paused")) return null
  if (typeof status.remainingSeconds === "number") return Math.max(0, status.remainingSeconds)
  var est = metadata && typeof metadata.estimated_time === "number" ? metadata.estimated_time : 0
  if (est > 0) return Math.max(0, Math.round(est - status.printDuration))
  if (status.progress > 0.02 && status.printDuration > 0) return Math.max(0, Math.round(status.printDuration / status.progress - status.printDuration))
  return null
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || !isFinite(seconds)) return ""
  var s = Math.max(0, Math.round(seconds))
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  if (h > 0) return h + "h " + (m < 10 ? "0" : "") + m + "m"
  if (m > 0) return m + "m"
  return s + "s"
}

function formatTemp(current, target) {
  if (current === null) return ""
  return Math.round(current) + (target && target > 0 ? "/" + Math.round(target) : "") + "°"
}

function stateLabel(status) {
  if (!status) return "…"
  switch (status.state) {
    case "printing": return "Printing"
    case "paused": return "Paused"
    case "complete": return "Finished"
    case "cancelled": return "Cancelled"
    case "error": return "Failed"
    case "standby": return "Idle"
    case "klippy": return "Klipper: " + status.message
    case "offline": return "Offline"
  }
  return status.state
}

// What a state change should announce: "finished", "failed", "cancelled", or "".
function transition(previous, next) {
  if (!previous || !next) return ""
  var wasRunning = previous === "printing" || previous === "paused"
  if (!wasRunning) return ""
  if (next === "complete") return "finished"
  if (next === "error") return "failed"
  if (next === "cancelled") return "cancelled"
  return ""
}

function baseName(path) { var s = String(path || ""); return s.substring(s.lastIndexOf("/") + 1) }

// The bar label: the busiest printer's progress, plus how many others are running.
// Attention means something needs you now: a paused print, Klipper in trouble, or a failure that
// happened while the widget was watching and has not been looked at yet (alerts, by printer name).
// A printer that was already in "error" when the widget started does not light the bar.
function barSummary(entries, alerts) {
  var running = []
  var attention = false
  for (var i = 0; i < entries.length; i++) {
    var st = entries[i].status
    if (!st) continue
    if (st.state === "printing" || st.state === "paused") running.push(entries[i])
    if (st.state === "paused" || st.state === "klippy") attention = true
    if (alerts && alerts[entries[i].printer ? entries[i].printer.name : ""]) attention = true
  }
  if (!running.length) return { text: "", running: 0, attention: attention }
  running.sort(function(a, b) { return b.status.progress - a.status.progress })
  var lead = running[0].status
  var text = Math.floor(lead.progress * 100) + "%"
  if (running.length > 1) text += " +" + (running.length - 1)
  return { text: text, running: running.length, attention: attention }
}
