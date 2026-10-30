import QtQuick
import QtQuick.Window

// Control center for Vapor. It's one more popup page of the bar: it grows out of the glass, uses the bar's colours
// and everything inside moves on springs.
// - opening: every block rises + pops in one after another (staggered, slight overshoot)
// - sub-pages (Wi-Fi, Bluetooth, mixer, stats) slide in and the glass morphs to their height
// - tiles flood with the accent from their icon, sliders stretch their thumb, the theme card unfolds
//
// everything is wired to the Python side. `B` is the bar's own backend (volume, battery, Wi-Fi name, output
// devices, theme colours), `CC` is cc_backend.py (radios, Wi-Fi / Bluetooth lists, DND, dark mode, brightness,
// mic, app mixer, stats, theme, clear cache, power).
Item {
    id: cc

    // ---- building blocks (inline components, so the whole control center stays in this one file) ----
    // pill button used all over the control center. `primary` fills it with the accent (black text, like the play
    // button), `danger` tints the text red, `selected` is the on-state for chips (Light / Saturation / Black).
    // settings gear drawn by hand, so it never depends on the icon font
    component CcGearGlyph: Canvas {
        id: gg
        property color ink: "white"
        width: 16          // same visual size as the other 15 px icon-font glyphs (it was 20 and looked bulky)
        height: 16
        onInkChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            c.scale(width / 20, height / 20)
            c.fillStyle = ink
            c.beginPath()
            var n = 8, first = true
            for (var i = 0; i < n; i++) {
                var a0 = i * 2 * Math.PI / n
                var pts = [[a0 - 0.30, 6.0], [a0 - 0.18, 8.6], [a0 + 0.18, 8.6], [a0 + 0.30, 6.0]]
                for (var k = 0; k < 4; k++) {
                    var x = 10 + Math.cos(pts[k][0]) * pts[k][1], y = 10 + Math.sin(pts[k][0]) * pts[k][1]
                    if (first) { c.moveTo(x, y); first = false } else c.lineTo(x, y)
                }
            }
            c.closePath()
            c.fill()
            c.globalCompositeOperation = "destination-out"
            c.beginPath()
            c.arc(10, 10, 4.2, 0, 2 * Math.PI, false)
            c.fill()
        }
    }

    component CcButton: Item {
        id: btn

        property string text: ""
        property string icon: ""
        property string kind: ""            // "gear" = draw the settings gear instead of an icon-font glyph
        property bool primary: false
        property bool danger: false
        property bool selected: false
        property bool flat: false           // no resting fill, only the hover wash
        property bool round: false          // 32px circle (icon-only buttons)
        property color accent: "#4cbcff"
        property color hoverColor: Qt.rgba(1, 1, 1, 0.1)
        property string uiFont: "CaskaydiaCove NFP"
        property real pixelSize: 12

        signal clicked()

        readonly property color onAccent: ((0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55) ? "#000000" : "#ffffff"
        readonly property color ink: primary ? onAccent : (danger ? "#ff6b7a" : "white")

        implicitHeight: round ? 32 : 34
        implicitWidth: round ? 32 : row.implicitWidth + 28

        Item {
            anchors.fill: parent
            scale: mouse.pressed ? 0.94 : 1
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.005 } }

            Rectangle {
                anchors.fill: parent
                radius: height / 2
                antialiasing: true
                color: btn.primary ? btn.accent
                     : btn.selected ? Qt.rgba(btn.accent.r, btn.accent.g, btn.accent.b, 0.3)
                     : (btn.flat ? "transparent" : Qt.rgba(1, 1, 1, 0.07))
                border.width: btn.selected && !btn.primary ? 1 : 0
                border.color: Qt.rgba(btn.accent.r, btn.accent.g, btn.accent.b, 0.7)
                Behavior on color { ColorAnimation { duration: 108 } }
            }
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                antialiasing: true
                color: btn.primary ? Qt.rgba(1, 1, 1, 0.16) : btn.hoverColor
                opacity: mouse.containsMouse ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 90 } }
            }
            Row {
                id: row
                anchors.centerIn: parent
                spacing: 7
                CcGearGlyph {
                    visible: btn.kind === "gear"
                    anchors.verticalCenter: parent.verticalCenter
                    ink: btn.ink
                }
                Text {
                    renderType: Text.QtRendering
                    visible: btn.icon !== ""
                    anchors.verticalCenter: parent.verticalCenter
                    text: btn.icon
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: btn.pixelSize + 3
                    color: btn.ink
                }
                Text {
                    renderType: Text.QtRendering
                    visible: btn.text !== ""
                    anchors.verticalCenter: parent.verticalCenter
                    text: btn.text
                    font.family: btn.uiFont
                    font.pixelSize: btn.pixelSize
                    font.weight: Font.DemiBold
                    color: btn.ink
                }
            }
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    // header of an in-panel page: round back button, title, and whatever you put inside goes on the right.
    // CcHeader { title: "Wi-Fi"; onBack: ...; CcSwitch { } }
    component CcHeader: Item {
        id: head

        property string title: ""
        property string uiFont: "CaskaydiaCove NFP"
        default property alias rightContent: rightRow.data

        signal back()

        implicitHeight: 32

        Rectangle {
            width: 32
            height: 32
            radius: 16
            antialiasing: true
            color: Qt.rgba(1, 1, 1, backMouse.containsMouse ? 0.14 : 0.07)
            scale: backMouse.pressed ? 0.9 : 1
            Behavior on color { ColorAnimation { duration: 90 } }
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.005 } }
            Text {
                renderType: Text.QtRendering
                anchors.centerIn: parent
                text: "\uE72B"
                font.family: "Segoe Fluent Icons"
                font.pixelSize: 14
                color: "white"
            }
            MouseArea {
                id: backMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: head.back()
            }
        }
        Text {
            renderType: Text.QtRendering
            x: 42
            anchors.verticalCenter: parent.verticalCenter
            text: head.title
            color: "white"
            font.family: head.uiFont
            font.pixelSize: 15
            font.weight: Font.Bold
        }
        Row {
            id: rightRow
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
        }
    }

    // on / off switch (Wi-Fi and Bluetooth pages), filled with the accent when on like the active tiles
    component CcSwitch: Item {
        id: sw

        property bool checked: false
        property color accent: "#4cbcff"
        readonly property color ink: ((0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55) ? "#0b0b12" : "#ffffff"

        signal toggled()

        implicitWidth: 44
        implicitHeight: 26

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            antialiasing: true
            color: sw.checked ? sw.accent : Qt.rgba(1, 1, 1, 0.16)
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        Rectangle {
            id: knob
            y: 3
            width: mouse.pressed ? 24 : 20
            height: 20
            radius: 10
            antialiasing: true
            color: sw.checked ? sw.ink : "white"
            x: sw.checked ? sw.width - width - 3 : 3
            Behavior on x { SpringAnimation { spring: 8; damping: 0.55; epsilon: 0.25 } }
            Behavior on width { NumberAnimation { duration: 80 } }
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: sw.toggled()
        }
    }

    // one slider row: [icon button] [track] [value] [optional >].
    // the fill glides to new values, the thumb stretches into a pill while you drag, the % bumps.
    // the row never writes to the backend itself, it emits moved(v) with v in 0..1 and the parent decides.
    component CcSlider: Item {
        id: row

        property string icon: ""
        property string iconSource: ""       // a picture (an app's icon, say) shown instead of the glyph / letter
        property string iconFont: "Segoe Fluent Icons"
        property real displayScale: 1
        property real value: 0
        property bool muted: false
        property bool showValue: true
        property bool hasMore: false
        property bool iconClickable: false
        property bool unavailable: false     // no such device (brightness on an external monitor, say): greyed out, "n/a"
        property color accent: "#4cbcff"
        property color lavender: "#d2bcff"
        property string uiFont: "CaskaydiaCove NFP"

        signal moved(real v)
        signal iconClicked()
        signal more()

        property bool dragging: false
        property real dragValue: 0
        readonly property real shown: dragging ? dragValue : (muted ? 0 : value)

        implicitHeight: 36
        opacity: unavailable ? 0.4 : 1
        enabled: !unavailable
        Behavior on opacity { NumberAnimation { duration: 96 } }

        // icon
        Rectangle {
            x: 0
            anchors.verticalCenter: parent.verticalCenter
            width: 32
            height: 32
            radius: 16
            antialiasing: true
            color: Qt.rgba(1, 1, 1, iconMouse.containsMouse && row.iconClickable ? 0.12 : 0.07)
            scale: iconMouse.pressed ? 0.88 : 1
            Behavior on color { ColorAnimation { duration: 90 } }
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.48; epsilon: 0.005 } }
            Image {
                id: iconPic
                anchors.centerIn: parent
                width: 20; height: 20
                visible: row.iconSource !== "" && status === Image.Ready
                source: row.iconSource
                sourceSize: Qt.size(40, 40)
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
                opacity: row.muted ? 0.4 : 1
                Behavior on opacity { NumberAnimation { duration: 96 } }
            }
            Text {
                renderType: Text.QtRendering
                anchors.centerIn: parent
                visible: !iconPic.visible
                text: row.icon
                font.family: row.iconFont
                font.pixelSize: row.iconFont === "Segoe Fluent Icons" ? 15 : 14
                font.weight: row.iconFont === "Segoe Fluent Icons" ? Font.Normal : Font.Bold
                color: row.muted ? Qt.rgba(1, 1, 1, 0.4) : "white"
                Behavior on color { ColorAnimation { duration: 96 } }
            }
            MouseArea {
                id: iconMouse
                anchors.fill: parent
                hoverEnabled: true
                enabled: row.iconClickable
                cursorShape: row.iconClickable ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: row.iconClicked()
            }
        }

        // track
        Item {
            id: track
            x: 42
            anchors.verticalCenter: parent.verticalCenter
            width: row.width - 42 - (row.showValue ? 46 : 8) - (row.hasMore ? 30 : 0)
            height: 24

            Rectangle {
                y: 12 - height / 2
                width: parent.width
                height: sliderMouse.pressed ? 12 : 10
                radius: height / 2
                antialiasing: true
                color: Qt.rgba(1, 1, 1, 0.12)
                Behavior on height { NumberAnimation { duration: 96; easing.type: Easing.OutCubic } }
            }
            Rectangle {
                id: fill
                y: 12 - height / 2
                width: Math.max(height, row.shown * parent.width)
                height: sliderMouse.pressed ? 12 : 10
                radius: height / 2
                antialiasing: true
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: row.accent }
                    GradientStop { position: 1; color: row.lavender }
                }
                opacity: row.muted && !row.dragging ? 0.35 : 1
                Behavior on width { NumberAnimation { duration: row.dragging ? 45 : 170; easing.type: Easing.OutCubic } }
                Behavior on height { NumberAnimation { duration: 96; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 96 } }
            }
            // thumb: a circle that stretches into a pill while pressed
            Rectangle {
                width: sliderMouse.pressed ? 26 : (sliderMouse.containsMouse ? 20 : 18)
                height: sliderMouse.pressed ? 20 : (sliderMouse.containsMouse ? 20 : 18)
                radius: height / 2
                antialiasing: true
                y: 12 - height / 2
                x: Math.max(0, Math.min(track.width - width, fill.width - width / 2))
                color: "white"
                Behavior on width { SpringAnimation { spring: 11.2; damping: 0.55; epsilon: 0.1 } }
                Behavior on height { SpringAnimation { spring: 11.2; damping: 0.55; epsilon: 0.1 } }
            }
            MouseArea {
                id: sliderMouse
                anchors.fill: parent
                anchors.topMargin: -6
                anchors.bottomMargin: -6
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                function setFrom(mx) {
                    var v = Math.max(0, Math.min(1, mx / width))
                    row.dragValue = v
                    row.moved(v)
                }
                onPressed: (m) => { row.dragging = true; setFrom(m.x) }
                onPositionChanged: (m) => { if (pressed) setFrom(m.x) }
                onReleased: row.dragging = false
                onCanceled: row.dragging = false
            }
        }

        Text {
            renderType: Text.QtRendering
            visible: row.showValue
            x: track.x + track.width + 6
            width: 34
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignRight
            text: row.unavailable ? "n/a" : (row.muted && !row.dragging ? "Muted" : Math.round(row.shown * 100 * row.displayScale) + "%")
            color: row.muted && !row.dragging ? Qt.rgba(1, 1, 1, 0.45) : "white"
            font.family: row.uiFont
            font.pixelSize: row.muted && !row.dragging ? 10 : 12
            font.weight: Font.DemiBold
            scale: row.dragging ? 1.12 : 1
            transformOrigin: Item.Right
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.005 } }
        }

        // > to the in-panel page (volume mixer)
        Rectangle {
            visible: row.hasMore
            x: row.width - width
            anchors.verticalCenter: parent.verticalCenter
            width: 26
            height: 26
            radius: 13
            antialiasing: true
            color: Qt.rgba(1, 1, 1, moreMouse.containsMouse ? 0.14 : 0.07)
            scale: moreMouse.pressed ? 0.88 : 1
            Behavior on color { ColorAnimation { duration: 90 } }
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.005 } }
            Text {
                renderType: Text.QtRendering
                anchors.centerIn: parent
                text: "\uE76C"
                font.family: "Segoe Fluent Icons"
                font.pixelSize: 11
                color: "white"
            }
            MouseArea {
                id: moreMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: row.more()
            }
        }
    }

    // quick-settings tile. turning it on is a liquid fill: the accent grows out of the icon disc and floods the tile
    // (and shrinks back into the disc when turned off). hover lifts it, press squishes it, both on springs.
    component CcTile: Item {
        id: tile

        property string icon: ""
        property string name: ""
        property string status: ""
        property bool active: false
        property bool hasMore: false
        property bool enabledTile: true

        property color accent: "#4cbcff"
        readonly property color inkOn: ((0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55) ? "#000000" : "#ffffff"
        property color hoverColor: Qt.rgba(1, 1, 1, 0.1)
        property string uiFont: "CaskaydiaCove NFP"

        signal toggled()
        signal more()

        readonly property bool hot: bodyMouse.containsMouse || moreMouse.containsMouse

        // 0 = fill is just the icon disc, 1 = fill covers the tile
        property real p: active ? 1 : 0
        Behavior on p { NumberAnimation { duration: 252; easing.type: Easing.OutCubic } }

        implicitHeight: 96

        Item {
            id: body
            anchors.fill: parent
            opacity: tile.enabledTile ? 1 : 0.4
            scale: bodyMouse.pressed ? 0.94 : (tile.hot ? 1.03 : 1)
            Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.48; epsilon: 0.005 } }

            Rectangle { anchors.fill: parent; radius: 20; antialiasing: true; color: Qt.rgba(1, 1, 1, 0.07) }

            // liquid fill
            Rectangle {
                visible: tile.p > 0.001
                x: 12 * (1 - tile.p)
                y: 11 * (1 - tile.p)
                width: 30 + (parent.width - 30) * tile.p
                height: 30 + (parent.height - 30) * tile.p
                radius: 15 + 5 * tile.p
                antialiasing: true
                color: tile.accent
                opacity: Math.min(1, tile.p * 6)
            }

            // hover wash
            Rectangle {
                anchors.fill: parent
                radius: 20
                antialiasing: true
                color: tile.active ? Qt.rgba(1, 1, 1, 0.14) : tile.hoverColor
                opacity: tile.hot ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 96 } }
            }

            // icon in a soft disc
            Rectangle {
                x: 12
                y: 11
                width: 30
                height: 30
                radius: 15
                antialiasing: true
                color: tile.active ? Qt.rgba(tile.inkOn.r, tile.inkOn.g, tile.inkOn.b, 0.14) : Qt.rgba(1, 1, 1, 0.08)
                Behavior on color { ColorAnimation { duration: 132 } }
                Text {
                    renderType: Text.QtRendering
                    anchors.centerIn: parent
                    text: tile.icon
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 15
                    color: tile.active ? tile.inkOn : "white"
                    scale: tile.active ? 1.0 : 0.94
                    rotation: tile.active ? 0 : -12
                    Behavior on scale { SpringAnimation { spring: 8; damping: 0.4; epsilon: 0.005 } }
                    Behavior on rotation { SpringAnimation { spring: 8; damping: 0.4; epsilon: 0.05 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            Text {
                renderType: Text.QtRendering
                x: 12
                y: parent.height - 38
                width: parent.width - 24 - (tile.hasMore ? 8 : 0)
                text: tile.name
                elide: Text.ElideRight
                color: tile.active ? tile.inkOn : "white"
                font.family: tile.uiFont
                font.pixelSize: 11
                font.weight: Font.DemiBold
                Behavior on color { ColorAnimation { duration: 120 } }
            }
            Text {
                renderType: Text.QtRendering
                x: 12
                y: parent.height - 23
                width: parent.width - 24 - (tile.hasMore ? 8 : 0)
                text: tile.status
                visible: text !== ""
                elide: Text.ElideRight
                color: tile.active ? Qt.rgba(tile.inkOn.r, tile.inkOn.g, tile.inkOn.b, 0.62) : Qt.rgba(1, 1, 1, 0.5)
                font.family: tile.uiFont
                font.pixelSize: 9
                Behavior on color { ColorAnimation { duration: 120 } }
            }

            // chevron (opens the in-panel page)
            Rectangle {
                visible: tile.hasMore
                x: parent.width - width - 8
                y: 10
                width: 26
                height: 32
                radius: 13
                antialiasing: true
                color: tile.active ? Qt.rgba(tile.inkOn.r, tile.inkOn.g, tile.inkOn.b, 0.16) : Qt.rgba(1, 1, 1, 0.1)
                opacity: moreMouse.containsMouse ? 1 : 0.7
                Behavior on opacity { NumberAnimation { duration: 84 } }
                Text {
                    renderType: Text.QtRendering
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: moreMouse.containsMouse ? 2 : 0
                    Behavior on anchors.horizontalCenterOffset { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.05 } }
                    text: "\uE76C"
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 11
                    color: tile.active ? tile.inkOn : "white"
                }
            }
        }

        MouseArea {
            id: bodyMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: tile.enabledTile
            cursorShape: Qt.PointingHandCursor
            onClicked: tile.toggled()
        }
        MouseArea {
            id: moreMouse
            visible: tile.hasMore
            enabled: tile.hasMore && tile.enabledTile
            x: parent.width - width - 4
            y: 6
            width: 34
            height: 40
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: tile.more()
        }
    }

    // one list row (a Wi-Fi network, a Bluetooth device or the "Add network" form). click to expand: optional name /
    // password boxes, an optional security button and one action button. while `busy` the row only shows its status.
    // Wi-Fi rows show signal bars, Bluetooth rows show a glyph. the connected row is tinted with the accent.
    component CcRow: Item {
        id: r

        property string icon: ""            // glyph in the disc (used when signalBars < 0)
        property int signalBars: -1         // 0..4, -1 = use the glyph instead
        property string title: ""
        property string sub: ""
        property bool warn: false           // sub line is an error / hint: orange
        property bool connected: false
        property bool lock: false
        property bool expanded: false
        property bool busy: false
        property bool askName: false        // "Add network": a name box above the password
        property bool needsPassword: false
        property string secText: ""         // "Security: WPA2" button (add-network form)
        property string actionText: ""      // "" = nothing to do (enterprise networks, say)
        property color accent: "#4cbcff"
        property color lavender: "#d2bcff"
        property color hoverColor: Qt.rgba(1, 1, 1, 0.1)
        property string uiFont: "CaskaydiaCove NFP"

        readonly property color ink: ((0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55) ? "#000000" : "#ffffff"
        readonly property string typedName: nameInput.text
        readonly property string typedPassword: pwInput.text
        readonly property bool hasExtra: !busy && (askName || needsPassword || secText !== "" || actionText !== "")

        signal toggled()
        signal activated(string password)
        signal secClicked()

        readonly property real headH: 54

        height: expanded && hasExtra ? headH + extra.implicitHeight + 12 : headH
        clip: true
        Behavior on height { NumberAnimation { duration: 156; easing.type: Easing.OutCubic } }

        // the popup doesn't take keyboard focus by default (so it never steals it from your app), Vapor turns that
        // on while a row that needs typing is open and then we grab the focus here
        function focusInput() {
            if (askName) nameInput.forceActiveFocus()
            else if (needsPassword) pwInput.forceActiveFocus()
        }
        onExpandedChanged: if (expanded && !busy && (askName || needsPassword)) focusTimer.restart()
        Timer {
            id: focusTimer
            interval: 90
            onTriggered: {
                if (r.Window.window) r.Window.window.requestActivate()
                r.focusInput()
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: 20
            antialiasing: true
            color: r.connected ? Qt.rgba(r.accent.r, r.accent.g, r.accent.b, 0.16) : Qt.rgba(1, 1, 1, 0.06)
            border.width: r.connected ? 1 : 0
            border.color: Qt.rgba(r.accent.r, r.accent.g, r.accent.b, 0.45)
            Behavior on color { ColorAnimation { duration: 132 } }
        }
        Rectangle {
            anchors.fill: parent
            radius: 20
            antialiasing: true
            color: r.hoverColor
            opacity: headMouse.containsMouse ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 90 } }
        }

        // disc with signal bars or glyph
        Rectangle {
            x: 12
            y: 9
            width: 36
            height: 36
            radius: 18
            antialiasing: true
            color: r.connected ? r.accent : Qt.rgba(1, 1, 1, 0.09)
            Behavior on color { ColorAnimation { duration: 132 } }
            Row {
                visible: r.signalBars >= 0
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: 4
                    Rectangle {
                        required property int index
                        width: 3
                        height: 5 + index * 3
                        radius: 1.5
                        antialiasing: true
                        anchors.bottom: parent.bottom
                        color: index < r.signalBars
                               ? (r.connected ? r.ink : "white")
                               : (r.connected ? Qt.rgba(r.ink.r, r.ink.g, r.ink.b, 0.28) : Qt.rgba(1, 1, 1, 0.22))
                    }
                }
            }
            Text {
                renderType: Text.QtRendering
                visible: r.signalBars < 0
                anchors.centerIn: parent
                text: r.icon
                font.family: "Segoe Fluent Icons"
                font.pixelSize: 16
                color: r.connected ? r.ink : "white"
            }
        }

        Text {
            renderType: Text.QtRendering
            x: 58
            y: 11
            width: r.width - 58 - 40
            text: r.title
            elide: Text.ElideRight
            color: "white"
            font.family: r.uiFont
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }
        Text {
            renderType: Text.QtRendering
            x: 58
            y: 30
            width: r.width - 58 - 40
            text: r.sub
            elide: Text.ElideRight
            color: r.warn ? "#ffb86b" : (r.connected ? Qt.lighter(r.accent, 1.25) : Qt.rgba(1, 1, 1, 0.5))
            font.family: r.uiFont
            font.pixelSize: 10
        }
        Text {
            renderType: Text.QtRendering
            visible: r.lock
            x: r.width - 32
            y: 0
            height: r.headH
            verticalAlignment: Text.AlignVCenter
            text: "\uE72E"
            font.family: "Segoe Fluent Icons"
            font.pixelSize: 12
            color: Qt.rgba(1, 1, 1, 0.45)
        }

        MouseArea {
            id: headMouse
            x: 0
            y: 0
            width: r.width
            height: r.headH
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: r.toggled()
        }

        Column {
            id: extra
            x: 12
            y: r.headH
            width: r.width - 24
            spacing: 8
            visible: r.hasExtra

            Rectangle {
                visible: r.askName
                width: parent.width
                height: 36
                radius: 18
                antialiasing: true
                color: Qt.rgba(0, 0, 0, 0.28)
                border.width: 1
                border.color: nameInput.activeFocus ? r.accent : Qt.rgba(1, 1, 1, 0.12)
                Behavior on border.color { ColorAnimation { duration: 90 } }
                TextInput {
                    id: nameInput
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    verticalAlignment: TextInput.AlignVCenter
                    color: "white"
                    selectByMouse: true
                    clip: true
                    font.family: r.uiFont
                    font.pixelSize: 12
                    onAccepted: if (r.needsPassword) pwInput.forceActiveFocus(); else r.activated(pwInput.text)
                }
                Text {
                    renderType: Text.QtRendering
                    visible: nameInput.text === ""
                    anchors.verticalCenter: parent.verticalCenter
                    x: 14
                    text: "Network name"
                    color: Qt.rgba(1, 1, 1, 0.38)
                    font.family: r.uiFont
                    font.pixelSize: 12
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.IBeamCursor; onClicked: nameInput.forceActiveFocus() }
            }

            Rectangle {
                visible: r.needsPassword
                width: parent.width
                height: 36
                radius: 18
                antialiasing: true
                color: Qt.rgba(0, 0, 0, 0.28)
                border.width: 1
                border.color: pwInput.activeFocus ? r.accent : Qt.rgba(1, 1, 1, 0.12)
                Behavior on border.color { ColorAnimation { duration: 90 } }
                TextInput {
                    id: pwInput
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: TextInput.Password
                    color: "white"
                    selectByMouse: true
                    clip: true
                    font.family: r.uiFont
                    font.pixelSize: 12
                    onAccepted: r.activated(text)
                }
                Text {
                    renderType: Text.QtRendering
                    visible: pwInput.text === ""
                    anchors.verticalCenter: parent.verticalCenter
                    x: 14
                    text: r.askName ? "Password" : "Network security key"
                    color: Qt.rgba(1, 1, 1, 0.38)
                    font.family: r.uiFont
                    font.pixelSize: 12
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.IBeamCursor; onClicked: pwInput.forceActiveFocus() }
            }

            CcButton {
                visible: r.secText !== ""
                width: parent.width
                text: r.secText
                icon: "\uE72E"
                accent: r.accent
                hoverColor: r.hoverColor
                uiFont: r.uiFont
                onClicked: r.secClicked()
            }

            CcButton {
                visible: r.actionText !== ""
                width: parent.width
                text: r.actionText
                primary: !r.connected
                danger: r.connected
                accent: r.accent
                hoverColor: r.hoverColor
                uiFont: r.uiFont
                onClicked: r.activated(pwInput.text)
            }
        }
    }

    // the five power-menu icons, drawn with strokes like the old full-screen power overlay
    component CcPowerGlyph: Canvas {
        id: g
        property string kind: "shutdown"
        property color ink: "#d2bcff"
        width: 40
        height: 40
        onKindChanged: requestPaint()
        onInkChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            c.scale(width / 40, height / 40)
            c.strokeStyle = ink
            c.fillStyle = ink
            c.lineWidth = 3
            c.lineCap = "round"
            c.lineJoin = "round"
            var cx = 20, cy = 20, r = 12
            function head(x, y, dx, dy, s) {
                var px = -dy, py = dx
                c.beginPath()
                c.moveTo(x + dx * s * 0.6, y + dy * s * 0.6)
                c.lineTo(x - dx * s * 0.6 + px * s * 0.7, y - dy * s * 0.6 + py * s * 0.7)
                c.lineTo(x - dx * s * 0.6 - px * s * 0.7, y - dy * s * 0.6 - py * s * 0.7)
                c.closePath()
                c.fill()
            }
            if (kind === "shutdown") {
                c.beginPath()
                c.arc(cx, cy + 1, r, -Math.PI / 2 + 0.62, -Math.PI / 2 - 0.62 + 2 * Math.PI, false)
                c.stroke()
                c.beginPath()
                c.moveTo(cx, cy - 15)
                c.lineTo(cx, cy - 2)
                c.stroke()
            } else if (kind === "restart") {
                var a0 = -Math.PI / 6, a1 = a0 + 1.5 * Math.PI
                c.beginPath()
                c.arc(cx, cy, r, a0, a1, false)
                c.stroke()
                var tx = cx + r * Math.cos(a1), ty = cy + r * Math.sin(a1)
                head(tx, ty, -Math.sin(a1), Math.cos(a1), 9)
            } else if (kind === "signout") {
                c.beginPath()
                c.moveTo(cx + 3, cy - 13)
                c.lineTo(cx - 10, cy - 13)
                c.lineTo(cx - 10, cy + 13)
                c.lineTo(cx + 3, cy + 13)
                c.stroke()
                c.beginPath()
                c.moveTo(cx - 3, cy)
                c.lineTo(cx + 11, cy)
                c.stroke()
                head(cx + 13, cy, 1, 0, 10)
            } else if (kind === "hibernate") {
                c.beginPath()
                c.arc(cx, cy, r, 0, 2 * Math.PI, false)
                c.stroke()
                c.fillRect(cx - 5, cy - 5, 10, 10)
            } else if (kind === "sleep") {
                c.beginPath()
                c.arc(cx, cy, 13, 0, 2 * Math.PI, false)
                c.fill()
                c.globalCompositeOperation = "destination-out"
                c.beginPath()
                c.arc(cx + 8, cy - 5, 11, 0, 2 * Math.PI, false)
                c.fill()
                c.globalCompositeOperation = "source-over"
            } else if (kind === "cancel") {
                c.beginPath()
                c.moveTo(cx - 10, cy - 10); c.lineTo(cx + 10, cy + 10)
                c.moveTo(cx + 10, cy - 10); c.lineTo(cx - 10, cy + 10)
                c.stroke()
            }
        }
    }

    // a system-stats card: name, big value, detail line and a row of history bars (same look as the audio visualizer
    // in the bar). `hist` is a list of 0..1 values, oldest first, `n` long.
    component CcStat: Rectangle {
        id: card

        property string name: ""
        property string value: ""
        property string detail: ""
        property var hist: []
        property color accent: "#4cbcff"
        property color lavender: "#d2bcff"
        property string uiFont: "CaskaydiaCove NFP"
        readonly property int n: 22

        implicitHeight: 100
        radius: 22
        antialiasing: true
        color: Qt.rgba(1, 1, 1, 0.06)

        function mix(a, b, t) { return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1) }

        Text {
            renderType: Text.QtRendering
            x: 14
            y: 11
            text: card.name.toUpperCase()
            color: Qt.rgba(1, 1, 1, 0.55)
            font.family: card.uiFont
            font.pixelSize: 10
            font.weight: Font.DemiBold
            font.letterSpacing: 1.2
        }
        Text {
            renderType: Text.QtRendering
            x: 14
            y: 25
            text: card.value
            color: "white"
            font.family: card.uiFont
            font.pixelSize: 20
            font.weight: Font.Bold
        }
        Text {
            renderType: Text.QtRendering
            x: 14
            y: 51
            width: card.width - 28
            text: card.detail
            elide: Text.ElideRight
            color: Qt.rgba(1, 1, 1, 0.5)
            font.family: card.uiFont
            font.pixelSize: 10
        }
        Item {
            id: bars
            x: 14
            y: card.height - 12 - 24
            width: card.width - 28
            height: 24
            Repeater {
                model: card.n
                Rectangle {
                    required property int index
                    readonly property real v: card.hist.length > index ? card.hist[index] : 0
                    x: index * ((bars.width - 3) / (card.n - 1))
                    anchors.bottom: parent.bottom
                    width: 3
                    height: 3 + v * 21
                    radius: 1.5
                    antialiasing: true
                    color: card.mix(card.accent, card.lavender, index / (card.n - 1))
                    opacity: 0.55 + 0.45 * (index / (card.n - 1))
                    Behavior on height { NumberAnimation { duration: 96 } }
                }
            }
        }
    }


    // ---- set by Vapor ----
    property bool active: false          // true while the panel is showing this page
    signal powerRequested()              // Vapor opens the full-screen PowerMenu
    signal closeRequested()              // Settings / Configure / Project / Cast / power: ask the bar to close the popup

    Connections {
        target: CC
        function onCloseRequested() { cc.closeRequested() }
    }

    // true while a row that needs typing (Wi-Fi password, add network) is open, Vapor then lets the popup take focus
    property bool hexEditing: false
    onShowPickerChanged: if (!showPicker) hexEditing = false
    readonly property bool wantsKeyboard: active && ((sub === "wifi" && wifiOpen !== "" && rowNeedsKb(wifiOpen, modelRev))
                                                   || (sub === "main" && showPicker && hexEditing))

    // ---- theme: the picker previews live in this panel, the bar follows straight away ----
    // the picker edits one target at a time: "shell" (glass fill), "outline" (its rim) or "icons" (every accent / icon).
    // each target either follows the wallpaper (auto) or is the exact colour you picked (custom). the panel just
    // shows what the bar shows (B), the picker hands the colour to CC.setTarget() which recolors the bar at once.
    property real hsvH: 0.5576
    property real hsvS: 0.702
    property real hsvV: 1.0
    property string themeTarget: "icons"
    property bool themeOpen: false
    property bool showPicker: false
    readonly property var themeSt: CC.themeState || ({})
    readonly property bool targetCustom: !!(themeSt[themeTarget] && themeSt[themeTarget].mode === "custom")
    readonly property bool themeTouched: targetCustom
    readonly property color themeColor: Qt.hsva(hsvH, hsvS, hsvV, 1)

    // ---- the bar's colours ----
    // the panel's own buttons, tiles, sliders and hover wash all use the shell's outline colour
    // (everything in the panel follows the icon accent, the same colour as the bar's icons)
    readonly property color iconColor: Qt.color(B.themeAccent)
    readonly property real iconHue: iconColor.hsvHue < 0 ? 0 : iconColor.hsvHue
    readonly property color accent: iconColor
    readonly property color blue: Qt.hsva(iconHue, iconColor.hsvSaturation * 0.45, Math.min(1, iconColor.hsvValue + 0.14), 0.95)
    readonly property color lavender: Qt.hsva((iconHue + 0.1) % 1, iconColor.hsvSaturation * 0.6, Math.min(1, iconColor.hsvValue + 0.1), 1)
    readonly property color hoverColor: Qt.rgba(iconColor.r, iconColor.g, iconColor.b, 0.16)
    readonly property string uiFont: "CaskaydiaCove NFP"
    readonly property color muted: Qt.rgba(1, 1, 1, 0.55)
    readonly property color cardColor: Qt.rgba(1, 1, 1, 0.06)

    width: 380
    height: pageHeight

    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

    // the colour the bar currently shows for a target
    function currentColor(t) {
        return Qt.color(t === "shell" ? B.glassColor : (t === "outline" ? B.glassOutline : B.themeAccent))
    }
    // picker <- the bar (used while the target follows the wallpaper)
    function syncFromBar() {
        var a = currentColor(themeTarget)
        if (a.hsvHue >= 0) hsvH = a.hsvHue
        hsvS = a.hsvSaturation
        hsvV = a.hsvValue
    }
    // picker <- the saved colour of the selected target (or the bar if it follows the wallpaper)
    function loadTarget() {
        var st = themeSt[themeTarget]
        if (st && st.mode === "custom") { hsvH = st.h; hsvS = st.s; hsvV = st.v }
        else syncFromBar()
    }
    function selectTarget(t) { themeTarget = t; loadTarget() }
    function isCustom(t) { return !!(themeSt[t] && themeSt[t].mode === "custom") }
    readonly property bool anyCustom: isCustom("shell") || isCustom("outline") || isCustom("icons")
    function followWallpaper() { CC.resetTheme(); syncFromBar() }
    Connections {
        target: B
        function onThemeAccentChanged() { if (!cc.targetCustom) cc.syncFromBar() }
        function onGlassColorChanged() { if (!cc.targetCustom) cc.syncFromBar() }
        function onGlassOutlineChanged() { if (!cc.targetCustom) cc.syncFromBar() }
    }
    function themeEdited() { CC.setTarget(themeTarget, "custom", hsvH, hsvS, hsvV) }
    function themeReset() {
        CC.resetTarget(themeTarget)
        syncFromBar()
    }
    function hexOf(c) {
        function h(v) { var s = Math.round(v * 255).toString(16); return (s.length < 2 ? "0" : "") + s }
        return (h(c.r) + h(c.g) + h(c.b)).toUpperCase()
    }
    function setSV(s, v) {
        hsvS = clamp(s, 0, 1)
        hsvV = clamp(v, 0, 1)
        themeEdited()
    }
    function applyHex(txt) {
        var c = Qt.color("#" + txt)
        if (c.hsvHue >= 0) hsvH = c.hsvHue
        setSV(c.hsvSaturation, c.hsvValue)
    }

    // ---- navigation + animation helpers ----
    property string sub: "main"          // main, wifi, bt, mixer, stats, clean
    readonly property real pageHeight: sub === "wifi" ? pgWifi.h : sub === "bt" ? pgBt.h
                                     : sub === "mixer" ? pgMixer.h : sub === "stats" ? pgStats.h
                                     : sub === "clean" ? pgClean.h : pgMain.h

    function back(t) { var c1 = 1.5, c3 = c1 + 1, u = t - 1; return 1 + c3 * u * u * u + c1 * u * u }   // ease-out-back

    // opening: block i starts a little after block i-1
    property real enter: 1
    function stag(i) { return Math.max(0, Math.min(1, (enter - i * 0.045) / 0.5)) }
    NumberAnimation { id: enterAnim; target: cc; property: "enter"; from: 0; to: 1; duration: 440; easing.type: Easing.Linear }

    // entering a sub-page: header, caption, list, footer follow one another
    property real subT: 1
    function sst(i) { return Math.max(0, Math.min(1, (subT - i * 0.08) / 0.55)) }
    NumberAnimation { id: subAnim; target: cc; property: "subT"; from: 0; to: 1; duration: 360; easing.type: Easing.Linear }
    onSubChanged: { subT = 0; subAnim.restart(); enterSub() }

    // what each page needs from the system when it opens
    function enterSub() {
        if (!active) return
        if (sub === "wifi") { wifiOpen = ""; CC.scanWifi() }
        else if (sub === "bt") { btOpen = ""; CC.scanBt() }
        else if (sub === "mixer") CC.refreshApps()
        else if (sub === "stats") { resetStats(); CC.startStats() }
        else if (sub === "clean" && CC.cleanState !== "running") { logModel.clear(); CC.cleanReset(); CC.cleanScan() }
    }

    onActiveChanged: {
        if (active) {
            resetTimer.stop(); enter = 0; enterAnim.restart()
            CC.refresh()                         // radios, DND, dark mode, brightness, mic: fresh every time it opens
            enterSub()
        } else resetTimer.restart()
    }
    // once the panel is gone the next opening starts on the main page again
    Timer {
        id: resetTimer
        interval: 450
        onTriggered: { cc.sub = "main"; cc.wifiOpen = ""; cc.btOpen = ""; cc.showPicker = false; cc.themeOpen = false; cc.hexEditing = false }
    }

    // ---- state helpers ----
    function volGlyph() {
        return (B.muted || B.volume <= 0) ? "\uE74F" : B.volume <= 5 ? "\uE992" : B.volume <= 20 ? "\uE993" : B.volume <= 50 ? "\uE994" : "\uE995"
    }
    function wifiStatus() {
        if (CC.wifiMissing) return "Not found"
        if (CC.errors && CC.errors.wifi) return "Error - retry"
        if (!CC.wifiOn) return "Off"
        return B.wifiConnected ? B.wifiName : "Not connected"
    }
    function btStatus() {
        if (CC.btMissing) return "Not found"
        if (CC.errors && CC.errors.bt) return "Error - retry"
        if (!CC.btOn) return "Off"
        return B.headphones !== "" ? B.headphones : "On"
    }

    // ---- lists: the backend hands over plain arrays, these ListModels keep the rows (and their animations) stable ----
    function syncModel(model, want, key) {
        for (var i = model.count - 1; i >= 0; i--) {
            var k = model.get(i)[key], found = false
            for (var a = 0; a < want.length; a++) if (want[a][key] === k) { found = true; break }
            if (!found) model.remove(i)
        }
        for (var j = 0; j < want.length; j++) {
            var w = want[j], idx = -1
            for (var m = j; m < model.count; m++) if (model.get(m)[key] === w[key]) { idx = m; break }
            if (idx < 0) { model.insert(j, w); continue }
            if (idx !== j) model.move(idx, j, 1)
            var row = model.get(j)
            for (var f in w) if (row[f] !== w[f]) model.setProperty(j, f, w[f])
        }
    }

    ListModel { id: wifiModel }
    ListModel { id: btModel }
    ListModel { id: appModel }
    ListModel { id: logModel }
    property int modelRev: 0
    property string wifiOpen: ""
    property string btOpen: ""
    property bool addWasBusy: false
    property int addSec: 0
    readonly property var secList: [ ["WPA2", "WPA2-Personal"], ["WPA3", "WPA3-Personal"], ["Open", "Open"] ]

    function rowNeedsKb(ssid, rev) {
        if (ssid === "__add__") return true
        for (var i = 0; i < wifiModel.count; i++) {
            var w = wifiModel.get(i)
            if (w.ssid === ssid) return w.link === "new" && w.secure && w.busyText === ""
        }
        return false
    }

    function syncWifi() {
        var nets = CC.wifiNets || [], busy = CC.wifiBusy || ({}), notes = CC.wifiNotes || ({})
        var want = []
        for (var i = 0; i < nets.length; i++) {
            var n = nets[i], sig = n.signal, au = (n.auth || "").toLowerCase()
            want.push({ ssid: n.ssid, secure: au !== "open", ent: au.indexOf("enterprise") >= 0,
                        bars: sig >= 75 ? 4 : sig >= 50 ? 3 : sig >= 25 ? 2 : sig > 0 ? 1 : -1,
                        link: n.connected ? "connected" : (n.known ? "saved" : "new"),
                        busyText: busy[n.ssid] || "", noteText: notes[n.ssid] || "" })
        }
        var ab = busy["__add__"] || "", an = notes["__add__"] || ""
        want.push({ ssid: "__add__", secure: false, ent: false, bars: -1, link: "add", busyText: ab, noteText: an })
        if (ab !== "") addWasBusy = true
        else if (addWasBusy) { addWasBusy = false; if (an === "") wifiOpen = "" }
        syncModel(wifiModel, want, "ssid")
        modelRev++
    }
    function syncBt() {
        var devs = CC.btDevices || [], busy = CC.btBusy || ({}), notes = CC.btNotes || ({})
        var want = []
        for (var i = 0; i < devs.length; i++) {
            var d = devs[i]
            want.push({ addr: d.addr, devName: d.name, glyph: d.glyph, link: d.connected ? "connected" : "paired",
                        busyText: busy[d.addr] || "", noteText: notes[d.addr] || "" })
        }
        syncModel(btModel, want, "addr")
    }
    property var appTouch: ({})
    function touchApp(k) { appTouch[k] = Date.now() }
    function syncApps() {
        var list = CC.apps || [], want = [], now = Date.now()
        for (var i = 0; i < list.length; i++) {
            var a = list[i], lvl = a.vol, mt = a.muted
            if (appTouch[a.key] && now - appTouch[a.key] < 1500) {      // you just moved it, don't snap back to the old reading
                for (var m = 0; m < appModel.count; m++) {
                    var e = appModel.get(m)
                    if (e.appKey === a.key) { lvl = e.level; mt = e.mute; break }
                }
            }
            want.push({ appKey: a.key, appName: a.name, level: lvl, mute: mt, playing: a.active,
                        iconUrl: (B.appIcon(a.key, a.name) || "") })
        }
        syncModel(appModel, want, "appKey")
    }

    Connections {
        target: CC
        function onWifiNetsChanged() { cc.syncWifi() }
        function onWifiBusyChanged() { cc.syncWifi() }
        function onWifiNotesChanged() { cc.syncWifi() }
        function onBtDevicesChanged() { cc.syncBt() }
        function onBtBusyChanged() { cc.syncBt() }
        function onBtNotesChanged() { cc.syncBt() }
        function onAppsChanged() { cc.syncApps() }
        function onCleanLine(kind, text) {
            logModel.append({ kind: kind, line: text })
            if (logModel.count > 400) logModel.remove(0)
        }
    }

    function wifiAct(ssid, link, pw) {
        wifiOpen = ""
        if (link === "connected") CC.wifiDisconnect(ssid)
        else CC.wifiConnect(ssid, pw)
    }
    function wifiAddGo(name, pw) {
        addWasBusy = true
        CC.wifiAdd(name, pw, secList[addSec][1])
    }
    function btAct(addr, link) {
        btOpen = ""
        CC.btSet(addr, link !== "connected")
    }

    // ---- live stats (polled once a second, only while the stats page is showing) ----
    property var cpuH: []
    property var memH: []
    property var gpuH: []
    property var netH: []
    property var netRaw: []
    property real cpuNow: 0
    property real memNow: 0
    property real gpuNow: 0
    function pushH(a, v) { var b = a.slice(a.length >= 22 ? a.length - 21 : 0); b.push(v); return b }
    function resetStats() { cpuH = []; memH = []; gpuH = []; netH = []; netRaw = [] }
    function fmtRate(b) {
        if (b < 1024) return Math.round(b) + " B/s"
        if (b < 1048576) return (b / 1024).toFixed(1) + " KB/s"
        return (b / 1048576).toFixed(1) + " MB/s"
    }
    function gb(b) { return (b / 1073741824).toFixed(1) }
    function tickStats() {
        CC.sampleStats()
        cpuNow = CC.cpu / 100
        memNow = CC.memTotal > 0 ? CC.memUsed / CC.memTotal : 0
        var g = CC.gpu
        gpuNow = (g && g.util !== undefined) ? g.util / 100 : 0
        cpuH = pushH(cpuH, cpuNow); memH = pushH(memH, memNow); gpuH = pushH(gpuH, gpuNow)
        netRaw = pushH(netRaw, CC.netRx)
        var mx = 262144                          // at least 256 KB/s so a trickle doesn't fill the whole graph
        for (var i = 0; i < netRaw.length; i++) mx = Math.max(mx, netRaw[i])
        var nh = []
        for (var k = 0; k < netRaw.length; k++) nh.push(netRaw[k] / mx)
        netH = nh
    }
    Timer { interval: 1000; repeat: true; triggeredOnStart: true; running: cc.active && cc.sub === "stats"; onTriggered: cc.tickStats() }
    Timer { interval: 2000; repeat: true; running: cc.active && cc.sub === "mixer"; onTriggered: CC.refreshApps() }

    Component.onCompleted: { loadTarget(); syncWifi(); syncBt(); syncApps() }

    // ---- main page ----
    Item {
        id: pgMain
        readonly property bool on: cc.sub === "main"
        readonly property real h: mainCol.implicitHeight + 14 + 16
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : -30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        Column {
            id: mainCol
            x: 16
            y: 14
            width: 348
            spacing: 8

            // ---- header ----
            Item {
                width: parent.width
                height: 32
                opacity: cc.stag(0)
                transform: Translate { y: (1 - cc.back(cc.stag(0))) * 14 }
                Text {
                    renderType: Text.QtRendering
                    anchors.verticalCenter: parent.verticalCenter
                    x: 2
                    text: "Control Center"
                    color: "white"
                    font.family: cc.uiFont
                    font.pixelSize: 15
                    font.weight: Font.Bold
                }
                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 4
                    CcButton { round: true; icon: "\uE9D9"; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: cc.sub = "stats" }
                    CcButton { round: true; kind: "gear"; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: { B.openUri("ms-settings:"); cc.closeRequested() } }
                    CcButton { round: true; icon: "\uE7E8"; danger: true; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: cc.powerRequested() }
                }
            }

            // ---- tiles ----
            Grid {
                id: tiles
                columns: 3
                spacing: 9
                readonly property real tw: (348 - 2 * 9) / 3

                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(1); scale: 0.82 + 0.18 * cc.back(cc.stag(1))
                    icon: "\uE701"; name: "Wi-Fi"
                    status: cc.wifiStatus()
                    active: CC.wifiOn; hasMore: true; enabledTile: !CC.wifiMissing
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.setWifi(!CC.wifiOn)
                    onMore: cc.sub = "wifi"
                }
                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(2); scale: 0.82 + 0.18 * cc.back(cc.stag(2))
                    icon: "\uE702"; name: "Bluetooth"
                    status: cc.btStatus()
                    active: CC.btOn; hasMore: true; enabledTile: !CC.btMissing
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.setBt(!CC.btOn)
                    onMore: cc.sub = "bt"
                }
                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(3); scale: 0.82 + 0.18 * cc.back(cc.stag(3))
                    icon: "\uE708"; name: "Do not disturb"; status: (CC.errors && CC.errors.dnd) ? "Error - retry" : (CC.dndOn ? "On" : "Off")
                    active: CC.dndOn
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.toggleDnd()
                }
                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(4); scale: 0.82 + 0.18 * cc.back(cc.stag(4))
                    icon: "\uE7F4"; name: "Project"; status: "Display mode"
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.project()
                }
                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(5); scale: 0.82 + 0.18 * cc.back(cc.stag(5))
                    icon: "\uEC15"; name: "Cast"; status: "Wireless display"
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.cast()
                }
                CcTile {
                    width: tiles.tw
                    opacity: cc.stag(6); scale: 0.82 + 0.18 * cc.back(cc.stag(6))
                    icon: "\uF08C"; name: "Dark mode"; status: (CC.errors && CC.errors.dark) ? "Error - retry" : (CC.darkOn ? "On" : "Off")
                    active: CC.darkOn
                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                    onToggled: CC.toggleDark()
                }
            }

            // ---- sliders ----
            Rectangle {
                width: parent.width
                height: sliderCol.implicitHeight + 24
                radius: 22
                antialiasing: true
                color: cc.cardColor
                opacity: cc.stag(7)
                transform: Translate { y: (1 - cc.back(cc.stag(7))) * 16 }
                Column {
                    id: sliderCol
                    x: 14
                    y: 12
                    width: parent.width - 28
                    spacing: 4
                    CcSlider {
                        width: parent.width
                        icon: "\uE706"
                        value: Math.max(0, CC.brightness) / 100
                        unavailable: CC.brightness < 0
                        accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                        onMoved: (v) => CC.setBrightness(Math.round(v * 100))
                    }
                    CcSlider {
                        width: parent.width
                        icon: cc.volGlyph()
                        value: B.volume / 100
                        muted: B.muted
                        iconClickable: true
                        hasMore: true
                        accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                        onMoved: (v) => B.setVolume(Math.round(v * 100))
                        onIconClicked: B.toggleMute()
                        onMore: cc.sub = "mixer"
                    }
                    CcSlider {
                        width: parent.width
                        icon: CC.micMuted ? "\uEC54" : "\uE720"
                        value: Math.max(0, CC.micVolume) / 100
                        muted: CC.micMuted
                        unavailable: CC.micVolume < 0
                        iconClickable: true
                        accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                        onMoved: (v) => CC.setMic(Math.round(v * 100))
                        onIconClicked: CC.toggleMic()
                    }
                }
            }

            // ---- configure ----
            Rectangle {
                width: parent.width
                height: cfgCol.implicitHeight + 26
                radius: 22
                antialiasing: true
                color: cc.cardColor
                opacity: cc.stag(8)
                transform: Translate { y: (1 - cc.back(cc.stag(8))) * 16 }
                Column {
                    id: cfgCol
                    x: 14
                    y: 12
                    width: parent.width - 28
                    spacing: 8
                    Item {
                        width: parent.width
                        height: 16
                        Text {
                            renderType: Text.QtRendering
                            anchors.verticalCenter: parent.verticalCenter
                            text: "CONFIGURE"
                            color: cc.muted
                            font.family: cc.uiFont
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.2
                        }
                        Text {
                            renderType: Text.QtRendering
                            visible: B.hasBattery
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Battery " + B.battery + "%"
                            color: B.battery <= 15 ? "#ff6b7a" : "white"
                            font.family: cc.uiFont
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                    }
                    Row {
                        width: parent.width
                        spacing: 8
                        CcButton {
                            width: (cfgCol.width - 8) / 2
                            text: "Configure"; icon: "\uE838"
                            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                            onClicked: CC.openConfig()
                        }
                        CcButton {
                            width: (cfgCol.width - 8) / 2
                            text: "Clear cache"; icon: "\uE74D"
                            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                            onClicked: cc.sub = "clean"
                        }
                    }
                }
            }

            // ---- theme colour (folded, click the header to unfold) ----
            Rectangle {
                width: parent.width
                height: themeCol.implicitHeight + 14
                radius: 22
                antialiasing: true
                color: cc.cardColor
                opacity: cc.stag(9)
                transform: Translate { y: (1 - cc.back(cc.stag(9))) * 16 }

                Column {
                    id: themeCol
                    x: 14
                    y: 12
                    width: parent.width - 28
                    spacing: 0

                    Item {
                        width: parent.width
                        height: 34
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: cc.themeOpen = !cc.themeOpen
                        }
                        Text {
                            renderType: Text.QtRendering
                            y: 5
                            text: "THEME COLOR"
                            color: cc.muted
                            font.family: cc.uiFont
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.2
                        }
                        Row {
                            anchors.right: parent.right
                            spacing: 8
                            CcButton {
                                height: 26
                                flat: true
                                text: "Reset"
                                pixelSize: 11
                                opacity: cc.themeTouched ? 1 : 0
                                visible: opacity > 0.01
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                                onClicked: cc.themeReset()
                            }
                            Rectangle {
                                width: 24
                                height: 24
                                radius: 12
                                antialiasing: true
                                y: 1
                                color: cc.themeColor
                                border.width: 2
                                border.color: cc.showPicker ? "white" : Qt.rgba(1, 1, 1, 0.35)
                                scale: swatchMouse.pressed ? 0.85 : (swatchMouse.containsMouse ? 1.12 : 1)
                                Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.48; epsilon: 0.005 } }
                                Behavior on border.color { ColorAnimation { duration: 90 } }
                                MouseArea {
                                    id: swatchMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: { cc.themeOpen = true; cc.showPicker = !cc.showPicker }
                                }
                            }
                            Item {
                                width: 20
                                height: 26
                                Text {
                                    renderType: Text.QtRendering
                                    anchors.centerIn: parent
                                    text: "\uE70D"
                                    font.family: "Segoe Fluent Icons"
                                    font.pixelSize: 11
                                    color: cc.muted
                                    rotation: cc.themeOpen ? 180 : 0
                                    Behavior on rotation { SpringAnimation { spring: 8; damping: 0.55; epsilon: 0.1 } }
                                }
                            }
                        }
                    }

                    // everything below the header unfolds
                    Item {
                        width: parent.width
                        height: cc.themeOpen ? themeInner.implicitHeight : 0
                        visible: height > 0.5
                        clip: true
                        opacity: cc.themeOpen ? 1 : 0
                        Behavior on height { NumberAnimation { duration: 252; easing.type: Easing.OutCubic } }
                        Behavior on opacity { NumberAnimation { duration: 156 } }

                        Column {
                            id: themeInner
                            width: parent.width
                            spacing: 0

                            // colour square (saturation / value), opens with the swatch
                            Item {
                                width: parent.width
                                height: cc.showPicker ? 172 : 0
                                visible: height > 0.5
                                clip: true
                                Behavior on height { NumberAnimation { duration: 216; easing.type: Easing.OutCubic } }
                                Item {
                                    id: sq
                                    width: parent.width
                                    height: 120
                                    Rectangle { anchors.fill: parent; radius: 14; color: Qt.hsva(cc.hsvH, 1, 1, 1) }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 14
                                        antialiasing: true
                                        gradient: Gradient {
                                            orientation: Gradient.Horizontal
                                            GradientStop { position: 0; color: "#ffffffff" }
                                            GradientStop { position: 1; color: "#00ffffff" }
                                        }
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 14
                                        antialiasing: true
                                        gradient: Gradient {
                                            GradientStop { position: 0; color: "#00000000" }
                                            GradientStop { position: 1; color: "#ff000000" }
                                        }
                                    }
                                    Rectangle {
                                        width: sqMouse.pressed ? 24 : 18
                                        height: width
                                        radius: width / 2
                                        antialiasing: true
                                        color: "transparent"
                                        border.width: 2.5
                                        border.color: "white"
                                        x: cc.clamp(cc.hsvS * sq.width - width / 2, 0, sq.width - width)
                                        y: cc.clamp((1 - cc.hsvV) * sq.height - height / 2, 0, sq.height - height)
                                        Behavior on width { SpringAnimation { spring: 11.2; damping: 0.55; epsilon: 0.1 } }
                                    }
                                    MouseArea {
                                        id: sqMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.CrossCursor
                                        function setFrom(m) { cc.setSV(m.x / width, 1 - m.y / height) }
                                        onPressed: (m) => setFrom(m)
                                        onPositionChanged: (m) => { if (pressed) setFrom(m) }
                                    }
                                }

                                // HEX box: type or paste a colour, it applies as soon as the 6 digits are there
                                Rectangle {
                                    id: hexBox
                                    y: 128
                                    width: parent.width
                                    height: 36
                                    radius: 18
                                    antialiasing: true
                                    color: Qt.rgba(0, 0, 0, 0.28)
                                    border.width: 1
                                    border.color: hexIn.activeFocus ? cc.accent : Qt.rgba(1, 1, 1, 0.12)
                                    Behavior on border.color { ColorAnimation { duration: 90 } }
                                    Rectangle { x: 6; y: 6; width: 24; height: 24; radius: 12; color: cc.themeColor }
                                    Text {
                                        renderType: Text.QtRendering
                                        x: 42
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "HEX"
                                        color: cc.muted
                                        font.family: cc.uiFont
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 1.2
                                    }
                                    Text {
                                        renderType: Text.QtRendering
                                        x: 84
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "#"
                                        color: cc.muted
                                        font.family: cc.uiFont
                                        font.pixelSize: 13
                                    }
                                    TextInput {
                                        id: hexIn
                                        x: 98
                                        width: parent.width - 98 - 14
                                        height: parent.height
                                        verticalAlignment: TextInput.AlignVCenter
                                        maximumLength: 6
                                        color: "white"
                                        selectByMouse: true
                                        clip: true
                                        font.family: cc.uiFont
                                        font.pixelSize: 13
                                        font.capitalization: Font.AllUppercase
                                        validator: RegularExpressionValidator { regularExpression: /[0-9A-Fa-f]{0,6}/ }
                                        onTextEdited: if (text.length === 6) cc.applyHex(text)
                                        onAccepted: { if (text.length === 6) cc.applyHex(text); cc.hexEditing = false; focus = false }
                                        onActiveFocusChanged: if (!activeFocus) cc.hexEditing = false
                                    }
                                    // shows the current colour whenever you're not typing
                                    Binding { target: hexIn; property: "text"; value: cc.hexOf(cc.themeColor); when: !hexIn.activeFocus }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !hexIn.activeFocus
                                        cursorShape: Qt.IBeamCursor
                                        onClicked: { cc.hexEditing = true; hexTimer.restart() }
                                    }
                                    Timer {
                                        id: hexTimer
                                        interval: 90
                                        onTriggered: {
                                            if (hexBox.Window.window) hexBox.Window.window.requestActivate()
                                            hexIn.forceActiveFocus()
                                            hexIn.selectAll()
                                        }
                                    }
                                }
                            }

                            // hue slider
                            Item {
                                width: parent.width
                                height: 32
                                Rectangle {
                                    id: hueTrack
                                    width: parent.width
                                    height: 24
                                    radius: 12
                                    antialiasing: true
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0000; color: Qt.hsva(0.0000, 1, 1, 1) }
                                        GradientStop { position: 0.1667; color: Qt.hsva(0.1667, 1, 1, 1) }
                                        GradientStop { position: 0.3333; color: Qt.hsva(0.3333, 1, 1, 1) }
                                        GradientStop { position: 0.5000; color: Qt.hsva(0.5000, 1, 1, 1) }
                                        GradientStop { position: 0.6667; color: Qt.hsva(0.6667, 1, 1, 1) }
                                        GradientStop { position: 0.8333; color: Qt.hsva(0.8333, 1, 1, 1) }
                                        GradientStop { position: 1.0000; color: Qt.hsva(0.9999, 1, 1, 1) }
                                    }
                                }
                                Rectangle {
                                    width: 24
                                    height: 24
                                    radius: 12
                                    antialiasing: true
                                    x: cc.hsvH * (hueTrack.width - width)
                                    color: Qt.hsva(cc.hsvH, 1, 1, 1)
                                    border.width: 3
                                    border.color: "white"
                                    scale: hueMouse.pressed ? 1.2 : 1
                                    Behavior on scale { SpringAnimation { spring: 9.6; damping: 0.5; epsilon: 0.005 } }
                                }
                                MouseArea {
                                    id: hueMouse
                                    anchors.fill: hueTrack
                                    cursorShape: Qt.PointingHandCursor
                                    function setFrom(mx) {
                                        cc.hsvH = cc.clamp((mx - 12) / (width - 24), 0, 0.9999)
                                        cc.themeEdited()
                                    }
                                    onPressed: (m) => setFrom(m.x)
                                    onPositionChanged: (m) => { if (pressed) setFrom(m.x) }
                                }
                            }

                            // what the picker edits
                            Row {
                                width: parent.width
                                spacing: 6
                                CcButton {
                                    width: (parent.width - 12) / 3
                                    height: 30
                                    text: "Shell" + (cc.isCustom("shell") ? "  \u25CF" : ""); selected: cc.themeTarget === "shell"
                                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                                    onClicked: cc.selectTarget("shell")
                                }
                                CcButton {
                                    width: (parent.width - 12) / 3
                                    height: 30
                                    text: "Outline" + (cc.isCustom("outline") ? "  \u25CF" : ""); selected: cc.themeTarget === "outline"
                                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                                    onClicked: cc.selectTarget("outline")
                                }
                                CcButton {
                                    width: (parent.width - 12) / 3
                                    height: 30
                                    text: "Icons" + (cc.isCustom("icons") ? "  \u25CF" : ""); selected: cc.themeTarget === "icons"
                                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                                    onClicked: cc.selectTarget("icons")
                                }
                            }

                            // a dot on a chip means that part is your colour and ignores the wallpaper. this puts all three back
                            Item {
                                width: parent.width
                                height: cc.anyCustom ? 40 : 0
                                visible: height > 0.5
                                clip: true
                                Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                                CcButton {
                                    y: 8
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    height: 28
                                    flat: true
                                    text: "Follow wallpaper"
                                    pixelSize: 11
                                    accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                                    onClicked: cc.followWallpaper()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- Wi-Fi page ----
    Item {
        id: pgWifi
        readonly property bool on: cc.sub === "wifi"
        property real listH: CC.wifiOn ? Math.max(96, Math.min(wifiCol.height, 262)) : 110
        readonly property real h: 14 + 32 + 8 + 16 + 8 + listH + 8 + 34 + 14
        Behavior on listH { NumberAnimation { duration: 192; easing.type: Easing.OutCubic } }
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : 30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        CcHeader {
            x: 16; y: 14; width: 348
            opacity: cc.sst(0)
            transform: Translate { y: (1 - cc.back(cc.sst(0))) * 10 }
            title: "Wi-Fi"
            uiFont: cc.uiFont
            onBack: cc.sub = "main"
            CcButton { round: true; icon: "\uE72C"; visible: CC.wifiOn; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: CC.scanWifi() }
            CcSwitch { checked: CC.wifiOn; accent: cc.accent; onToggled: CC.setWifi(!CC.wifiOn) }
        }
        Text {
            renderType: Text.QtRendering
            x: 18; y: 14 + 32 + 8
            opacity: cc.sst(1)
            text: CC.wifiMissing ? "No Wi-Fi adapter found"
                : !CC.wifiOn ? "Wi-Fi is off"
                : CC.wifiScanning ? "Scanning..."
                : CC.wifiNote === "location" ? "Saved networks only (Location is off)"
                : CC.wifiNote === "error" ? "Couldn't read networks"
                : Math.max(0, wifiModel.count - 1) + " networks found"
            color: cc.muted
            font.family: cc.uiFont
            font.pixelSize: 11
        }
        CcButton {
            visible: CC.wifiOn && CC.wifiNote === "location"
            x: 364 - width
            y: 14 + 32 + 8 - 5
            height: 24
            opacity: cc.sst(1)
            flat: true
            text: "Turn on Location"
            pixelSize: 10
            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
            onClicked: CC.openLocationSettings()
        }

        Flickable {
            id: wifiFlick
            visible: CC.wifiOn
            x: 16; y: 14 + 32 + 8 + 16 + 8
            width: 348
            height: pgWifi.listH
            opacity: cc.sst(2)
            transform: Translate { y: (1 - cc.back(cc.sst(2))) * 14 }
            contentWidth: width
            contentHeight: wifiCol.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: wifiCol
                width: wifiFlick.width
                spacing: 6
                opacity: CC.wifiScanning && wifiModel.count > 1 ? 0.55 : 1
                Behavior on opacity { NumberAnimation { duration: 120 } }
                move: Transition { NumberAnimation { properties: "y"; duration: 156; easing.type: Easing.OutCubic } }
                Repeater {
                    model: wifiModel
                    CcRow {
                        id: wr
                        required property int index
                        required property string ssid
                        required property bool secure
                        required property bool ent
                        required property int bars
                        required property string link
                        required property string busyText
                        required property string noteText
                        readonly property bool isAdd: link === "add"
                        width: wifiCol.width
                        signalBars: isAdd ? -1 : bars
                        icon: isAdd ? "\uE710" : "\uE701"
                        title: isAdd ? "Add network" : ssid
                        sub: busyText !== "" ? busyText
                           : noteText !== "" ? noteText
                           : isAdd ? "Enter a name and password"
                           : ent ? "Set up in Windows settings"
                           : link === "connected" ? (secure ? "Connected, secured" : "Connected, open")
                           : link === "saved" ? (secure ? "Saved, secured" : "Saved") : (secure ? "Secured" : "Open")
                        warn: busyText === "" && noteText !== ""
                        connected: link === "connected"
                        lock: secure && !isAdd
                        busy: busyText !== ""
                        expanded: cc.wifiOpen === ssid
                        askName: isAdd
                        needsPassword: isAdd ? cc.secList[cc.addSec][1] !== "Open" : (link === "new" && secure && !ent)
                        secText: isAdd ? "Security: " + cc.secList[cc.addSec][0] : ""
                        actionText: isAdd ? "Connect" : ent ? "" : (link === "connected" ? "Disconnect" : "Connect")
                        accent: cc.accent; lavender: cc.lavender; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                        onToggled: cc.wifiOpen = (cc.wifiOpen === ssid ? "" : ssid)
                        onSecClicked: cc.addSec = (cc.addSec + 1) % 3
                        onActivated: (pw) => { if (isAdd) cc.wifiAddGo(typedName, pw); else cc.wifiAct(ssid, link, pw) }
                    }
                }
            }
            Text {
                renderType: Text.QtRendering
                visible: wifiModel.count === 0
                width: parent.width
                y: 30
                horizontalAlignment: Text.AlignHCenter
                text: "Looking for networks..."
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 12
            }
        }
        // off state
        Item {
            visible: !CC.wifiOn
            x: 16; y: 14 + 32 + 8 + 16 + 8
            width: 348
            height: 110
            opacity: cc.sst(2)
            Rectangle { anchors.fill: parent; radius: 22; color: cc.cardColor }
            Column {
                anchors.centerIn: parent
                spacing: 8
                Text { renderType: Text.QtRendering; anchors.horizontalCenter: parent.horizontalCenter; text: "\uE701"; font.family: "Segoe Fluent Icons"; font.pixelSize: 28; color: Qt.rgba(1, 1, 1, 0.3) }
                Text { renderType: Text.QtRendering; anchors.horizontalCenter: parent.horizontalCenter; text: CC.wifiMissing ? "No Wi-Fi adapter on this PC" : "Turn Wi-Fi on to see networks"; color: cc.muted; font.family: cc.uiFont; font.pixelSize: 12 }
            }
        }

        CcButton {
            x: 16; y: 14 + 32 + 8 + 16 + 8 + pgWifi.listH + 8
            width: 348
            opacity: cc.sst(3)
            text: "More Wi-Fi settings"; icon: "\uE713"
            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
            onClicked: { B.openUri("ms-settings:network-wifi"); cc.closeRequested() }
        }
    }

    // ---- Bluetooth page ----
    Item {
        id: pgBt
        readonly property bool on: cc.sub === "bt"
        property real listH: CC.btOn ? Math.max(96, Math.min(btCol.height, 262)) : 110
        readonly property real h: 14 + 32 + 8 + 16 + 8 + listH + 8 + 34 + 14
        Behavior on listH { NumberAnimation { duration: 192; easing.type: Easing.OutCubic } }
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : 30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        CcHeader {
            x: 16; y: 14; width: 348
            opacity: cc.sst(0)
            transform: Translate { y: (1 - cc.back(cc.sst(0))) * 10 }
            title: "Bluetooth"
            uiFont: cc.uiFont
            onBack: cc.sub = "main"
            CcButton { round: true; icon: "\uE72C"; visible: CC.btOn; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: CC.scanBt() }
            CcSwitch { checked: CC.btOn; accent: cc.accent; onToggled: CC.setBt(!CC.btOn) }
        }
        Text {
            renderType: Text.QtRendering
            x: 18; y: 14 + 32 + 8
            opacity: cc.sst(1)
            text: CC.btMissing ? "No Bluetooth adapter found"
                : !CC.btOn ? "Bluetooth is off"
                : (CC.btScanning && btModel.count === 0) ? "Looking for devices..."
                : btModel.count + (btModel.count === 1 ? " paired device" : " paired devices")
            color: cc.muted
            font.family: cc.uiFont
            font.pixelSize: 11
        }

        Flickable {
            id: btFlick
            visible: CC.btOn
            x: 16; y: 14 + 32 + 8 + 16 + 8
            width: 348
            height: pgBt.listH
            opacity: cc.sst(2)
            transform: Translate { y: (1 - cc.back(cc.sst(2))) * 14 }
            contentWidth: width
            contentHeight: btCol.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column {
                id: btCol
                width: btFlick.width
                spacing: 6
                move: Transition { NumberAnimation { properties: "y"; duration: 156; easing.type: Easing.OutCubic } }
                Repeater {
                    model: btModel
                    CcRow {
                        required property int index
                        required property string addr
                        required property string devName
                        required property string glyph
                        required property string link
                        required property string busyText
                        required property string noteText
                        width: btCol.width
                        icon: glyph
                        title: devName
                        sub: busyText !== "" ? busyText : noteText !== "" ? noteText : (link === "connected" ? "Connected" : "Paired")
                        warn: busyText === "" && noteText !== ""
                        connected: link === "connected"
                        busy: busyText !== ""
                        expanded: cc.btOpen === addr
                        actionText: link === "connected" ? "Disconnect" : "Connect"
                        accent: cc.accent; lavender: cc.lavender; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                        onToggled: cc.btOpen = (cc.btOpen === addr ? "" : addr)
                        onActivated: cc.btAct(addr, link)
                    }
                }
            }
            Text {
                renderType: Text.QtRendering
                visible: btModel.count === 0 && !CC.btScanning
                width: parent.width
                y: 30
                horizontalAlignment: Text.AlignHCenter
                text: "No paired devices"
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 12
            }
        }
        Item {
            visible: !CC.btOn
            x: 16; y: 14 + 32 + 8 + 16 + 8
            width: 348
            height: 110
            opacity: cc.sst(2)
            Rectangle { anchors.fill: parent; radius: 22; color: cc.cardColor }
            Column {
                anchors.centerIn: parent
                spacing: 8
                Text { renderType: Text.QtRendering; anchors.horizontalCenter: parent.horizontalCenter; text: "\uE702"; font.family: "Segoe Fluent Icons"; font.pixelSize: 28; color: Qt.rgba(1, 1, 1, 0.3) }
                Text { renderType: Text.QtRendering; anchors.horizontalCenter: parent.horizontalCenter; text: CC.btMissing ? "No Bluetooth adapter on this PC" : "Turn Bluetooth on to see devices"; color: cc.muted; font.family: cc.uiFont; font.pixelSize: 12 }
            }
        }

        CcButton {
            x: 16; y: 14 + 32 + 8 + 16 + 8 + pgBt.listH + 8
            width: 348
            opacity: cc.sst(3)
            text: "More Bluetooth settings"; icon: "\uE713"
            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
            onClicked: { B.openUri("ms-settings:bluetooth"); cc.closeRequested() }
        }
    }

    // ---- volume mixer page ----
    Item {
        id: pgMixer
        readonly property bool on: cc.sub === "mixer"
        readonly property real h: mixCol.implicitHeight + 14 + 16
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : 30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        Column {
            id: mixCol
            x: 16
            y: 14
            width: 348
            spacing: 8

            CcHeader {
                width: parent.width
                opacity: cc.sst(0)
                transform: Translate { y: (1 - cc.back(cc.sst(0))) * 10 }
                title: "Volume mixer"
                uiFont: cc.uiFont
                onBack: cc.sub = "main"
                CcButton { round: true; icon: "\uE72C"; accent: cc.accent; hoverColor: cc.hoverColor; onClicked: CC.refreshApps() }
            }
            Text {
                renderType: Text.QtRendering
                x: 2
                opacity: cc.sst(1)
                text: "Every app that makes sound, each with its own volume"
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 11
            }

            // output devices (from the bar's backend): click one to make it the default playback device
            Column {
                width: parent.width
                spacing: 6
                visible: B.outputs.length > 0
                opacity: cc.sst(2)
                transform: Translate { y: (1 - cc.back(cc.sst(2))) * 12 }
                Text {
                    renderType: Text.QtRendering
                    x: 2
                    text: "OUTPUT"
                    color: cc.muted
                    font.family: cc.uiFont
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.2
                }
                Flow {
                    width: parent.width
                    spacing: 6
                    Repeater {
                        model: B.outputs
                        CcButton {
                            required property var modelData
                            height: 30
                            icon: modelData.kind === "headphones" ? "\uE7F6" : "\uE767"
                            text: modelData.label
                            pixelSize: 11
                            selected: modelData.key === B.defaultOutput
                            accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                            onClicked: B.setOutput(modelData.id)
                        }
                    }
                }
            }

            Text {
                renderType: Text.QtRendering
                x: 2
                opacity: cc.sst(3)
                text: "APPS"
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 1.2
            }
            Rectangle {
                width: parent.width
                height: appModel.count > 0 ? Math.min(appCol.height, 5 * 52 + 4 * 4) + 20 : 84
                radius: 22
                antialiasing: true
                color: cc.cardColor
                opacity: cc.sst(3)
                transform: Translate { y: (1 - cc.back(cc.sst(3))) * 14 }
                Behavior on height { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                Text {
                    renderType: Text.QtRendering
                    visible: appModel.count === 0
                    anchors.centerIn: parent
                    width: parent.width - 40
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: CC.appsState === "error" ? "Couldn't read app volumes (see the log)"
                        : CC.appsState === "empty" ? "No app has played sound yet.\nStart a video or some music and it shows up here."
                        : "Looking for apps..."
                    color: cc.muted
                    font.family: cc.uiFont
                    font.pixelSize: 11
                }
                Flickable {
                    x: 14; y: 10
                    width: parent.width - 28
                    height: parent.height - 20
                    contentWidth: width
                    contentHeight: appCol.height
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: appCol
                        width: parent.width
                        spacing: 4
                        move: Transition { NumberAnimation { properties: "y"; duration: 144; easing.type: Easing.OutCubic } }
                        Repeater {
                            model: appModel
                            Item {
                                id: ar
                                required property int index
                                required property string appKey
                                required property string appName
                                required property real level
                                required property bool mute
                                required property bool playing
                                required property string iconUrl
                                width: appCol.width
                                height: 52
                                Text {
                                    renderType: Text.QtRendering
                                    x: 2
                                    width: parent.width - 90
                                    text: ar.appName
                                    elide: Text.ElideRight
                                    color: ar.playing ? "white" : Qt.rgba(1, 1, 1, 0.55)
                                    font.family: cc.uiFont
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    renderType: Text.QtRendering
                                    anchors.right: parent.right
                                    anchors.rightMargin: 2
                                    visible: ar.playing
                                    text: "\u25CF  playing"
                                    color: cc.accent
                                    font.family: cc.uiFont
                                    font.pixelSize: 10
                                }
                                CcSlider {
                                    y: 14
                                    width: parent.width
                                    icon: ar.appName.charAt(0).toUpperCase()
                                    iconSource: ar.iconUrl
                                    iconFont: cc.uiFont
                                    value: ar.level
                                    muted: ar.mute
                                    iconClickable: true
                                    accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                                    onMoved: (v) => { appModel.setProperty(ar.index, "level", v); cc.touchApp(ar.appKey); CC.setAppVolume(ar.appKey, v) }
                                    onIconClicked: { appModel.setProperty(ar.index, "mute", !ar.mute); cc.touchApp(ar.appKey); CC.setAppMute(ar.appKey, !ar.mute) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- system stats page ----
    Item {
        id: pgStats
        readonly property bool on: cc.sub === "stats"
        readonly property real h: statCol.implicitHeight + 14 + 16
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : 30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        Column {
            id: statCol
            x: 16
            y: 14
            width: 348
            spacing: 8

            CcHeader {
                width: parent.width
                opacity: cc.sst(0)
                transform: Translate { y: (1 - cc.back(cc.sst(0))) * 10 }
                title: "System stats"
                uiFont: cc.uiFont
                onBack: cc.sub = "main"
            }

            Grid {
                columns: 2
                spacing: 8
                readonly property real cw: (348 - 8) / 2
                CcStat {
                    width: parent.cw
                    opacity: cc.sst(1); scale: 0.88 + 0.12 * cc.back(cc.sst(1))
                    name: "CPU"; value: Math.round(cc.cpuNow * 100) + "%"
                    detail: "Processor load"
                    hist: cc.cpuH
                    accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                }
                CcStat {
                    width: parent.cw
                    opacity: cc.sst(2); scale: 0.88 + 0.12 * cc.back(cc.sst(2))
                    name: "Memory"; value: Math.round(cc.memNow * 100) + "%"
                    detail: cc.gb(CC.memUsed) + " of " + cc.gb(CC.memTotal) + " GB in use"
                    hist: cc.memH
                    accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                }
                CcStat {
                    visible: CC.gpu !== undefined && CC.gpu.name !== undefined
                    width: parent.cw
                    opacity: cc.sst(3); scale: 0.88 + 0.12 * cc.back(cc.sst(3))
                    name: "GPU"; value: Math.round(cc.gpuNow * 100) + "%"
                    detail: (CC.gpu && CC.gpu.name ? CC.gpu.name : "")
                            + (CC.gpu && CC.gpu.mem_used !== undefined && CC.gpu.mem_used !== null && CC.gpu.mem_total ? "  \u00B7  " + (CC.gpu.mem_used / 1024).toFixed(1) + "/" + (CC.gpu.mem_total / 1024).toFixed(1) + " GB" : "")
                            + (CC.gpu && CC.gpu.temp !== undefined && CC.gpu.temp !== null ? "  \u00B7  " + Math.round(CC.gpu.temp) + "\u00B0C" : "")
                    hist: cc.gpuH
                    accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                }
                CcStat {
                    width: parent.cw
                    opacity: cc.sst(4); scale: 0.88 + 0.12 * cc.back(cc.sst(4))
                    name: "Network"; value: "\u2193 " + cc.fmtRate(CC.netRx)
                    detail: "\u2191 " + cc.fmtRate(CC.netTx)
                    hist: cc.netH
                    accent: cc.accent; lavender: cc.lavender; uiFont: cc.uiFont
                }
            }

            Rectangle {
                width: parent.width
                height: diskCol.implicitHeight + 26
                radius: 22
                antialiasing: true
                color: cc.cardColor
                opacity: cc.sst(5)
                transform: Translate { y: (1 - cc.back(cc.sst(5))) * 14 }
                Column {
                    id: diskCol
                    x: 14
                    y: 12
                    width: parent.width - 28
                    spacing: 10
                    Text {
                        renderType: Text.QtRendering
                        text: "DISKS"
                        color: cc.muted
                        font.family: cc.uiFont
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.2
                    }
                    Repeater {
                        model: CC.disks || []
                        Item {
                            required property var modelData
                            width: diskCol.width
                            height: 30
                            Text {
                                renderType: Text.QtRendering
                                text: modelData.letter + ":"
                                color: "white"
                                font.family: cc.uiFont
                                font.pixelSize: 12
                                font.weight: Font.Bold
                            }
                            Text {
                                renderType: Text.QtRendering
                                anchors.right: parent.right
                                text: Math.round(modelData.used / 1073741824) + " GB of " + Math.round(modelData.total / 1073741824) + " GB"
                                color: cc.muted
                                font.family: cc.uiFont
                                font.pixelSize: 10
                            }
                            Rectangle { y: 20; width: parent.width; height: 6; radius: 3; color: Qt.rgba(1, 1, 1, 0.12) }
                            Rectangle {
                                y: 20
                                width: Math.max(6, parent.width * (modelData.total > 0 ? modelData.used / modelData.total : 0) * cc.sst(5))
                                height: 6
                                radius: 3
                                antialiasing: true
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: (modelData.used / modelData.total) > 0.9 ? "#ff6b7a" : cc.accent }
                                    GradientStop { position: 1; color: (modelData.used / modelData.total) > 0.9 ? "#ff6b7a" : cc.lavender }
                                }
                            }
                        }
                    }
                }
            }
            Text {
                renderType: Text.QtRendering
                x: 2
                visible: CC.uptime !== ""
                opacity: cc.sst(5)
                text: "Uptime " + CC.uptime
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 10
            }
        }
    }

    // ---- clear cache page: scan -> confirm -> live log, all inside the panel, no dialogs ----
    Item {
        id: pgClean
        readonly property bool on: cc.sub === "clean"
        readonly property string st: CC.cleanState
        readonly property bool showLog: st === "running" || st === "done"
        readonly property real bodyH: st === "ready" ? readyCard.height : (showLog ? 240 : 96)
        readonly property real h: 14 + 32 + 10 + bodyH + 10 + 36 + 14
        width: 380
        height: h
        opacity: on ? 1 : 0
        visible: opacity > 0.01
        x: on ? 0 : 30
        Behavior on opacity { NumberAnimation { duration: 144 } }
        Behavior on x { NumberAnimation { duration: 252; easing.type: Easing.OutQuart } }

        CcHeader {
            x: 16; y: 14; width: 348
            opacity: cc.sst(0)
            transform: Translate { y: (1 - cc.back(cc.sst(0))) * 10 }
            title: "Clear cache"
            uiFont: cc.uiFont
            onBack: cc.sub = "main"
        }

        // scanning / nothing to do
        Rectangle {
            visible: !pgClean.showLog && pgClean.st !== "ready"
            x: 16; y: 56; width: 348; height: 96
            radius: 22
            antialiasing: true
            color: cc.cardColor
            opacity: cc.sst(1)
            Text {
                renderType: Text.QtRendering
                anchors.centerIn: parent
                text: pgClean.st === "empty" ? "Nothing to clean up." : "Scanning..."
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 12
            }
        }

        // confirm
        Rectangle {
            id: readyCard
            visible: pgClean.st === "ready"
            x: 16; y: 56; width: 348
            height: readyCol.implicitHeight + 28
            radius: 22
            antialiasing: true
            color: cc.cardColor
            opacity: cc.sst(1)
            transform: Translate { y: (1 - cc.back(cc.sst(1))) * 14 }
            Column {
                id: readyCol
                x: 14
                y: 14
                width: parent.width - 28
                spacing: 8
                Text {
                    renderType: Text.QtRendering
                    text: "Delete " + CC.cleanCount + " items (" + CC.cleanSize + ")?"
                    color: "white"
                    font.family: cc.uiFont
                    font.pixelSize: 14
                    font.weight: Font.Bold
                }
                Text {
                    renderType: Text.QtRendering
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Clears the Vapor, Harmony, Synapse, system and temp file caches. Your theme, settings and favourites are not touched. Restart Vapor and Harmony afterwards so they rebuild their icons and thumbnails."
                    color: cc.muted
                    font.family: cc.uiFont
                    font.pixelSize: 10
                }
                Text {
                    renderType: Text.QtRendering
                    text: "LARGEST"
                    color: cc.muted
                    font.family: cc.uiFont
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.2
                }
                Repeater {
                    model: CC.cleanPreview || []
                    Text {
                        renderType: Text.QtRendering
                        required property string modelData
                        width: readyCol.width
                        text: modelData
                        elide: Text.ElideMiddle
                        color: Qt.rgba(1, 1, 1, 0.7)
                        font.family: "CaskaydiaCove NFM"
                        font.pixelSize: 9
                    }
                }
            }
        }

        // live log
        Rectangle {
            visible: pgClean.showLog
            x: 16; y: 56; width: 348; height: 240
            radius: 22
            antialiasing: true
            color: Qt.rgba(0, 0, 0, 0.28)
            Flickable {
                id: logFlick
                x: 14; y: 10
                width: parent.width - 28
                height: parent.height - 20
                contentWidth: width
                contentHeight: logCol.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: logCol
                    width: logFlick.width
                    spacing: 2
                    Repeater {
                        model: logModel
                        Text {
                            renderType: Text.QtRendering
                            required property string kind
                            required property string line
                            width: logCol.width
                            text: line
                            elide: Text.ElideMiddle
                            color: kind === "ok" ? "#7ee2a0" : kind === "skip" ? "#e8b062" : kind === "done" ? "white" : "#9aa0a6"
                            font.family: "CaskaydiaCove NFM"
                            font.pixelSize: 9
                            font.weight: kind === "done" ? Font.Bold : Font.Normal
                        }
                    }
                }
            }
            Connections {
                target: logModel
                function onCountChanged() { Qt.callLater(function() { logFlick.contentY = Math.max(0, logFlick.contentHeight - logFlick.height) }) }
            }
        }

        // bottom row
        Item {
            x: 16; y: 56 + pgClean.bodyH + 10
            width: 348
            height: 36
            opacity: cc.sst(3)
            Row {
                visible: pgClean.st === "ready"
                spacing: 8
                CcButton { width: 170; text: "Cancel"; accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont; onClicked: cc.sub = "main" }
                CcButton { width: 170; text: "Delete"; icon: "\uE74D"; primary: true; accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont; onClicked: CC.cleanRun() }
            }
            Text {
                renderType: Text.QtRendering
                visible: pgClean.st === "running"
                anchors.verticalCenter: parent.verticalCenter
                x: 4
                text: "Cleaning..."
                color: cc.muted
                font.family: cc.uiFont
                font.pixelSize: 12
            }
            CcButton {
                visible: pgClean.st === "done" || pgClean.st === "empty"
                width: 348
                text: pgClean.st === "done" ? (CC.cleanSummary + "  -  Close") : "Back"
                primary: true
                accent: cc.accent; hoverColor: cc.hoverColor; uiFont: cc.uiFont
                onClicked: cc.sub = "main"
            }
        }
    }
}
