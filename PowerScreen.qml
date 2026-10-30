import QtQuick
import QtQuick.Window

// Full-screen power menu for the Fluid Bar.
// FluidBar.qml creates one of these (id: powerScreen) and calls powerScreen.open() when the control center's power
// button is pressed. It covers the whole screen with the bar's glass colour, keeps the rounded glass frame outline,
// and the five actions rise in one after another on the same ease-out-back spring feel as the control center.
//   Esc / click on the empty glass / X button  -> cancel        1-5  -> pick an action
Window {
    id: ps
    title: "Fluid Bar Power"
    // OPAQUE window with FAKE transparency: B.grabScreen() takes a screenshot of the desktop just before the window
    // appears, and that picture is the backdrop. At t = 0 the window looks exactly like the desktop (nothing seems to
    // happen), then the blur and the glass tint fade in over it, and on close they fade back out to the same picture.
    // So it looks see-through, fades smoothly and never flashes black, but dwm.exe only has a plain opaque window.
    color: Qt.rgba(B.glassColor.r, B.glassColor.g, B.glassColor.b, 1)
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    x: B.screenX
    y: B.screenY
    width: B.screenW
    height: B.fullH
    visible: shown

    property bool shown: false           // the window exists while this is true (it stays true until the fade-out ends)
    signal finished()                    // fade-out done: FluidBar then unloads this window completely (frees its memory)
    property real t: 0                   // 0..1 opening progress; everything below is driven from it
    property bool wasActive: false
    property string bgUrl: ""            // the desktop screenshot ("" = grab failed: plain glass colour)
    readonly property string bgBlurUrl: bgUrl === "" ? "" : bgUrl.replace(/\.bmp$/, "_blur.png")
    property date now: new Date()

    readonly property color accent: B.themeAccent
    readonly property color lavender: B.themeLavender
    readonly property color hoverColor: B.themeHover
    readonly property color glass: B.glassColor
    readonly property string uiFont: "CaskaydiaCove NFP"
    readonly property real k: Math.max(0.55, Math.min(1, (width - 80) / 830))   // shrink the tile row on small screens

    function back(p) { var c1 = 1.5, c3 = c1 + 1, u = p - 1; return 1 + c3 * u * u * u + c1 * u * u }
    function st(i) { return Math.max(0, Math.min(1, (t - i * 0.07) / 0.5)) }

    function open() {
        closeAnim.stop()
        now = new Date()
        if (typeof CC.refreshUptime === "function") CC.refreshUptime()
        wasActive = false
        bgUrl = B.grabScreen()           // BEFORE the window becomes visible, or it would photograph itself
        shown = true
        t = 0
        openAnim.restart()
        focusTimer.restart()
    }
    function close() {
        if (!shown) return
        openAnim.stop()
        closeAnim.restart()
    }
    function act(kind) {
        if (typeof CC.power === "function") CC.power(kind)
        close()
    }

    NumberAnimation { id: openAnim; target: ps; property: "t"; from: 0; to: 1; duration: 460; easing.type: Easing.Linear }
    NumberAnimation { id: closeAnim; target: ps; property: "t"; to: 0; duration: 170; easing.type: Easing.OutCubic; onFinished: { ps.shown = false; ps.finished() } }
    Timer {
        id: focusTimer
        interval: 60
        onTriggered: { ps.requestActivate(); keys.forceActiveFocus() }
    }
    Timer { interval: 1000; repeat: true; running: ps.shown; onTriggered: ps.now = new Date() }
    Timer { id: fitTimer; interval: 40; onTriggered: B.fitFullscreen(ps.title) }       // exact monitor size in device pixels
    onVisibleChanged: if (visible) fitTimer.restart()
    onActiveChanged: {
        if (active) wasActive = true
        else if (wasActive && shown && t > 0.9) close()        // clicked / alt-tabbed away
    }

    // ---- pieces ----------------------------------------------------------------------------------------------
    component PowerGlyph: Canvas {
        id: g
        property string kind: "shutdown"
        property color ink: "#d2bcff"
        property real k: 1.6
        width: 40 * k
        height: 40 * k
        onKindChanged: requestPaint()
        onInkChanged: requestPaint()
        onKChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            c.scale(k, k)
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

    component PowerTile: Item {
        id: pt
        property string kind: ""
        property string label: ""
        property string hint: ""
        property bool danger: false
        property real prog: 1                       // 0..1 entrance
        property color accent: "#4cbcff"
        property color lavender: "#d2bcff"
        property color hoverColor: Qt.rgba(1, 1, 1, 0.1)
        property string uiFont: "CaskaydiaCove NFP"
        signal clicked()

        function back(p) { var c1 = 1.5, c3 = c1 + 1, u = p - 1; return 1 + c3 * u * u * u + c1 * u * u }

        width: 150
        height: 176
        opacity: prog
        transform: Translate { y: (1 - pt.back(pt.prog)) * 46 }

        Item {
            anchors.fill: parent
            scale: (0.86 + 0.14 * pt.back(pt.prog)) * (pm.pressed ? 0.95 : (pm.containsMouse ? 1.06 : 1))
            Behavior on scale { SpringAnimation { spring: 14; damping: 0.55; epsilon: 0.002 } }

            Rectangle { anchors.fill: parent; radius: 38; color: Qt.rgba(1, 1, 1, 0.07) }
            Rectangle {
                anchors.fill: parent
                radius: 38
                color: pt.danger ? Qt.rgba(1, 0.42, 0.48, 0.22) : pt.hoverColor
                border.width: 1
                border.color: pt.danger ? Qt.rgba(1, 0.42, 0.48, 0.55) : Qt.rgba(pt.accent.r, pt.accent.g, pt.accent.b, 0.55)
                opacity: pm.containsMouse ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 90 } }
            }
            PowerGlyph {
                x: (parent.width - width) / 2
                y: 30
                k: 1.7
                kind: pt.kind
                ink: pt.danger ? "#ff6b7a" : pt.lavender
            }
            Text {
                width: parent.width
                y: 118
                horizontalAlignment: Text.AlignHCenter
                text: pt.label
                color: pt.danger ? "#ff6b7a" : "white"
                font.family: pt.uiFont
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                y: 142
                horizontalAlignment: Text.AlignHCenter
                text: pt.hint
                color: Qt.rgba(1, 1, 1, 0.38)
                font.family: pt.uiFont
                font.pixelSize: 11
            }
        }
        MouseArea {
            id: pm
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: pt.clicked()
        }
    }

    // ---- the screen -------------------------------------------------------------------------------------------
    Item {
        id: root
        anchors.fill: parent

        // glass scrim: the bar's own glass colour, a touch more transparent, with a faint accent wash from the top
        Image {                                                    // the desktop, sharp: identical to what was there
            anchors.fill: parent
            source: ps.bgUrl
            fillMode: Image.Stretch
            cache: false
            visible: ps.bgUrl !== ""
        }
        Image {                                                    // the same picture, blurred (small file, smooth scaling)
            anchors.fill: parent
            source: ps.bgBlurUrl
            fillMode: Image.Stretch
            smooth: true
            cache: false
            opacity: Math.min(1, ps.t * 2.2)
            visible: ps.bgUrl !== ""
        }
        Rectangle {                                                // the bar's glass colour over it
            anchors.fill: parent
            color: Qt.rgba(ps.glass.r, ps.glass.g, ps.glass.b, 1)
            opacity: ps.bgUrl === "" ? 1 : Math.min(1, ps.t * 2.4) * 0.78
        }
        Rectangle {
            anchors.fill: parent
            opacity: Math.min(1, ps.t * 2.2)
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(ps.accent.r, ps.accent.g, ps.accent.b, 0.13) }
                GradientStop { position: 0.55; color: Qt.rgba(ps.accent.r, ps.accent.g, ps.accent.b, 0.0) }
                GradientStop { position: 1.0; color: Qt.rgba(ps.lavender.r, ps.lavender.g, ps.lavender.b, 0.07) }
            }
        }
        // the same rounded glass frame outline the bar draws around the screen
        Rectangle {
            x: 8; y: 8
            width: parent.width - 16
            height: parent.height - 16
            radius: 18
            color: "transparent"
            border.width: 1
            border.color: B.glassOutline
            opacity: Math.min(1, ps.t * 2)
        }

        // empty glass cancels
        MouseArea { anchors.fill: parent; onClicked: ps.close() }

        Item {
            id: keys
            focus: true
            Keys.onPressed: (e) => {
                if (e.key === Qt.Key_Escape) { ps.close(); e.accepted = true }
                else if (e.key >= Qt.Key_1 && e.key <= Qt.Key_5) { ps.act(tiles.kinds[e.key - Qt.Key_1]); e.accepted = true }
            }
        }

        // clock + date
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            y: Math.max(48, parent.height * 0.17)
            spacing: 4
            opacity: ps.st(0)
            transform: Translate { y: (1 - ps.back(ps.st(0))) * 30 }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                textFormat: Text.RichText
                // 12-hour clock, with a smaller AM / PM next to it
                text: Qt.formatDateTime(ps.now, "hh:mm AP").replace(" ", " <span style='font-size:" + Math.round(34 * ps.k) + "px'>") + "</span>"
                color: "white"
                font.family: ps.uiFont
                font.pixelSize: Math.round(96 * ps.k)
                font.weight: Font.Light
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatDateTime(ps.now, "dddd, d MMMM")
                color: Qt.rgba(1, 1, 1, 0.6)
                font.family: ps.uiFont
                font.pixelSize: 18
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: CC.uptime !== ""
                text: "Uptime  " + CC.uptime
                color: Qt.rgba(1, 1, 1, 0.42)
                font.family: ps.uiFont
                font.pixelSize: 14
            }
        }

        // the five actions
        Item {
            id: tiles
            readonly property var kinds: ["shutdown", "restart", "sleep", "hibernate", "signout"]
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.5 - 20
            width: 5 * 150 + 4 * 18
            height: 176
            scale: ps.k
            Row {
                spacing: 18
                PowerTile { prog: ps.st(1); kind: "shutdown";  label: "Shut down"; accent: ps.accent; lavender: ps.lavender; hoverColor: ps.hoverColor; uiFont: ps.uiFont; onClicked: ps.act("shutdown") }
                PowerTile { prog: ps.st(2); kind: "restart";   label: "Restart";   accent: ps.accent; lavender: ps.lavender; hoverColor: ps.hoverColor; uiFont: ps.uiFont; onClicked: ps.act("restart") }
                PowerTile { prog: ps.st(3); kind: "sleep";     label: "Sleep";     accent: ps.accent; lavender: ps.lavender; hoverColor: ps.hoverColor; uiFont: ps.uiFont; onClicked: ps.act("sleep") }
                PowerTile { prog: ps.st(4); kind: "hibernate"; label: "Hibernate"; accent: ps.accent; lavender: ps.lavender; hoverColor: ps.hoverColor; uiFont: ps.uiFont; onClicked: ps.act("hibernate") }
                PowerTile { prog: ps.st(5); kind: "signout";   label: "Sign out";  accent: ps.accent; lavender: ps.lavender; hoverColor: ps.hoverColor; uiFont: ps.uiFont; onClicked: ps.act("signout") }
            }
        }

        // cancel
        Item {
            id: cancelBtn
            anchors.horizontalCenter: parent.horizontalCenter
            y: tiles.y + tiles.height * ps.k + 54
            width: 150
            height: 46
            opacity: ps.st(6)
            transform: Translate { y: (1 - ps.back(ps.st(6))) * 24 }
            scale: cancelMouse.pressed ? 0.95 : (cancelMouse.containsMouse ? 1.05 : 1)
            Behavior on scale { SpringAnimation { spring: 14; damping: 0.55; epsilon: 0.002 } }
            Rectangle { anchors.fill: parent; radius: 23; color: Qt.rgba(1, 0.42, 0.48, cancelMouse.containsMouse ? 0.3 : 0.18); border.width: 1; border.color: Qt.rgba(1, 0.42, 0.48, 0.55); Behavior on color { ColorAnimation { duration: 90 } } }
            Text {
                anchors.centerIn: parent
                text: "Cancel   Esc"
                color: "#ff6b7a"
                font.family: ps.uiFont
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
            MouseArea { id: cancelMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: ps.close() }
        }
    }
}
