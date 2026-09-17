import QtQuick
import QtQml
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Printers-0.3.0.js" as Model

// Printers: the running print in the bar, every printer in the panel.
// Printers come from ~/.config/omarchy-maker/printers.json (written by `maker printer add`),
// not from shell.json, because API keys do not belong in a file people share as dotfiles.
BarWidget {
  id: root
  moduleName: "layermaker.printers"

  readonly property string glyph: "󰐫"
  readonly property string configDir: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")) + "/omarchy-maker"
  readonly property bool notifyOnFinish: root.setting("notifyOnFinish", true) === true
  readonly property bool notifyOnError: root.setting("notifyOnError", true) === true
  readonly property int finishHoldMin: Number(root.setting("finishHoldMin", 10))

  property var printers: []
  property string configError: ""
  property var statuses: ({})
  property var metadata: ({})
  property var finishedAt: ({})
  property var alerts: ({})
  property var inFlight: ({})
  property double now: Date.now()

  readonly property var entries: {
    var list = []
    for (var i = 0; i < printers.length; i++) {
      var p = printers[i]
      var st = statuses[p.name] || null
      var md = metadata[p.name] && st && metadata[p.name].filename === st.filename ? metadata[p.name].data : null
      list.push({ printer: p, status: st, metadata: md, timeLeft: Model.timeLeft(st, md), thumbnail: md ? Model.thumbnailUrl(p, st.filename, md) : "" })
    }
    return list
  }
  readonly property var summary: Model.barSummary(entries, alerts)
  readonly property bool holdingFinish: {
    var hold = finishHoldMin * 60000
    if (hold <= 0) return false
    for (var k in finishedAt) if (now - finishedAt[k] < hold) return true
    return false
  }
  readonly property var lead: {
    for (var i = 0; i < entries.length; i++) {
      var st = entries[i].status
      if (st && (st.state === "printing" || st.state === "paused")) return entries[i]
    }
    return entries.length ? entries[0] : null
  }

  function applyConfig(text) {
    var parsed = Model.parseConfig(text)
    root.configError = text === "" ? "" : parsed.error
    root.printers = parsed.printers
    root.pollAll()
  }

  readonly property var klipperPrinters: printers.filter(function(p) { return p.type !== "bambu" })
  readonly property var bambuPrinters: printers.filter(function(p) { return p.type === "bambu" })
  readonly property string watcher: Quickshell.env("HOME") + "/.local/bin/maker-bambu"

  // Bambu printers push their state; only Klipper printers are polled.
  function pollAll() {
    root.now = Date.now()
    for (var i = 0; i < klipperPrinters.length; i++) fetchStatus(klipperPrinters[i])
  }

  function fetchStatus(printer) {
    var name = printer.name
    var busy = inFlight[name]
    if (busy) {
      if (Date.now() - busy.started < 8000) return
      busy.xhr.abort()
      delete inFlight[name]
      applyStatus(printer, { state: "offline", message: "No answer" })
      return
    }
    var xhr = new XMLHttpRequest()
    inFlight[name] = { xhr: xhr, started: Date.now() }
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      if (!inFlight[name] || inFlight[name].xhr !== xhr) return
      delete inFlight[name]
      root.applyStatus(printer, Model.parseStatus(xhr.status, xhr.responseText))
    }
    xhr.open("GET", Model.queryUrl(printer))
    if (printer.apiKey) xhr.setRequestHeader("X-Api-Key", printer.apiKey)
    xhr.send()
  }

  function fetchMetadata(printer, filename) {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      var next = Object.assign({}, root.metadata)
      next[printer.name] = { filename: filename, data: Model.parseMetadata(xhr.status, xhr.responseText) }
      root.metadata = next
    }
    xhr.open("GET", Model.metadataUrl(printer, filename))
    if (printer.apiKey) xhr.setRequestHeader("X-Api-Key", printer.apiKey)
    xhr.send()
  }

  function applyStatus(printer, status) {
    var name = printer.name
    var previous = statuses[name] || null
    var next = Object.assign({}, statuses)
    next[name] = status
    statuses = next

    if (printer.type !== "bambu" && status.filename && (!metadata[name] || metadata[name].filename !== status.filename)) {
      var placeholder = Object.assign({}, metadata)
      placeholder[name] = { filename: status.filename, data: null }
      metadata = placeholder
      fetchMetadata(printer, status.filename)
    }

    var change = Model.transition(previous ? previous.state : "", status.state)
    var file = Model.baseName(status.filename)
    if (change === "finished") {
      var held = Object.assign({}, finishedAt)
      held[name] = Date.now()
      finishedAt = held
      if (notifyOnFinish) notify("normal", name + " finished", file + (status.printDuration ? " · " + Model.formatDuration(status.printDuration) : ""))
    } else if (change === "failed") {
      var raised = Object.assign({}, alerts)
      raised[name] = Date.now()
      alerts = raised
      if (notifyOnError) notify("critical", name + ": print failed", file + (status.message ? " · " + status.message : ""))
    } else if (change === "cancelled" && notifyOnError) {
      notify("normal", name + ": print cancelled", file)
    }
    // a new print clears that printer's old failure
    if (status.state === "printing" && alerts[name]) {
      var cleared = Object.assign({}, alerts)
      delete cleared[name]
      alerts = cleared
    }
  }

  function notify(urgency, headline, description) {
    Quickshell.execDetached(["omarchy-notification-send", "-u", urgency, "-g", root.glyph, headline, description])
  }

  function openWebUi(entry) {
    if (entry && entry.printer.webUrl) Qt.openUrlExternally(entry.printer.webUrl)
  }

  // Panel plumbing, same shape as the built-in popup widgets.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  // opening the panel counts as having seen finished and failed prints
  function open() { if (panelLoader.item) { root.finishedAt = ({}); root.alerts = ({}); panelLoader.item.open(); root.pollAll() } }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { root.opened ? root.close() : root.open() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    target.bar = root.bar
    target.settings = Qt.binding(function() { return root.settings })
    target.anchorItem = button
    target.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  FileView {
    id: configFile
    path: root.configDir + "/printers.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.applyConfig(text())
    onLoadFailed: root.applyConfig("")
  }

  // One long-running maker-bambu per Bambu printer. The access code travels in the environment,
  // never on the command line, and each line on stdout is one status.
  Instantiator {
    model: root.bambuPrinters
    delegate: Process {
      id: watch
      required property var modelData
      command: [root.watcher, "watch"]
      environment: ({
        BAMBU_HOST: modelData.host,
        BAMBU_SERIAL: modelData.serial,
        BAMBU_ACCESS_CODE: modelData.accessCode,
        BAMBU_FINGERPRINT: modelData.fingerprint
      })
      running: true
      stdout: SplitParser {
        onRead: function(line) {
          var st = Model.parseBambuLine(line)
          if (st) root.applyStatus(watch.modelData, st)
        }
      }
      onExited: function(code) {
        root.applyStatus(watch.modelData, { state: "offline", message: "Watcher stopped (" + code + "); retrying" })
        restart.start()
      }
      property Timer restart: Timer { interval: 15000; onTriggered: watch.running = true }
    }
  }

  Timer {
    // quick while something prints or the panel is open, relaxed otherwise
    interval: (root.summary.running > 0 || root.opened) ? 3000 : 20000
    running: root.klipperPrinters.length > 0
    repeat: true
    onTriggered: root.pollAll()
  }

  Timer {
    // keeps the finished-print highlight honest without polling faster
    interval: 30000
    running: root.holdingFinish
    repeat: true
    onTriggered: root.now = Date.now()
  }

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.glyph + (root.summary.text !== "" ? " " + root.summary.text : (root.holdingFinish ? " 󰄬" : ""))
    active: root.summary.attention
    dimmed: root.summary.running === 0 && !root.holdingFinish && !root.summary.attention
    tooltipText: {
      if (root.configError) return root.configError
      if (root.printers.length === 0) return "No printers yet: maker printer add NAME URL"
      var e = root.lead
      if (!e || !e.status) return "Printers"
      var parts = [e.printer.name, Model.stateLabel(e.status)]
      if (e.status.state === "printing" || e.status.state === "paused") {
        parts.push(Math.floor(e.status.progress * 100) + "%")
        if (e.timeLeft !== null) parts.push(Model.formatDuration(e.timeLeft) + " left")
      }
      return parts.join(" · ")
    }
    onPressed: function(which) {
      if (which === Qt.MiddleButton) root.pollAll()
      else if (which === Qt.RightButton) root.openWebUi(root.lead)
      else root.toggle()
    }
  }
}
