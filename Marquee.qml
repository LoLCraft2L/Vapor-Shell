import QtQuick

// Text that scrolls right-to-left, in a loop, when it is wider than maxWidth.
// Shorter text just sits still. Put the file next to FluidBar.qml.
Item {
    id: root

    property string text: ""
    property color color: "white"
    property string fontFamily: "CaskaydiaCove NFP"
    property real pixelSize: 12
    property int weight: Font.Normal
    property real maxWidth: 200        // widest the visible window gets
    property bool active: true         // only animate while this is true (e.g. while the popup is open)
    property real gap: 36              // empty space between the end of the text and its repeat
    property real msPerPx: 30          // scroll speed (higher = slower)
    property int pauseMs: 1800         // rest at the start of every pass

    readonly property real textW: label.implicitWidth
    readonly property bool overflow: textW > maxWidth + 0.5
    readonly property real travel: textW + gap

    property bool _hold: false         // flipped for a moment when the text changes so the scroll restarts from the beginning

    width: Math.min(textW, maxWidth)
    height: label.implicitHeight
    clip: true

    onTextChanged: {
        _hold = true
        strip.x = 0
        Qt.callLater(function () { root._hold = false })
    }

    Item {
        id: strip
        height: parent.height
        width: root.travel + root.textW

        Text {
            id: label
            text: root.text
            color: root.color
            font.family: root.fontFamily
            font.pixelSize: root.pixelSize
            font.weight: root.weight
            textFormat: Text.PlainText
        }
        Text {
            visible: root.overflow
            x: root.travel
            text: root.text
            color: root.color
            font.family: root.fontFamily
            font.pixelSize: root.pixelSize
            font.weight: root.weight
            textFormat: Text.PlainText
        }
    }

    SequentialAnimation {
        running: root.active && root.overflow && !root._hold
        loops: Animation.Infinite
        onRunningChanged: if (!running) strip.x = 0
        PauseAnimation { duration: root.pauseMs }
        NumberAnimation {
            target: strip
            property: "x"
            from: 0
            to: -root.travel
            duration: Math.max(1500, root.travel * root.msPerPx)
            easing.type: Easing.Linear
        }
    }
}
