import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "Printers-0.3.0.js" as Model

Panel {
  id: root
  moduleName: "layermaker.printers"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var entries: hostWidget ? hostWidget.entries : []
  readonly property string fontFamily: root.bar ? root.bar.fontFamily : Style.font.family

  function open() { root.controller.show() }
  function close() { root.controller.hide() }
  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function") return root.bar.switchPanelFrom(root.hostWidget || root, direction)
    return false
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(8)

        Row {
          width: parent.width
          Text {
            width: parent.width - refresh.width
            text: "󰐫  Printers"
            color: root.barForeground
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            font.bold: true
          }
          Text {
            id: refresh
            text: "󰑐"
            color: root.barForeground
            opacity: 0.7
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: if (root.hostWidget) root.hostWidget.pollAll()
            }
          }
        }

        Text {
          visible: !!(root.hostWidget && root.hostWidget.configError)
          width: parent.width
          wrapMode: Text.WordWrap
          text: root.hostWidget ? root.hostWidget.configError : ""
          color: Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Text {
          visible: root.entries.length === 0
          width: parent.width
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
          text: "No printers yet. Add a Klipper printer in a terminal:\n\nmaker printer add Voron http://voron.local:7125"
          color: root.barForeground
          opacity: 0.8
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
        }

        Repeater {
          model: root.entries

          delegate: Column {
            id: card
            required property var modelData
            required property int index
            readonly property var st: modelData.status
            readonly property bool running: !!st && (st.state === "printing" || st.state === "paused")
            readonly property bool trouble: !!st && (st.state === "error" || st.state === "klippy" || st.state === "offline" || st.state === "paused")
            width: content.width
            spacing: Style.space(4)

            PanelSeparator { visible: card.index > 0; foreground: root.barForeground }

            Row {
              width: parent.width
              spacing: Style.space(10)

              Image {
                id: thumb
                visible: card.modelData.thumbnail !== "" && status === Image.Ready
                width: visible ? Style.space(56) : 0
                height: Style.space(56)
                fillMode: Image.PreserveAspectFit
                source: card.modelData.thumbnail
                asynchronous: true
                cache: true
              }

              Column {
                width: parent.width - thumb.width - (thumb.visible ? Style.space(10) : 0)
                spacing: Style.space(3)

                Row {
                  width: parent.width
                  Text {
                    width: parent.width - stateText.implicitWidth
                    text: card.modelData.printer.name
                    color: root.barForeground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.subtitle
                    font.bold: true
                    elide: Text.ElideRight
                  }
                  Text {
                    id: stateText
                    text: Model.stateLabel(card.st)
                    color: card.trouble ? Color.urgent : root.barForeground
                    opacity: card.trouble || card.running ? 1 : 0.7
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                  }
                }

                Text {
                  visible: !!card.st && !!card.st.filename && card.st.state !== "standby"
                  width: parent.width
                  text: card.st ? Model.baseName(card.st.filename) : ""
                  elide: Text.ElideMiddle
                  color: root.barForeground
                  opacity: 0.8
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }

                Rectangle {
                  visible: card.running
                  width: parent.width
                  height: Style.space(4)
                  radius: height / 2
                  color: Qt.rgba(root.barForeground.r, root.barForeground.g, root.barForeground.b, 0.15)
                  Rectangle {
                    width: parent.width * (card.st ? card.st.progress : 0)
                    height: parent.height
                    radius: parent.radius
                    color: card.st && card.st.state === "paused" ? Color.urgent : Color.accent
                  }
                }

                Text {
                  visible: card.running
                  width: parent.width
                  text: {
                    if (!card.st) return ""
                    var parts = [Math.floor(card.st.progress * 100) + "%"]
                    if (card.modelData.timeLeft !== null) parts.push(Model.formatDuration(card.modelData.timeLeft) + " left")
                    if (card.st.totalLayer) parts.push("layer " + (card.st.currentLayer || 0) + "/" + card.st.totalLayer)
                    return parts.join(" · ")
                  }
                  color: root.barForeground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }

                Text {
                  visible: !!card.st && card.st.extruder !== null && card.st.extruder !== undefined
                  width: parent.width
                  text: card.st ? "hotend " + Model.formatTemp(card.st.extruder, card.st.extruderTarget) + "   bed " + Model.formatTemp(card.st.bed, card.st.bedTarget) + (card.modelData.printer.type === "bambu" ? "   " + card.modelData.printer.host : "") : ""
                  color: root.barForeground
                  opacity: 0.7
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }

                Text {
                  visible: !!card.st && (card.st.state === "klippy" || card.st.state === "offline" || card.st.state === "error") && !!card.st.message
                  width: parent.width
                  wrapMode: Text.WordWrap
                  text: card.st ? card.st.message : ""
                  color: Color.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }

                Text {
                  visible: card.modelData.printer.webUrl !== ""
                  text: "Open " + card.modelData.printer.webUrl.replace(/^https?:\/\//, "") + "  󰏌"
                  color: root.barForeground
                  opacity: webHover.containsMouse ? 1 : 0.6
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  MouseArea {
                    id: webHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.openUrlExternally(card.modelData.printer.webUrl)
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
