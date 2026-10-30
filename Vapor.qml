import QtQuick
import QtQuick.Window

// Vapor: a Caelestia-style shell. a bar across the top plus a thin glass frame around the other three screen
// edges, with the popups growing out of the bar. everything dynamic comes from the Python backend `B`,
// taskModel is the app list. it's all one screen-sized window, the glass is a single shape (see Glass.qml)
// and the backend clips the window to that shape, so the empty middle of the screen is click-through.
Window {
    id: bar

    // hidden (Alt+W or a fullscreen app): once the frame has retracted the window really gets hidden
    visible: shown
    title: "Vapor"
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    x: B.screenX
    y: B.screenY
    width: B.screenW
    height: B.screenH

    // ---- theme ----
    // the accent / icon colours come from the backend (wallpaper, plus whatever the control center's theme card overrides)
    property color accent: B.themeAccent
    property color blue: B.themeBlue
    property color lavender: B.themeLavender
    property color hoverColor: B.themeHover
    // glass colours fade over about as long as Harmony's wallpaper transition (0.8 - 1.2 s) and start the moment it does
    readonly property int colorMs: 900
    property color glassFill: B.glassColor
    property color glassLine: B.glassOutline
    Behavior on accent { ColorAnimation { duration: bar.colorMs } }
    Behavior on blue { ColorAnimation { duration: bar.colorMs } }
    Behavior on lavender { ColorAnimation { duration: bar.colorMs } }
    Behavior on hoverColor { ColorAnimation { duration: bar.colorMs } }
    Behavior on glassFill { ColorAnimation { duration: bar.colorMs } }
    Behavior on glassLine { ColorAnimation { duration: bar.colorMs } }
    readonly property color muted: Qt.rgba(1, 1, 1, 0.55)
    // CaskaydiaCove NFP if it's installed, otherwise Consolas (also monospaced, ships with Windows)
    readonly property string uiFont: (typeof Qt.fontFamilies === "function" && Qt.fontFamilies().indexOf("CaskaydiaCove NFP") < 0) ? "Consolas" : "CaskaydiaCove NFP"

    // ---- geometry ----
    readonly property int barH: 36            // the bar along the top (keep in sync with PILL_H in vapor.pyw)
    readonly property int hitPad: (barH - 28) / 2   // bar widgets are 28 px tall inside the bar, this is the dead strip above / below them that now counts as part of the widget
    readonly property int frameW: 8           // thickness of the glass border down the sides and along the bottom
    readonly property int frameR: 18          // radius of the rounded inner corners
    readonly property int flare: 14           // concave joins between the bar and a popup
    readonly property real popSpeed: 1      // popup animation speed: 1 = original, 1.5 = 1.5x slower, 2 = twice as slow
    readonly property int hideMs: 200         // Alt+W: frame retracts
    readonly property int showMs: 320         // Alt+W / startup: frame slides back in

    // ---- popup motion: Material 3 expressive curves, same as Caelestia (no springs, so no wobble or long tail) ----
    readonly property var curveSpatial: [0.38, 1.21, 0.22, 1.0, 1, 1]      // opening / growing: fast out, with one barely visible settle (~1.4 %)
    readonly property var curveEmphasized: [0.05, 0.7, 0.1, 1.0, 1, 1]     // sliding between chips, morphing: smooth, no overshoot
    readonly property var curveStandard: [0.2, 0.0, 0.0, 1.0, 1, 1]        // content fades
    readonly property var curveExit: [0.3, 0.0, 0.8, 0.15, 1, 1]           // closing: eases away, then gets pulled into the bar

    // ---- reveal: 1 = frame fully out, 0 = fully retracted (everything below follows it) ----
    property bool ready: false
    readonly property bool slideOut: B.userHidden || B.fullscreen
    property real reveal: (ready && !slideOut) ? 1 : 0
    Behavior on reveal {
        NumberAnimation { duration: bar.slideOut ? bar.hideMs : bar.showMs; easing.type: Easing.OutCubic }
    }
    readonly property bool shown: !(ready && slideOut && reveal <= 0.01)
    readonly property real barNow: barH * reveal
    readonly property real frameNow: frameW * reveal
    readonly property real holeR: frameR * reveal
    readonly property real bottomExtra: B.stripMode ? 80 : 0     // strip mode: the hole runs past the window bottom so no bottom frame / corners show

    // ---- state ----
    property date now: new Date()
    property string page: ""                 // "", media, volume, clock, tray, control
    property string lastPage: "media"
    // set while the power menu grabs its desktop backdrop, the popup then retracts at once instead of springing shut
    property bool snapClose: false
    // true while the full-screen power menu is up. the control center stays open underneath and only retracts
    // after the power menu closes (Cancel / Esc / click away)
    property bool powerHold: false
    property real anchorX: width / 2
    readonly property bool open: page !== ""
    property int fg: B.fgSerial
    // after a click on a tray icon its app comes to the front (menu / window), which used to close the popup right away.
    // trayHold keeps the tray popup open for a bit after such a click, coming back with the mouse releases it.
    property bool trayHold: false
    // true from the moment a mouse button goes down on a tray icon (bar or popup) until it is released, so the popup can't
    // close during the first pixels of a press / drag, before trayDragging is even set. trayBusy = pressed or dragging.
    property bool trayPressed: false
    readonly property bool trayBusy: trayDragging || trayPressed
    Timer { interval: 60000; running: bar.trayPressed; onTriggered: { bar.trayPressed = false; bar.trayDragging = false; closeDelay.restart() } }     // safety net if a release never arrives
    // the chip the mouse is on right now ("" = none). HitPad reports "left chip A" 45 ms AFTER "entered chip B", so a
    // plain close timer used to be restarted by the stale "left" and closed the popup while the mouse sat on chip B.
    property string hoverChip: ""
    property Item hoverChipItem: null
    function holdTray() { trayHold = true; trayHoldTimer.restart() }
    Timer { id: trayHoldTimer; interval: 10000; onTriggered: { bar.trayHold = false; closeDelay.restart() } }
    onFgChanged: if (open && !powerHold && !(page === "tray" && (trayHold || trayBusy))) page = ""
    onSlideOutChanged: if (slideOut) page = ""
    Connections {
        target: B
        function onFullscreenChanged() { if (B.fullscreen) bar.page = "" }
        function onOutsideClick() {
            if (bar.page === "control" && !bar.powerHold) bar.page = ""     // clicked outside the control center
            bar.sideOutside()                                                // ...and outside the side panel while a note is being edited
        }
    }
    onPageChanged: { if (page !== "clock") { clockTyping = false; clockPage.cancelEdit() } else clockPage.resetToNow(); if (page === "control") sideWant = false; if (page !== "") lastPage = page; if (page !== "tray") { trayHold = false; trayHoldTimer.stop() } B.setControlOpen(page === "control") }
    onRevealChanged: syncClip()
    // the click region used to be re-sent to Windows on every animation frame while a popup grew or moved (60 SetWindowRgn
    // calls a second), which makes dwm.exe rebuild the window over and over. now it follows the popup's target box,
    // so it only changes when a popup opens, closes or changes page.
    onWantHChanged: { if (wantH > 0) { clipH = wantH; syncClip(); fitPopup() } animateH() }
    onWantWChanged: { syncClip(); fitPopup() }
    onWantCXChanged: { syncClip(); fitPopup() }
    onPanelActiveChanged: { syncClip(); if (panelActive) fitPopup() }
    property real clipH: 0

    // ---- dragging tray icons: tray popup -> bar (pin), along the bar (reorder), off the bar (unpin) ----
    // the pointer position is kept in this window's coordinates even while the popup window has the mouse
    property bool trayDragging: false
    property bool trayDragFromBar: false
    property string trayDragKey: ""
    property string trayDragIcon: ""
    property real trayDragX: 0
    property real trayDragY: 0
    property int trayDropIndex: 0
    property real trayDropX: 0
    property bool trayDragWasPinned: false
    readonly property bool trayOverBar: trayDragging && trayDragY < barH + 8
    function beginTrayDrag(key, icon, fromBar, wasPinned) {
        trayDragWasPinned = wasPinned === true
        trayDragKey = key
        trayDragIcon = icon
        trayDragFromBar = fromBar
        trayDragging = true
    }
    function moveTrayDrag(gx, gy) {
        trayDragX = gx
        trayDragY = gy
        var left = trayRow.mapToItem(null, 0, 0).x
        var n = B.trayPinnedCount
        var rel = (gx - left) / 28
        // from the popup: the gap between two pinned icons. from the bar: the slot the icon will take
        var idx = trayDragFromBar ? Math.floor(rel) : Math.round(rel)
        idx = Math.max(0, Math.min(trayDragFromBar ? n - 1 : n, idx))
        trayDropIndex = idx
        trayDropX = left + idx * 28
    }
    function endTrayDrag() {
        if (!trayDragging) return
        var key = trayDragKey, idx = trayDropIndex, over = trayOverBar, fromBar = trayDragFromBar, wasPinned = trayDragWasPinned
        trayDragging = false
        trayPressed = false
        if (over) Qt.callLater(function () { B.trayMove(key, true, idx) })
        else if (fromBar || wasPinned) Qt.callLater(function () { B.trayMove(key, false, -1) })     // a pinned icon dragged off the bar (from the bar or from the popup) = unpin
        closeDelay.restart()
    }
    onWidthChanged: Qt.callLater(syncClip)
    onHeightChanged: Qt.callLater(syncClip)
    onVisibleChanged: if (visible) { Qt.callLater(B.fitWindow); Qt.callLater(syncClip) }

    Timer { interval: 120; running: true; onTriggered: bar.ready = true }
    Timer { interval: 700; running: true; onTriggered: { B.fitWindow(); bar.syncClip() } }
    Timer { interval: 500; running: true; onTriggered: bar.syncClip() }
    Timer { interval: 1500; running: true; onTriggered: bar.syncClip() }
    Timer { interval: 1000; running: bar.visible; repeat: true; onTriggered: bar.now = new Date() }

    function mix(a, b, t) { return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t) }
    function layoutGlyph(n) {
        var m = { bsp: "\uebeb", columns: "\uebf7", rows: "\uec01", grid: "\udb81\udf58", scrolling: "\uebf7",
                  vertical_stack: "\uebee", horizontal_stack: "\uebf0", ultrawide_vertical_stack: "\uebee",
                  right_main_vertical_stack: "\uebf1", monocle: "\uf06f", maximized: "\uf06f", floating: "\uf2d2" }
        return m[n] !== undefined ? m[n] : "\udb81\ude40"
    }

    function pageW(p) { return p === "tray" ? 292 : p === "control" ? 380 + ccOver : p === "media" ? 380 : p === "volume" ? 300 : p === "clock" ? 330 : 300 }
    function pageH(p) { return p === "tray" ? trayPage.h : p === "control" ? Math.min(ccPage.pageHeight, B.fullH - barH - frameW - 6) : p === "media" ? 176 : p === "volume" ? (B.outputs.length > 0 ? 122 + outFlow.height + 14 : 124) : p === "clock" ? clockPage.h : 100 }

    // ---- clock page building blocks ----
                        // small rounded button used all over this page
                        component ClkBtn: Rectangle {
                            id: cb
                            property string text: ""
                            property string icon: ""
                            property bool primary: false
                            property bool selected: false
                            property color accent: "#4cbcff"
                            property color ink: ((0.299 * accent.r + 0.587 * accent.g + 0.114 * accent.b) > 0.55) ? "#000000" : "#ffffff"
                            property string fontFamily: bar.uiFont
                            signal clicked()
                            implicitWidth: cbRow.implicitWidth + 24
                            implicitHeight: 32
                            radius: 8
                            antialiasing: true
                            color: primary ? accent
                                 : selected ? Qt.rgba(accent.r, accent.g, accent.b, 0.3)
                                 : Qt.rgba(1, 1, 1, cbMouse.containsMouse ? 0.14 : 0.08)
                            border.width: selected && !primary ? 1 : 0
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.7)
                            scale: cbMouse.pressed ? 0.96 : 1
                            Behavior on scale { NumberAnimation { duration: 80 } }
                            Behavior on color { ColorAnimation { duration: 90 } }
                            Row {
                                id: cbRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    visible: cb.icon !== ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: cb.icon
                                    font.family: "Segoe Fluent Icons"
                                    font.pixelSize: 13
                                    color: cb.primary ? cb.ink : "white"
                                }
                                Text {
                                    visible: cb.text !== ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: cb.text
                                    font.family: cb.fontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    color: cb.primary ? cb.ink : "white"
                                }
                            }
                            MouseArea {
                                id: cbMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: cb.clicked()
                            }
                        }

                        // number with up / down arrows (mouse wheel works too)
                        component ClkSpin: Item {
                            id: sp
                            property int value: 0
                            property int min: 0
                            property int max: 59
                            property string label: ""
                            property string fontFamily: bar.uiFont
                            property color accent: "#4cbcff"
                            property bool editing: false
                            signal edited(int v)
                            signal editStarted()
                            signal editEnded()
                            implicitWidth: 60
                            implicitHeight: 100
                            // double-click the number, type a value, Enter (or click away) confirms, Esc cancels
                            function beginEdit() {
                                if (editing) return
                                editing = true
                                spInput.text = (value < 10 ? "0" : "") + value
                                editStarted()
                                spFocus.restart()
                            }
                            function commitEdit() {
                                if (!editing) return
                                editing = false
                                var v = parseInt(spInput.text, 10)
                                if (!isNaN(v)) edited(Math.max(min, Math.min(max, v)))
                                editEnded()
                            }
                            function cancelEdit() {
                                if (!editing) return
                                editing = false
                                editEnded()
                            }
                            onVisibleChanged: if (!visible) cancelEdit()
                            Timer {
                                id: spFocus
                                interval: 90
                                onTriggered: {
                                    if (sp.Window.window) sp.Window.window.requestActivate()
                                    spInput.forceActiveFocus()
                                    spInput.selectAll()
                                }
                            }
                            function bump(d) {
                                var v = value + d
                                if (v > max) v = min
                                if (v < min) v = max
                                edited(v)
                            }
                            Rectangle {
                                x: 10; y: 0; width: 40; height: 24; radius: 8; antialiasing: true
                                color: Qt.rgba(1, 1, 1, upMouse.containsMouse ? 0.14 : 0.07)
                                Text { anchors.centerIn: parent; text: "\uE70E"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "white" }
                                MouseArea { id: upMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sp.bump(1) }
                            }
                            Text {
                                y: 28
                                width: parent.width
                                height: 32
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                text: (sp.value < 10 ? "0" : "") + sp.value
                                color: "white"
                                font.family: sp.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                visible: !sp.editing
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.IBeamCursor
                                    onDoubleClicked: sp.beginEdit()
                                    onWheel: (w) => sp.bump(w.angleDelta.y > 0 ? 1 : -1)
                                }
                            }
                            Rectangle {
                                visible: sp.editing
                                x: 4; y: 28; width: parent.width - 8; height: 32
                                radius: 8
                                antialiasing: true
                                color: Qt.rgba(0, 0, 0, 0.35)
                                border.width: 1
                                border.color: sp.accent
                                TextInput {
                                    id: spInput
                                    anchors.fill: parent
                                    horizontalAlignment: TextInput.AlignHCenter
                                    verticalAlignment: TextInput.AlignVCenter
                                    color: "white"
                                    selectByMouse: true
                                    maximumLength: 2
                                    inputMethodHints: Qt.ImhDigitsOnly
                                    validator: IntValidator { bottom: 0; top: 99 }
                                    font.family: sp.fontFamily
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    Keys.onReturnPressed: sp.commitEdit()
                                    Keys.onEnterPressed: sp.commitEdit()
                                    Keys.onEscapePressed: sp.cancelEdit()
                                    onActiveFocusChanged: if (!activeFocus && sp.editing) sp.commitEdit()
                                }
                            }
                            Rectangle {
                                x: 10; y: 64; width: 40; height: 24; radius: 8; antialiasing: true
                                color: Qt.rgba(1, 1, 1, downMouse.containsMouse ? 0.14 : 0.07)
                                Text { anchors.centerIn: parent; text: "\uE70D"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "white" }
                                MouseArea { id: downMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sp.bump(-1) }
                            }
                            Text {
                                y: 90
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: sp.label
                                color: Qt.rgba(1, 1, 1, 0.5)
                                font.family: sp.fontFamily
                                font.pixelSize: 9
                            }
                        }


    // ---- HitPad: lets a bar chip reach the very top / bottom edge of the bar ----
    // the chips are 28 px tall inside the 36 px bar, which leaves a dead 4 px strip above and below. a HitPad is a
    // transparent MouseArea under its chip (z: -1) that covers the full bar height. inside the chip nothing changes
    // (it keeps its own hover / click / reveal), the pad only catches the gap. hover = pad or chip, with a short
    // debounce so moving between the two never flickers the popup.
    component HitPad: MouseArea {
        id: hp
        property Item target: null
        property bool wheelEnabled: false
        property bool cover: false          // true: the pad sits above its chip and tracks hover on its own (never clicks)
        readonly property bool over: hp.containsMouse || (!cover && target !== null && target.hovered === true)
        property bool last: false
        signal hoverToggled(bool on)
        signal wheeled(real delta)
        z: cover ? 5 : -1
        x: target ? target.x + target.parent.x : 0
        y: 0
        width: target ? target.width : 0
        height: bar.barH
        visible: target !== null && target.visible && target.width > 0.5
        hoverEnabled: true
        acceptedButtons: cover ? Qt.NoButton : (Qt.LeftButton | Qt.RightButton | Qt.MiddleButton)
        onOverChanged: {
            if (over) { hoverOff.stop(); if (!last) { last = true; hoverToggled(true) } }
            else hoverOff.restart()
        }
        onVisibleChanged: if (!visible && last) { last = false; hoverToggled(false) }
        Timer { id: hoverOff; interval: 45; onTriggered: if (!hp.over && hp.last) { hp.last = false; hp.hoverToggled(false) } }
        // a click in the gap above / below the chip does what a click on the chip does
        onClicked: (m) => { if (target && typeof target.activated === "function") target.activated(m.button) }
        onWheel: (w) => {
            if (wheelEnabled) { wheeled(w.angleDelta.y); w.accepted = true } else w.accepted = false
        }
    }

    // scroll over a music widget = previous / next playing app (same as the media chip in the bar)
    component MediaWheel: MouseArea {
        property real acc: 0
        anchors.fill: parent
        onWheel: (w) => {
            acc += w.angleDelta.y
            if (Math.abs(acc) >= 120) { B.mediaCycle(acc > 0 ? -1 : 1); acc = 0 }
        }
    }

    // one line of the profile card: icon + text
    component ProfileRow: Row {
        property string glyph: ""
        property string label: ""
        spacing: 8
        height: 22
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: 20
            horizontalAlignment: Text.AlignHCenter
            text: parent.glyph
            font.family: "Segoe Fluent Icons"
            font.pixelSize: 15
            color: bar.accent
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 28
            text: parent.label
            color: "white"
            font.family: bar.uiFont
            font.pixelSize: 13
            font.weight: Font.DemiBold
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 9
            elide: Text.ElideRight
        }
    }

    // ---- clock: timer + alarms ----
    // they live here and not in the popup, so they keep running while it's closed
    property real timerEnd: 0              // epoch ms when the running timer ends, 0 = not running
    property int timerTotal: 0             // seconds the timer was set to
    property int timerPausedLeft: 0        // seconds left while paused
    readonly property int timerLeft: timerEnd > 0 ? Math.max(0, Math.ceil((timerEnd - now.getTime()) / 1000)) : timerPausedLeft
    property var alarms: []                // reminders: [{ts, on, rep, t}]
    property string ringing: ""
    property bool clockTyping: false       // true while the reminder text box has the keyboard (the popup then takes focus)

    function fmtDur(sec) {
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
        function p(n) { return (n < 10 ? "0" : "") + n }
        return (h > 0 ? h + ":" + p(m) : p(m)) + ":" + p(s)
    }
    function clockSave() {
        try { B.clockSave(JSON.stringify({ alarms: alarms, timerEnd: timerEnd, timerTotal: timerTotal, timerPausedLeft: timerPausedLeft })) }
        catch (e) { console.log("B.clockSave failed:", e) }
    }
    function clockLoad() {
        try {
            var d = JSON.parse(B.clockLoad() || "{}")
            var list = d.alarms || [], out = []
            for (var i = 0; i < list.length; i++) {
                var r = list[i]
                if (r.ts === undefined) {                       // alarm from the earlier version: next time that clock time comes round
                    var n = new Date(), t = new Date(n.getFullYear(), n.getMonth(), n.getDate(), r.h, r.m, 0, 0)
                    if (t.getTime() <= n.getTime()) t.setDate(t.getDate() + 1)
                    r = { ts: t.getTime(), on: r.on, rep: r.daily ? "daily" : "none", t: r.t || "" }
                }
                out.push(r)
            }
            alarms = out
            if (d.timerEnd > Date.now()) { timerEnd = d.timerEnd; timerTotal = d.timerTotal || 0 }
            else if (d.timerPausedLeft > 0) { timerPausedLeft = d.timerPausedLeft; timerTotal = d.timerTotal || 0 }
        } catch (e) { alarms = [] }
    }
    function timerStart(sec) {
        if (sec <= 0) return
        timerTotal = sec
        timerPausedLeft = 0
        timerEnd = Date.now() + sec * 1000
        clockSave()
    }
    function timerTogglePause() {
        if (timerEnd > 0) { timerPausedLeft = timerLeft; timerEnd = 0 }
        else if (timerPausedLeft > 0) { timerEnd = Date.now() + timerPausedLeft * 1000; timerPausedLeft = 0 }
        clockSave()
    }
    function timerAdd(sec) {
        if (timerEnd > 0) timerEnd += sec * 1000
        else if (timerPausedLeft > 0) timerPausedLeft += sec
        timerTotal += sec
        clockSave()
    }
    function timerCancel() { timerEnd = 0; timerPausedLeft = 0; timerTotal = 0; clockSave() }

    // a reminder is {ts: when (epoch ms), t: text, on: bool, rep: "none" | "daily" | "weekly" | "monthly"}
    function repLabel(r) { return r === "daily" ? "Every day" : r === "weekly" ? "Every week" : r === "monthly" ? "Every month" : "Once" }
    function nextRep(r) { return r === "none" ? "daily" : r === "daily" ? "weekly" : r === "weekly" ? "monthly" : "none" }
    function fmtReminder(ts, rep) {
        return Qt.formatDateTime(new Date(ts), "ddd d MMM, h:mm AP") + (rep !== "none" ? "  \u00B7  " + repLabel(rep).toLowerCase() : "")
    }
    // first time after now that a repeating reminder (starting at ts) comes round. for "none" it just returns ts
    function nextTs(ts, rep) {
        if (rep === "none") return ts
        var d = new Date(ts), n = Date.now(), guard = 0
        while (d.getTime() <= n && guard++ < 4000) {
            if (rep === "daily") d.setDate(d.getDate() + 1)
            else if (rep === "weekly") d.setDate(d.getDate() + 7)
            else d.setMonth(d.getMonth() + 1)
        }
        return d.getTime()
    }
    function alarmAdd(ts, rep, text) {
        var a = alarms.slice()
        a.push({ ts: ts, on: true, rep: rep, t: text || "" })
        a.sort(function (x, y) { return x.ts - y.ts })
        alarms = a
        clockSave()
    }
    function alarmToggle(i) {
        var a = alarms.slice(), r = a[i]
        var on = !r.on
        var ts = r.ts
        if (on && ts <= Date.now()) ts = r.rep !== "none" ? nextTs(ts, r.rep) : ts + Math.ceil((Date.now() - ts + 1000) / 86400000) * 86400000   // a past one-off moves to the same time on the next day
        a[i] = { ts: ts, on: on, rep: r.rep, t: r.t || "" }
        alarms = a; clockSave()
    }
    function alarmRepeat(i) {
        var a = alarms.slice(), r = a[i]
        a[i] = { ts: r.ts, on: r.on, rep: nextRep(r.rep), t: r.t || "" }
        alarms = a; clockSave()
    }
    function alarmDelete(i) {
        var a = alarms.slice(); a.splice(i, 1)
        alarms = a; clockSave()
    }
    function alarmReplace(i, ts, rep, text) {
        var a = alarms.slice()
        if (i < 0 || i >= a.length) { alarmAdd(ts, rep, text); return }
        a[i] = { ts: ts, on: true, rep: rep, t: text || "" }
        a.sort(function (x, y) { return x.ts - y.ts })
        alarms = a
        clockSave()
    }
    // opens the clock popup on the Reminders tab with reminder i loaded for editing
    function openReminderEdit(i) {
        sideWant = false
        anchorX = clockChip.mapToItem(null, clockChip.width / 2, 0).x
        page = "clock"
        clockPage.startEdit(i)
    }

    property string ringTitle: ""
    property string ringSub: ""
    function ring(title, sub) {
        console.log("alarm:", title, sub)
        // the in-bar card / clock text come first, so a backend problem can never stop them
        ringTitle = title
        ringSub = sub || ""
        ringing = title + (sub ? "  \u00B7  " + sub : "")
        ringStopTimer.restart()
        try { B.ringStart() } catch (e) { console.log("B.ringStart failed:", e) }
    }
    function dismissRing() { ringing = ""; ringStopTimer.stop(); try { B.ringStop() } catch (e) { console.log("B.ringStop failed:", e) } }
    function snoozeRing() { var t = ringTitle; dismissRing(); alarmAdd(Date.now() + 300000, "none", t) }
    Timer { id: ringStopTimer; interval: 60000; onTriggered: bar.dismissRing() }

    // checked once a second, even while the bar is hidden. two clocks can call it (a second call finds nothing left
    // to do): this QML Timer and a plain OS timer in the backend (B.clockPoke), which keeps ticking when Qt Quick
    // has nothing to draw.
    property int tickN: 0
    function clockTick() {
        var now = Date.now()
        var fired = []
        var changed = false
        var next = 0
        try {
            if (timerEnd > 0) {
                if (now >= timerEnd) {
                    timerEnd = 0; timerPausedLeft = 0; timerTotal = 0
                    fired.push(["Timer finished", "Your timer is up"])
                    changed = true
                } else next = timerEnd
            }
            var a = alarms.slice()
            for (var i = 0; i < a.length; i++) {
                var r = a[i]
                if (!r || !r.on) continue
                var ts = Number(r.ts)
                if (isNaN(ts)) continue
                if (ts <= now) {
                    var rep = r.rep || "none"
                    fired.push([r.t && r.t !== "" ? r.t : "Reminder", Qt.formatDateTime(new Date(ts), "h:mm AP")])
                    a[i] = rep === "none" ? { ts: ts, on: false, rep: "none", t: r.t || "" }
                                          : { ts: nextTs(ts, rep), on: true, rep: rep, t: r.t || "" }
                    changed = true
                } else if (next === 0 || ts < next) next = ts
            }
            if (changed) alarms = a
        } catch (e) { console.log("clockTick failed:", e) }
        for (var k = 0; k < fired.length; k++) {
            try { ring(fired[k][0], fired[k][1]) } catch (e) { console.log("ring failed:", e) }
        }
        if (changed) clockSave()
        // while something is about to go off, write it to vapor.log every 10 s (so you can see the clock is alive)
        tickN++
        if (next > 0 && tickN % 10 === 0 && next - now < 120000) console.log("clock: next alert in", Math.round((next - now) / 1000), "s")
    }
    Timer { interval: 1000; running: true; repeat: true; onTriggered: bar.clockTick() }
    Connections { target: B; function onClockPoke() { bar.clockTick() } }
    // commands from the CLI (vaporctl) that need QML state: alerts, timer, reminders
    Connections {
        target: B
        function onCliCommand(name, arg) {
            try {
                var d = arg !== "" ? JSON.parse(arg) : null
                if (name === "alert") bar.ring(d[0], d[1])
                else if (name === "dismiss") bar.dismissRing()
                else if (name === "timer") bar.timerStart(Number(d))
                else if (name === "timer-cancel") bar.timerCancel()
                else if (name === "remind") bar.alarmAdd(Number(d.ts), d.rep || "none", d.t || "")
                else if (name === "remind-rm") bar.alarmDelete(Number(d))
                else if (name === "note") bar.noteSave(d.title || "", d.t || "", -1)
                else if (name === "note-rm") bar.noteDelete(Number(d))
                else if (name === "location") { bar.applyPlace(true); bar.weatherFetch() }
            } catch (e) { console.log("cli command failed:", name, e) }
        }
    }

    // ---- hovering opens a page, leaving the chip and the panel closes it ----
    property string pendingName: ""
    property var pendingItem: null
    Timer { id: openDelay; interval: 90; onTriggered: if (bar.pendingItem) bar.showPage(bar.pendingName, bar.pendingItem) }
    Timer { id: closeDelay; interval: 280; onTriggered: {
        // the mouse is on a chip: never close. (and if the popup did get closed under it, bring it back, which is what
        // used to leave the chip highlighted with no popup until you moved out and in again)
        if (bar.hoverChip !== "" && bar.hoverChipItem) { bar.showPage(bar.hoverChip, bar.hoverChipItem); return }
        if (!panelHover.hovered && bar.page !== "control" && !bar.clockTyping && !bar.trayBusy && !bar.trayHold) bar.page = ""
    } }

    // the control center is click-to-open and stays open (hovering other chips never takes it over),
    // it closes on a second click or when you focus another window
    function toggleControl(item) {
        openDelay.stop()
        closeDelay.stop()
        if (page === "control") { page = ""; return }
        anchorX = item.mapToItem(null, item.width / 2, 0).x
        page = "control"
    }

    function showPage(name, item) {
        if (page === "control" && name !== "control") return
        if (trayBusy && name !== "tray") return          // dragging a tray icon: hovering other chips must not swap the popup away
        if (page === name) return
        anchorX = item.mapToItem(null, item.width / 2, 0).x
        page = name
    }
    function chipHover(name, item, on) {
        if (on) {
            hoverChip = name
            hoverChipItem = item
            closeDelay.stop()
            if (open) showPage(name, item)      // sliding from one chip to another: switch straight away
            else { pendingName = name; pendingItem = item; openDelay.restart() }
        } else {
            if (hoverChip !== name) return      // a late "left" from the chip we just came from: the mouse is already on another one
            hoverChip = ""
            hoverChipItem = null
            openDelay.stop()
            closeDelay.restart()
        }
    }

    // the window is clipped to the glass (screen minus the rounded hole, plus the popup) so the transparent middle
    // never swallows clicks meant for other apps
    readonly property bool panelActive: panelH >= 1.5 && shapeW > 4
    function syncClip() {
        var p = false                       // the popup is its own window now
        var cw = wantW + 28                 // spring overshoot margin, the region only has to be big enough, never exact
        var ch = clipH + 28
        B.setClip(Math.round(frameNow), Math.round(barNow), Math.round(width - 2 * frameNow),
                  Math.round(height - barNow - frameNow + bottomExtra), Math.round(holeR),
                  p ? Math.max(0, Math.floor(wantCX - cw / 2 - flare - 2)) : 0, p ? Math.round(barNow) - 2 : 0,
                  p ? Math.ceil(cw + flare * 2 + 4) : 0, p ? Math.ceil(ch + 6) : 0)
    }


    // ---- popup window box: only recomputed when the target changes, never per animation frame ----
    property real popX: 0
    property real popW: 480
    property real popH: 120
    readonly property real popY: barH - 2
    Timer { id: popSettle; interval: 900; onTriggered: bar.fitPopup(true) }
    function fitPopup(settled) {
        // while the popup slides between chips the window covers both the old and the new spot,
        // once it has settled it shrinks back around the target
        var half = Math.max(panelW, wantW) / 2 + flare + 30
        var lo = settled === true ? wantCX : Math.min(panelCX, wantCX)
        var hi = settled === true ? wantCX : Math.max(panelCX, wantCX)
        var l = Math.max(0, Math.floor(lo - half))
        var r = Math.min(width, Math.ceil(hi + half))
        var h = Math.ceil(Math.max(clipH, panelH) + 36)
        // resizing a transparent window re-creates its swap chain (slow, and dwm.exe keeps growing). while the panel
        // morphs its height changes every frame, so the window only grows in coarse steps and shrinks once settled
        h = Math.min(Math.ceil(h / 96) * 96, Math.max(96, Math.floor(B.fullH - popY)))
        if (settled !== true && h < popH) h = popH
        if (l !== popX) popX = l
        if (r - l !== popW) popW = r - l
        if (h !== popH) popH = h
        if (settled !== true) popSettle.restart()
    }
    Component.onCompleted: { fitPopup(true); clockLoad(); notesLoad() }

    // animated panel geometry (springs give the morph its bounce)
    readonly property real edge: frameW + frameR + flare + 2     // keeps the panel + flares on the straight part of the bar
    readonly property real wantW: pageW(lastPage)
    readonly property real wantH: open ? pageH(page) : 0
    // the control center is joined to the screen edge (flush with the frame), the other popups stay clear of the corners
    readonly property real ccOver: 30          // how far the control center's panel runs past the frame, off-screen
    readonly property real wantCX: lastPage === "control" ? (width - frameW + ccOver - wantW / 2)
                                                          : Math.max(wantW / 2 + edge, Math.min(width - wantW / 2 - edge, anchorX))
    property real panelW: wantW
    property real rawH: 0                       // animated by hAnim below (never negative now, but clamped to be safe)
    readonly property real panelH: Math.max(0, rawH)
    // the drawn width follows the height. before, the panel was already full width while only a few px tall, which
    // looked like a wide flat line when opening and closing. now it grows out of the bar as a bump.
    readonly property real grow: Math.max(0, Math.min(1, panelH / 60))
    readonly property real shapeW: panelW * grow * grow * (3 - 2 * grow)
    property real panelCX: wantCX

    // height: one explicit animation whose curve depends on the direction (grow = expressive curve with a hair of
    // overshoot, shrink = emphasized, close = accelerate into the bar). it ends exactly on target, so the popup window
    // can hide right away instead of waiting for a spring to settle.
    NumberAnimation { id: hAnim; target: bar; property: "rawH"; easing.type: Easing.BezierSpline }
    function animateH() {
        hAnim.stop()
        var to = wantH
        if (snapClose || Math.abs(to - rawH) < 0.5) { rawH = to; return }
        if (ccPage.themeMorph)  { hAnim.duration = 320 * popSpeed; hAnim.easing.bezierCurve = curveEmphasized }
        else if (to > rawH)     { hAnim.duration = (rawH < 1 ? 460 : 400) * popSpeed; hAnim.easing.bezierCurve = curveSpatial }
        else if (to <= 0)       { hAnim.duration = 240 * popSpeed; hAnim.easing.bezierCurve = curveExit }
        else                    { hAnim.duration = 340 * popSpeed; hAnim.easing.bezierCurve = curveEmphasized }
        hAnim.to = to
        hAnim.start()
    }
    // sliding / resizing between two chips
    Behavior on panelW  { enabled: bar.panelH > 20; NumberAnimation { duration: 380 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveEmphasized } }
    Behavior on panelCX { enabled: bar.panelH > 20; NumberAnimation { duration: 380 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveEmphasized } }

    // ---- glass: bar + frame + popup as one shape ----
    Glass {
        x: 0
        y: 0
        width: bar.width
        height: bar.height
        visible: bar.reveal > 0.01 && !B.noGlass
        fillColor: bar.glassFill
        holeX: bar.frameNow
        holeY: bar.barNow
        holeW: bar.width - 2 * bar.frameNow
        holeH: bar.height - bar.barNow - bar.frameNow + bar.bottomExtra
        holeR: bar.holeR
        panelX: 0
        panelW: 0
        panelH: 0
        panelR: 22
        flare: bar.flare
        outline: bar.glassLine
        cutRY0: bar.sideCutY0
        cutRY1: bar.sideCutY1
        cutBX0: bar.dockCutX0
        cutBX1: bar.dockCutX1
    }


    // ---- frame windows (--strip) ----
    // the sides + bottom of the frame are three thin static windows, so the main window only has to be as tall as
    // the bar + popups. each one draws the same glass shape, shifted by its own origin.
    component EdgeWin: Window {
        id: ew
        property real ox: 0
        property real oy: 0
        visible: bar.shown && B.stripMode && !B.noGlass && width > 0 && height > 0
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        x: B.screenX + ox
        y: B.screenY + oy
        Glass {
            anchors.fill: parent
            originX: ew.ox
            originY: ew.oy
            visible: bar.reveal > 0.01
            fillColor: bar.glassFill
            holeX: bar.frameNow
            holeY: bar.barNow
            holeW: bar.width - 2 * bar.frameNow
            holeH: B.fullH - bar.barNow - bar.frameNow
            holeR: bar.holeR
            panelH: 0
            outline: bar.glassLine
            cutRY0: bar.sideCutY0
            cutRY1: bar.sideCutY1
            cutBX0: bar.dockCutX0
            cutBX1: bar.dockCutX1
        }
        // hover handle (only the right frame has one): a slim pill in the middle of the edge
        property bool side: false
        signal handleHover(bool on)
        property bool bottom: false
        readonly property bool handleHovered: sideHH.hovered || botHH.hovered
        Item {
            visible: ew.side
            width: ew.width
            height: 200
            y: Math.round(B.fullH / 2 - ew.oy - height / 2)
            HoverHandler { id: sideHH; enabled: ew.side; onHoveredChanged: ew.handleHover(hovered) }
            Rectangle {
                anchors.centerIn: parent
                width: 4
                height: sideHH.hovered || bar.sideWant ? 72 : 52
                radius: 2
                antialiasing: true
                color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, sideHH.hovered || bar.sideWant ? 0.95 : 0.45)
                Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 140 } }
            }
        }
        // hover handle of the bottom frame: a slim pill in the middle of the bottom edge (opens the dock)
        Item {
            visible: ew.bottom
            width: 200
            height: bar.frameW
            x: Math.round(ew.width / 2 - width / 2)
            y: ew.height - bar.frameW
            HoverHandler { id: botHH; enabled: ew.bottom; onHoveredChanged: ew.handleHover(hovered) }
            Rectangle {
                anchors.centerIn: parent
                height: 4
                width: botHH.hovered || bar.dockWant ? 72 : 52
                radius: 2
                antialiasing: true
                color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, botHH.hovered || bar.dockWant ? 0.95 : 0.45)
                Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: 140 } }
            }
        }
    }
    readonly property int cornerH: frameW + frameR      // height of the bottom strip, covers the rounded bottom corners
    EdgeWin { title: "Vapor L"; ox: 0;                    oy: bar.height - 2; width: bar.frameW; height: B.fullH - bar.height - bar.cornerH + 4 }
    EdgeWin { id: edgeR; side: true; onHandleHover: (on) => bar.sideHover(on); title: "Vapor R"; ox: bar.width - bar.frameW; oy: bar.height - 2; width: bar.frameW; height: B.fullH - bar.height - bar.cornerH + 4 }
    EdgeWin { id: edgeB; bottom: true; onHandleHover: (on) => bar.dockHover(on); title: "Vapor B"; ox: 0;                    oy: B.fullH - bar.cornerH; width: bar.width; height: bar.cornerH }

    // ---- the bar (content only: left / centre / right) ----
    Item {
        id: pill
        x: 0
        y: bar.barNow - bar.barH            // slides up with the frame when it retracts
        width: bar.width
        height: bar.barH

        Row {
            id: leftRow
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            Chip {
                shown: B.hasBattery
                iconComponent: batteryIcon
                text: B.battery + "%"
                revealOnHover: true
            }

            Chip {
                id: wifiChip
                icon: B.netKind === "ethernet" ? "\uE839" : "\uE701"
                iconColor: B.wifiConnected ? bar.blue : Qt.rgba(1, 1, 1, 0.35)
                text: B.wifiConnected ? B.wifiName : "Not connected"
                revealOnHover: true
                onActivated: B.openUri("ms-settings:network")
            }

            Chip {
                shown: B.headphones !== ""
                icon: "\uE7F6"
                text: B.headphones
                revealOnHover: true
            }

            Chip {
                shown: !B.komoOnline
                text: "Komorebi offline"
                textColor: bar.lavender
                showText: true
            }

            Chip {
                id: layoutChip
                shown: B.komoOnline && B.layout !== ""
                icon: bar.layoutGlyph(B.layout)
                iconFont: "CaskaydiaCove NFP"
                iconColor: bar.lavender
                text: B.layout.replace(/_/g, " ")
                revealOnHover: true
                onActivated: (button) => B.cycleLayout(button === Qt.RightButton ? -1 : 1)
            }

            Item {
                id: ws
                property int n: B.wsCount
                property int active: B.wsActive
                property real l: 0
                property real r: 0
                property int prev: 0
                property bool inited: false

                height: 28
                width: n > 0 ? n * 22 + 12 : 0
                visible: width > 0.5
                Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                Rectangle { anchors.fill: parent; radius: 14; color: Qt.rgba(1, 1, 1, 0.06) }

                Repeater {
                    model: ws.n
                    Rectangle {
                        required property int index
                        x: 6 + index * 22 + 7
                        anchors.verticalCenter: parent.verticalCenter
                        width: 8
                        height: 8
                        radius: 4
                        color: B.wsPopulated[index] === true ? Qt.rgba(1, 1, 1, 0.42) : Qt.rgba(1, 1, 1, 0.16)
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                }

                // the active pill stretches towards its target, the leading edge moves first
                Rectangle {
                    x: ws.l
                    width: Math.max(12, ws.r - ws.l)
                    // a circle at rest. while it stretches towards the next workspace it gets thinner, so it reads as a
                    // long rounded line and not a fat blob
                    height: 12 - 6 * Math.min(1, (width - 12) / 18)
                    radius: height / 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: bar.accent
                    visible: ws.n > 0
                }

                NumberAnimation { id: lAnim; target: ws; property: "l"; easing.type: Easing.OutCubic }
                NumberAnimation { id: rAnim; target: ws; property: "r"; easing.type: Easing.OutCubic }

                onActiveChanged: {
                    var tl = 6 + active * 22 + 5
                    var tr = 6 + active * 22 + 17
                    if (!inited) { l = tl; r = tr; inited = true; prev = active; return }
                    var right = active > prev
                    lAnim.duration = right ? 230 : 120
                    rAnim.duration = right ? 120 : 230
                    lAnim.to = tl
                    rAnim.to = tr
                    lAnim.restart()
                    rAnim.restart()
                    prev = active
                }
                Component.onCompleted: { l = 6 + active * 22 + 5; r = 6 + active * 22 + 17; inited = true; prev = active }

                MouseArea {
                    anchors.fill: parent
                    anchors.topMargin: -bar.hitPad
                    anchors.bottomMargin: -bar.hitPad
                    onClicked: (m) => {
                        var i = Math.floor((m.x - 6) / 22)
                        if (i >= 0 && i < ws.n) B.focusWorkspaceAt(i)
                    }
                    onWheel: (w) => B.stepWorkspace(w.angleDelta.y > 0 ? -1 : 1)
                }
            }
        }


        Item {
            id: taskBox
            anchors.centerIn: parent
            height: 28
            width: tasks.implicitWidth
            Behavior on width { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

            Row {
                id: tasks
                spacing: 4
                add: Transition {
                    NumberAnimation { properties: "opacity,scale"; from: 0; to: 1; duration: 340; easing.type: Easing.OutBack }
                }
                move: Transition {
                    NumberAnimation { properties: "x"; duration: 320; easing.type: Easing.OutCubic }
                }

                Repeater {
                    model: taskModel
                    delegate: Item {
                        id: td
                        required property string appKey
                        required property string appTitle
                        required property bool isActive
                        required property int winCount
                        required property string iconUrl

                        width: 32
                        height: 28

                        Rectangle {
                            anchors.fill: parent
                            radius: 14
                            color: bar.hoverColor
                            opacity: tdMouse.containsMouse ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                        }
                        Image {
                            anchors.centerIn: parent
                            anchors.verticalCenterOffset: -2
                            width: 18
                            height: 18
                            source: td.iconUrl
                            sourceSize: Qt.size(36, 36)
                            smooth: true
                            mipmap: true
                            scale: tdMouse.containsMouse ? 1.2 : 1
                            Behavior on scale { SpringAnimation { spring: 5; damping: 0.35; epsilon: 0.005 } }
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: parent.height - 6
                            height: 3
                            radius: 1.5
                            width: td.isActive ? 14 : (td.winCount > 1 ? 8 : 4)
                            color: td.isActive ? bar.accent : Qt.rgba(1, 1, 1, 0.35)
                            Behavior on width { SpringAnimation { spring: 4; damping: 0.4; epsilon: 0.25 } }
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }
                        MouseArea {
                            id: tdMouse
                            anchors.fill: parent
                            anchors.topMargin: -bar.hitPad
                            anchors.bottomMargin: -bar.hitPad
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                            cursorShape: Qt.PointingHandCursor
                            onClicked: (m) => {
                                if (m.button === Qt.MiddleButton) B.taskClose(td.appKey)
                                else B.taskClick(td.appKey)
                            }
                        }
                    }
                }
            }
        }


        Row {
            id: rightRow
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            // audio visualizer: 6 mirrored bars, slides away 3 s after the sound stops
            Item {
                id: viz
                property bool shown: B.vizActive
                height: 28
                width: shown ? 6 * 2 + 5 * 3 + 20 : 0
                opacity: shown ? 1 : 0
                visible: shown || width > 0.5
                clip: true
                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 220 } }

                Repeater {
                    model: 6
                    Rectangle {
                        required property int index
                        readonly property real v: B.vizBars.length > index ? B.vizBars[index] : 0
                        x: 10 + index * 5
                        width: 2
                        height: 3 + v * 19
                        radius: 1
                        anchors.verticalCenter: parent.verticalCenter
                        color: bar.mix(bar.accent, bar.lavender, index / 5)
                        Behavior on height { NumberAnimation { duration: 70 } }
                    }
                }
            }

            // system tray: pinned icons live here (left click = open, right click = its menu, middle click = unpin),
            // the chevron opens the tray popup with every icon and a pin button on each
            Row {
                id: trayRow
                height: 28
                spacing: 0
                Repeater {
                    model: trayModel
                    Item {
                        id: tb
                        required property string trayKey
                        required property string trayTitle
                        required property string iconUrl
                        required property bool pinned
                        readonly property bool beingDragged: bar.trayDragging && bar.trayDragKey === trayKey
                        height: 28
                        width: pinned ? 28 : 0
                        opacity: pinned ? (beingDragged ? (bar.trayOverBar ? 0.3 : 0.12) : 1) : 0
                        visible: width > 0.5
                        clip: width < 27.5          // only clips while it slides in / out, so the hit area can reach the screen edge
                        Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                        Behavior on opacity { NumberAnimation { duration: 120 } }

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 1
                            radius: 13
                            color: bar.hoverColor
                            opacity: tbMouse.containsMouse ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: 140 } }
                        }
                        Image {
                            width: 16
                            height: 16
                            x: Math.round((parent.width - width) / 2 * Screen.devicePixelRatio) / Screen.devicePixelRatio
                            y: Math.round((parent.height - height) / 2 * Screen.devicePixelRatio) / Screen.devicePixelRatio
                            source: tb.iconUrl
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            mipmap: true
                            scale: tbMouse.pressed ? 0.85 : 1
                            Behavior on scale { SpringAnimation { spring: 14; damping: 0.5; epsilon: 0.005 } }
                        }
                        MouseArea {
                            id: tbMouse
                            anchors.fill: parent
                            anchors.topMargin: -bar.hitPad
                            anchors.bottomMargin: -bar.hitPad
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                            cursorShape: Qt.PointingHandCursor
                            property real sx: 0
                            property real sy: 0
                            property bool moved: false
                            onPressed: (m) => { sx = m.x; sy = m.y; moved = false; bar.trayPressed = true }
                            Component.onDestruction: if (pressed) { bar.trayPressed = false; if (moved) bar.trayDragging = false }
                            onPositionChanged: (m) => {
                                if (!(pressedButtons & Qt.LeftButton)) return
                                if (!moved && Math.abs(m.x - sx) + Math.abs(m.y - sy) > 8) {
                                    moved = true
                                    bar.beginTrayDrag(tb.trayKey, tb.iconUrl, true, true)
                                }
                                if (moved) {
                                    var p = tbMouse.mapToItem(null, m.x, m.y)
                                    bar.moveTrayDrag(p.x, p.y)
                                }
                            }
                            onReleased: { bar.trayPressed = false; if (moved) bar.endTrayDrag(); else closeDelay.restart() }
                            onCanceled: { moved = false; bar.trayDragging = false; bar.trayPressed = false; closeDelay.restart() }
                            onClicked: (m) => {
                                if (moved) return
                                if (m.button === Qt.MiddleButton) B.trayTogglePin(tb.trayKey)
                                else B.trayClick(tb.trayKey, m.button === Qt.RightButton ? "right" : "left")
                            }
                        }
                    }
                }
            }

            Chip {
                id: trayChip
                shown: B.trayCount > 0
                icon: "\uE70E"
                iconSize: 12
                iconColor: bar.page === "tray" ? "white" : bar.muted
            }

            Chip {
                id: volumeChip
                icon: (B.muted || B.volume <= 0) ? "\uE74F" : B.volume <= 5 ? "\uE992" : B.volume <= 20 ? "\uE993" : B.volume <= 50 ? "\uE994" : "\uE995"
                text: B.muted ? "Muted" : B.volume + "%"
                revealOnHover: true
                onActivated: (button) => { if (button === Qt.RightButton) B.toggleMute() }
            }

            Chip {
                id: clockChip
                fillColor: (clockPad.over || bar.page === "clock") ? bar.hoverColor : "transparent"
                Behavior on fillColor { ColorAnimation { duration: 160 } }
                iconComponent: null
                text: bar.ringing !== "" ? bar.noteText(bar.ringing)
                    : (bar.timerLeft > 0 ? bar.fmtDur(bar.timerLeft) + "  \u00B7  " : "") + Qt.formatDateTime(bar.now, "hh:mm AP")
                showText: true
                hoverFx: false
                icon: ""
            }

            Chip {
                id: notifChip
                icon: "\uE7E7"
                iconColor: bar.lavender
                onActivated: B.openNotifications()
            }

            Chip {
                id: ccChip
                icon: "\uE712"
                iconColor: bar.page === "control" ? "white" : B.themeBlue
                fillColor: bar.page === "control" ? Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.3) : "transparent"
                onActivated: bar.toggleControl(ccChip)
            }
        }

        // media: slides open when something plays, album art glows faintly behind the title.
        // it sits left of everything on the right and only gets the room between the app icons and those chips. the more
        // tray icons you pin (or apps you open) the narrower it gets, and when there's no sensible room left it switches off.
        Item {
            id: mediaChip
            readonly property real room: rightRow.x - 2 - (taskBox.x + taskBox.width) - 12
            readonly property real maxW: Math.min(250, room)
            property bool fits: true                       // hysteresis, so it doesn't flicker around the threshold
            onMaxWChanged: fits = fits ? maxW >= 90 : maxW >= 104
            Component.onCompleted: fits = maxW >= 96
            property bool shown: B.mediaTitle !== "" && fits
            anchors.right: rightRow.left
            anchors.rightMargin: 2
            anchors.verticalCenter: parent.verticalCenter
            height: 28
            property real wantW: shown ? 34 + mediaLabel.width + 14 : 0
            Behavior on wantW { NumberAnimation { duration: 340; easing.type: Easing.OutCubic } }
            width: Math.max(0, Math.min(wantW, maxW))      // growing is animated, shrinking to make room is immediate (never overlaps)
            opacity: shown ? 1 : 0
            visible: shown || width > 0.5
            clip: true
            Behavior on opacity { NumberAnimation { duration: 220 } }

            RoundImage { anchors.fill: parent; radius: 14; cover: true; source: B.mediaArt; opacity: 0.2 }
            Rectangle {
                anchors.fill: parent
                radius: 14
                color: bar.hoverColor
                opacity: mediaMouse.containsMouse ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 160 } }
            }
            RoundImage {
                x: 4
                anchors.verticalCenter: parent.verticalCenter
                width: 20
                height: 20
                radius: 10
                source: B.mediaArt
            }
            Marquee {
                id: mediaLabel
                x: 30
                anchors.verticalCenter: parent.verticalCenter
                maxWidth: Math.max(0, Math.min(200, mediaChip.maxW - 48))
                text: B.mediaArtist !== "" ? B.mediaTitle + " - " + B.mediaArtist : B.mediaTitle
                color: "white"
                fontFamily: bar.uiFont
                pixelSize: 12
                weight: Font.DemiBold
                active: mediaChip.shown
            }
        }

        // the media chip's hit area lives outside the chip (the chip clips its children) and runs the full height of
        // the bar so it reaches the very top edge of the screen
        MouseArea {
            id: mediaMouse
            anchors.left: mediaChip.left
            anchors.right: mediaChip.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            enabled: mediaChip.shown
            visible: mediaChip.visible
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
            cursorShape: Qt.PointingHandCursor
            onClicked: (m) => {
                if (m.button === Qt.MiddleButton) B.mediaPlayPause()
            }
            // scroll while hovering: jump between the apps that can play (Spotify, Zen, ...)
            onWheel: (w) => B.mediaCycle(w.angleDelta.y > 0 ? -1 : 1)
            onContainsMouseChanged: bar.chipHover("media", mediaChip, containsMouse)
        }

        // ---- full-height hit strips over the bar chips (see HitPad) ----
        HitPad { target: wifiChip }
        HitPad { target: layoutChip }
        HitPad { target: trayChip;   onHoverToggled: (on) => bar.chipHover("tray", trayChip, on) }
        HitPad { target: volumeChip; wheelEnabled: true; onHoverToggled: (on) => bar.chipHover("volume", volumeChip, on); onWheeled: (delta) => B.stepVolume(delta > 0 ? 2 : -2) }
        HitPad { id: clockPad; target: clockChip;  cover: true; onHoverToggled: (on) => bar.chipHover("clock", clockChip, on) }
        HitPad { target: notifChip }
        HitPad { target: ccChip }

        // ---- drop feedback while a tray icon is dragged over the bar ----
        Rectangle {                 // new icon: a line where it will be inserted
            visible: bar.trayOverBar && !bar.trayDragFromBar
            z: 50
            x: bar.trayDropX - 1.5
            y: (parent.height - height) / 2
            width: 3
            height: 22
            radius: 1.5
            color: bar.accent
        }
        Rectangle {                 // icon that's already pinned: the slot it will move to
            visible: bar.trayOverBar && bar.trayDragFromBar
            z: 50
            x: bar.trayDropX
            y: (parent.height - height) / 2
            width: 28
            height: 28
            radius: 14
            color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.22)
            border.width: 1.5
            border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.8)
        }
        Rectangle {                 // the dragged icon follows the pointer
            visible: bar.trayDragging && (bar.trayOverBar || bar.trayDragFromBar)
            z: 60
            width: 28
            height: 28
            radius: 14
            x: bar.trayDragX - 14
            y: bar.trayDragY - pill.y - 14
            color: Qt.rgba(0.14, 0.15, 0.22, 0.96)
            border.width: 1.5
            border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.8)
            opacity: bar.trayOverBar ? 1 : 0.5
            Image {
                anchors.centerIn: parent
                width: 16
                height: 16
                source: bar.trayDragIcon
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }

    }

    // full-screen power menu (opened from the control center's power button)
    // it's a full-screen transparent window that only exists while it's open (destroyed after the fade-out,
    // so dwm.exe gives its memory back)
    Component {
        id: powerComp
        PowerScreen {
            onFinished: {
                powerLoader.active = false
                bar.powerHold = false
                bar.page = ""              // now the control center retracts
            }
        }
    }
    Loader {
        id: powerLoader
        active: false
        sourceComponent: powerComp
        onLoaded: item.open()
        onActiveChanged: if (!active) bar.powerHold = false      // safety: never leave the hold on if the menu is gone
    }
    // the control center stays open while the power menu is up (its screenshot backdrop just includes it).
    // PowerScreen's `finished` (after the Cancel / Esc / click-away fade-out) releases the hold and retracts it.
    function openPower() {
        powerHold = true                   // control center stays open behind the power menu
        if (powerLoader.active && powerLoader.item) powerLoader.item.open()
        else powerLoader.active = true
    }

    Component {
        id: batteryIcon
        Item {
            width: 23
            height: 12
            Rectangle {
                width: 20
                height: 12
                radius: 3.5
                color: "transparent"
                border.width: 1.4
                border.color: Qt.rgba(1, 1, 1, 0.75)
                Rectangle {
                    x: 2.4
                    y: 2.4
                    height: parent.height - 4.8
                    radius: 1.5
                    width: Math.max(2, (parent.width - 4.8) * B.battery / 100)
                    color: B.battery <= 15 ? "#ff6b7a" : bar.blue
                    Behavior on width { SpringAnimation { spring: 4; damping: 0.5; epsilon: 0.1 } }
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
            }
            Rectangle { x: 20.6; y: 3.6; width: 2; height: 4.8; radius: 1; color: Qt.rgba(1, 1, 1, 0.75) }
        }
    }

    // ---- popup window ----
    // its own small transparent window, only shown while a popup is out. (a screen-sized transparent window makes
    // dwm.exe balloon to GBs while it animates, small ones don't.) it follows the popup's box (popX/popW/popH,
    // see fitPopup) and draws the same glass shape as the bar.
    Window {
        id: popup
        title: "Vapor Popup"
        visible: bar.panelActive && bar.shown
        color: "transparent"
        // the popup never takes keyboard focus, except while the control center has a text box open (Wi-Fi password)
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | ((ccPage.wantsKeyboard || bar.clockTyping) ? 0 : Qt.WindowDoesNotAcceptFocus)
        x: B.screenX + bar.popX
        y: B.screenY + bar.popY
        width: bar.popW
        height: bar.popH

        Glass {
            anchors.fill: parent
            originX: bar.popX
            originY: bar.popY
            visible: bar.reveal > 0.01 && !B.noGlass
            fillColor: bar.glassFill
            holeX: bar.frameNow
            holeY: bar.barNow
            holeW: bar.width - 2 * bar.frameNow
            holeH: B.fullH - bar.barNow - bar.frameNow
            holeR: bar.holeR
            panelX: bar.panelCX - bar.shapeW / 2
            panelW: bar.shapeW
            panelH: bar.panelActive ? bar.panelH : 0
            panelR: 22
            flare: bar.flare
            outline: bar.glassLine
        }

        Item {
            id: panel
            x: Math.round(bar.panelCX - width / 2 - bar.popX)
            y: bar.barH - bar.popY
            width: Math.round(Math.max(0, bar.shapeW))
            height: Math.round(Math.max(0, bar.panelH))
            visible: bar.panelActive
            opacity: Math.max(0, Math.min(1, (bar.panelH - 12) / Math.max(40, bar.wantH * 0.4)))

            HoverHandler {
                id: panelHover
                onHoveredChanged: if (hovered) { closeDelay.stop(); bar.trayHold = false; trayHoldTimer.stop() } else closeDelay.restart()
            }
            MouseArea { anchors.fill: parent }

                Item {
                    id: pages
                    anchors.fill: parent
                    clip: true

                    // ---- control center ----
                    ControlCenter {
                        id: ccPage
                        x: Math.round(parent.width - width - bar.ccOver)       // stays against the screen edge while the panel grows
                        opacity: bar.page === "control" ? 1 : 0
                        visible: opacity > 0.01
                        active: bar.page === "control"
                        onCloseRequested: bar.page = ""
                        onPowerRequested: bar.openPower()
                        Behavior on opacity { NumberAnimation { duration: 220 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveStandard } }
                    }

                    // ---- system tray ----
                    // every tray icon is listed here. drag one up onto the bar to pin it (drop it where you want it), along the bar
                    // to reorder, or down off the bar to unpin. click = open, right click = its menu, middle click / pin button = pin or unpin.
                    Item {
                        id: trayPage
                        readonly property int perRow: 5
                        readonly property real dpr: Screen.devicePixelRatio
                        readonly property int rows: Math.max(1, Math.ceil(B.trayCount / perRow))
                        readonly property real flowY: 34
                        readonly property real flowH: rows * 46 + (rows - 1) * 6
                        readonly property real h: flowY + flowH + 8 + 16 + 14
                        property string hoverTitle: ""
                        property real dragX: 0
                        property real dragY: 0
                        width: 292
                        height: h
                        x: (parent.width - width) / 2
                        opacity: bar.page === "tray" ? 1 : 0
                        visible: opacity > 0.01
                        Behavior on opacity { NumberAnimation { duration: 220 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveStandard } }
                        onVisibleChanged: if (!visible && !bar.trayDragFromBar) bar.trayDragging = false

                        function snap(v) { return Math.round(v * dpr) / dpr }

                        Text {
                            x: 18; y: 14
                            text: "TRAY"
                            color: bar.muted
                            font.family: bar.uiFont
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.2
                        }
                        Text {
                            visible: B.trayCount === 0
                            x: 18; y: trayPage.flowY + 15
                            text: "No tray icons found"
                            color: bar.muted
                            font.family: bar.uiFont
                            font.pixelSize: 12
                        }

                        Component {
                            id: trayTileComp
                            Item {
                                id: tt
                                required property string trayKey
                                required property string trayTitle
                                required property string iconUrl
                                required property bool pinned
                                width: 46
                                height: 46
                                opacity: (bar.trayDragging && bar.trayDragKey === trayKey) ? 0.3 : 1

                                Rectangle { anchors.fill: parent; radius: 16; color: Qt.rgba(1, 1, 1, 0.07) }
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 16
                                    color: bar.hoverColor
                                    opacity: ttMouse.containsMouse && !bar.trayDragging ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: 90 } }
                                }
                                Image {
                                    width: 24
                                    height: 24
                                    x: trayPage.snap((parent.width - width) / 2)
                                    y: trayPage.snap((parent.height - height) / 2)
                                    source: tt.iconUrl
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                    mipmap: true
                                    scale: ttMouse.pressed ? 0.88 : (ttMouse.containsMouse && !bar.trayDragging ? 1.1 : 1)
                                    Behavior on scale { SpringAnimation { spring: 14; damping: 0.5; epsilon: 0.005 } }
                                }
                                MouseArea {
                                    id: ttMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                                    cursorShape: bar.trayDragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                                    property real sx: 0
                                    property real sy: 0
                                    property bool moved: false
                                    onContainsMouseChanged: {
                                        if (bar.trayDragging) return
                                        if (containsMouse) trayPage.hoverTitle = tt.trayTitle
                                        else if (trayPage.hoverTitle === tt.trayTitle) trayPage.hoverTitle = ""
                                    }
                                    onPressed: (m) => { sx = m.x; sy = m.y; moved = false; bar.trayPressed = true }
                                    Component.onDestruction: if (pressed) { bar.trayPressed = false; if (moved) bar.trayDragging = false }
                                    onPositionChanged: (m) => {
                                        if (!(pressedButtons & Qt.LeftButton)) return
                                        if (!moved && Math.abs(m.x - sx) + Math.abs(m.y - sy) > 8) {
                                            moved = true
                                            trayPage.hoverTitle = ""
                                            bar.beginTrayDrag(tt.trayKey, tt.iconUrl, false, tt.pinned)
                                        }
                                        if (moved) {
                                            var p = ttMouse.mapToItem(trayPage, m.x, m.y)       // for the ghost inside the popup
                                            trayPage.dragX = p.x
                                            trayPage.dragY = p.y
                                            var g = ttMouse.mapToItem(null, m.x, m.y)           // popup window -> bar window coordinates
                                            bar.moveTrayDrag(bar.popX + g.x, bar.popY + g.y)
                                        }
                                    }
                                    onReleased: { bar.trayPressed = false; if (moved) bar.endTrayDrag(); else closeDelay.restart() }
                                    onCanceled: { moved = false; bar.trayDragging = false; bar.trayPressed = false; closeDelay.restart() }
                                    onClicked: (m) => {
                                        if (moved) return
                                        if (m.button === Qt.MiddleButton) { B.trayTogglePin(tt.trayKey); return }
                                        B.trayClick(tt.trayKey, m.button === Qt.RightButton ? "right" : "left")
                                        bar.holdTray()
                                    }
                                }
                                // pin button: shows on hover (and stays on pinned icons)
                                Rectangle {
                                    x: parent.width - 15
                                    y: -4
                                    width: 19
                                    height: 19
                                    radius: 9.5
                                    visible: opacity > 0.01
                                    opacity: !bar.trayDragging && (ttMouse.containsMouse || pinMouse.containsMouse || tt.pinned) ? 1 : 0
                                    color: tt.pinned ? bar.accent : Qt.rgba(0.12, 0.12, 0.18, 0.95)
                                    border.width: 1
                                    border.color: Qt.rgba(1, 1, 1, pinMouse.containsMouse ? 0.5 : 0.2)
                                    scale: pinMouse.pressed ? 0.85 : (pinMouse.containsMouse ? 1.12 : 1)
                                    Behavior on opacity { NumberAnimation { duration: 90 } }
                                    Behavior on scale { SpringAnimation { spring: 14; damping: 0.5; epsilon: 0.005 } }
                                    Text {
                                        anchors.centerIn: parent
                                        text: tt.pinned ? "\uE840" : "\uE718"
                                        font.family: "Segoe Fluent Icons"
                                        font.pixelSize: 10
                                        color: tt.pinned ? "#000000" : "white"
                                    }
                                    MouseArea {
                                        id: pinMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: B.trayTogglePin(tt.trayKey)
                                    }
                                }
                            }
                        }
                        Flow {
                            id: trayFlow
                            x: 14
                            y: trayPage.flowY
                            width: 264
                            spacing: 6
                            Repeater { model: trayModel; delegate: trayTileComp }
                        }

                        Text {
                            x: 18
                            y: trayPage.flowY + trayPage.flowH + 8
                            width: parent.width - 36
                            elide: Text.ElideRight
                            text: trayPage.hoverTitle !== "" ? trayPage.hoverTitle : "Drag to pin or unpin  \u00B7  click to open"
                            color: bar.muted
                            font.family: bar.uiFont
                            font.pixelSize: 11
                        }

                        // the icon that follows the pointer while it's still inside the popup
                        Rectangle {
                            visible: bar.trayDragging && !bar.trayDragFromBar && !bar.trayOverBar
                            z: 100
                            width: 46; height: 46
                            radius: 16
                            x: trayPage.dragX - 23
                            y: trayPage.dragY - 23
                            color: Qt.rgba(0.14, 0.15, 0.22, 0.96)
                            border.width: 1.5
                            border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.8)
                            scale: 1.08
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: bar.trayDragIcon
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                mipmap: true
                            }
                        }
                    }

                    // ---- media ----
                    Item {
                        width: 380
                        height: 176
                        x: (parent.width - width) / 2
                        opacity: bar.page === "media" ? 1 : 0
                        visible: opacity > 0.01
                        Behavior on opacity { NumberAnimation { duration: 220 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveStandard } }

                        // the whole widget scrolls to the previous / next playing app (the transport chips below handle the wheel too,
                        // so it works with the pointer anywhere on the popup)
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            onWheel: (w) => B.mediaCycle(w.angleDelta.y > 0 ? -1 : 1)
                        }

                        RoundImage { x: 18; y: 18; width: 112; height: 112; radius: 20; source: B.mediaArt }
                        Marquee {
                            x: 146; y: 18
                            maxWidth: 216
                            text: B.mediaTitle
                            color: "white"
                            fontFamily: bar.uiFont
                            pixelSize: 17
                            weight: Font.Bold
                            active: bar.page === "media"
                        }
                        Marquee {
                            x: 146; y: 42
                            maxWidth: 216
                            text: B.mediaArtist
                            color: Qt.rgba(1, 1, 1, 0.7)
                            fontFamily: bar.uiFont
                            pixelSize: 13
                            active: bar.page === "media"
                        }
                        Text {
                            x: 146; y: 62; width: 216
                            text: B.mediaSource
                            elide: Text.ElideRight
                            color: bar.lavender
                            font.family: bar.uiFont
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                        Row {
                            x: 142; y: 84
                            spacing: 6
                            Chip { icon: "\uE892"; iconColor: "white"; minWidth: 40; height: 40; onActivated: B.mediaPrev(); onWheeled: (d) => B.mediaCycle(d > 0 ? -1 : 1) }
                            Chip {
                                icon: B.mediaPlaying ? "\uE769" : "\uE768"
                                iconColor: "#000000"
                                iconSize: 19
                                fillColor: bar.accent
                                minWidth: 48
                                height: 40
                                onActivated: B.mediaPlayPause()
                                onWheeled: (d) => B.mediaCycle(d > 0 ? -1 : 1)
                            }
                            Chip { icon: "\uE893"; iconColor: "white"; minWidth: 40; height: 40; onActivated: B.mediaNext(); onWheeled: (d) => B.mediaCycle(d > 0 ? -1 : 1) }
                        }
                        // clickable / draggable progress bar, click to seek in the track shown
                        Item {
                            x: 18; y: 140; width: 344; height: 16
                            property bool dragging: false
                            property real dragFrac: 0.0
                            property real lastSent: -1
                            readonly property real frac: dragging ? dragFrac : B.mediaProgress

                            Rectangle { y: 6; width: 344; height: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.12) }
                            Rectangle {
                                y: 6
                                width: 344 * parent.frac
                                height: 4
                                radius: 2
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: bar.accent }
                                    GradientStop { position: 1; color: bar.lavender }
                                }
                                // one glide per poll tick (0.25 s): the bar eases into the next reading, no freeze
                                Behavior on width { enabled: !parent.dragging; NumberAnimation { duration: 250; easing.type: Easing.Linear } }
                            }
                            Rectangle {                         // knob, shown only while dragging
                                visible: parent.dragging
                                x: 344 * parent.frac - 5; y: 3
                                width: 10; height: 10; radius: 5
                                color: bar.accent
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onPressed: (mouse) => { parent.dragging = true; parent.lastSent = -1; parent.seek(mouse.x) }
                                onPositionChanged: (mouse) => parent.seek(mouse.x)
                                onReleased: parent.commit()
                                onCanceled: { parent.dragging = false; parent.lastSent = -1 }
                            }
                            function seek(px) {
                                if (!dragging) return
                                var f = Math.max(0, Math.min(1, px / 344))
                                dragFrac = f
                                if (Math.abs(f - lastSent) > 0.005) { lastSent = f; B.mediaSeek(f) }   // don't spam the app on every pixel
                            }
                            function commit() {
                                if (dragging) { lastSent = dragFrac; B.mediaSeek(dragFrac); dragging = false }
                            }
                        }
                        Text {
                            x: 18; y: 154
                            text: B.mediaTime
                            color: bar.muted
                            font.family: bar.uiFont
                            font.pixelSize: 11
                        }
                    }

                    // ---- volume ----
                    Item {
                        id: volPage
                        width: 300
                        height: 124
                        x: (parent.width - width) / 2
                        opacity: bar.page === "volume" ? 1 : 0
                        visible: opacity > 0.01
                        Behavior on opacity { NumberAnimation { duration: 220 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveStandard } }

                        Text {
                            x: 18; y: 14
                            text: "Volume"
                            color: bar.muted
                            font.family: bar.uiFont
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                        Text {
                            y: 10
                            anchors.right: parent.right
                            anchors.rightMargin: 18
                            text: B.muted ? "Muted" : B.volume + "%"
                            color: "white"
                            font.family: bar.uiFont
                            font.pixelSize: 20
                            font.weight: Font.Bold
                        }
                        Item {
                            id: slider
                            x: 18; y: 48
                            width: parent.width - 36
                            height: 24
                            property bool dragging: false
                            property real dragValue: 0
                            property real shownValue: dragging ? dragValue : (B.muted ? 0 : B.volume / 100)

                            Rectangle { y: 7; width: parent.width; height: 10; radius: 5; color: Qt.rgba(1, 1, 1, 0.12) }
                            Rectangle {
                                id: fill
                                y: 7
                                width: Math.max(10, slider.shownValue * parent.width)
                                height: 10
                                radius: 5
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: bar.accent }
                                    GradientStop { position: 1; color: bar.lavender }
                                }
                                Behavior on width { enabled: !slider.dragging; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                            }
                            Rectangle {
                                x: fill.width - 9
                                y: 3
                                width: 18
                                height: 18
                                radius: 9
                                color: "white"
                                scale: sliderMouse.pressed ? 1.25 : 1
                                Behavior on scale { SpringAnimation { spring: 6; damping: 0.4; epsilon: 0.005 } }
                            }
                            MouseArea {
                                id: sliderMouse
                                anchors.fill: parent
                                anchors.topMargin: -6
                                anchors.bottomMargin: -6
                                function setFrom(mx) {
                                    var v = Math.max(0, Math.min(1, mx / width))
                                    slider.dragValue = v
                                    B.setVolume(Math.round(v * 100))
                                }
                                onPressed: (m) => { slider.dragging = true; setFrom(m.x) }
                                onPositionChanged: (m) => { if (pressed) setFrom(m.x) }
                                onReleased: slider.dragging = false
                            }
                        }
                        Chip {
                            x: 14; y: 84
                            icon: B.muted ? "\uE74F" : "\uE767"
                            text: B.muted ? "Unmute" : "Mute"
                            showText: true
                            onActivated: B.toggleMute()
                        }

                        // output devices: click one to make it the default playback device
                        Flow {
                            id: outFlow
                            x: 14; y: 122
                            width: parent.width - 28
                            spacing: 6
                            Repeater {
                                model: B.outputs
                                Chip {
                                    required property var modelData
                                    readonly property bool isDefault: modelData.key === B.defaultOutput
                                    icon: modelData.kind === "headphones" ? "\uE7F6" : "\uE767"
                                    text: modelData.label
                                    showText: true
                                    iconColor: isDefault ? "white" : bar.blue
                                    textColor: isDefault ? "white" : bar.muted
                                    fillColor: isDefault ? Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.3) : "transparent"
                                    onActivated: B.setOutput(modelData.id)
                                }
                            }
                        }
                    }

                    // ---- clock: timer + alarms ----
                    Item {
                        id: clockPage
                        width: 330
                        readonly property real h: clkCol.implicitHeight + 30
                        height: h
                        x: (parent.width - width) / 2
                        opacity: bar.page === "clock" ? 1 : 0
                        visible: opacity > 0.01
                        Behavior on opacity { NumberAnimation { duration: 220 * bar.popSpeed; easing.type: Easing.BezierSpline; easing.bezierCurve: bar.curveStandard } }

                        property string tab: "timer"
                        property int tmH: 0
                        property int tmM: 5
                        property int tmS: 0
                        property int alH: 7
                        property int alM: 0
                        property bool alPM: false
                        property string alRep: "none"
                        property string alText: ""
                        property date pickDate: new Date()
                        property date viewMonth: new Date()
                        property bool showCal: false
                        readonly property int vy: viewMonth.getFullYear()
                        readonly property int vm: viewMonth.getMonth()
                        readonly property int firstDow: new Date(vy, vm, 1).getDay()
                        readonly property real pickTs: new Date(pickDate.getFullYear(), pickDate.getMonth(), pickDate.getDate(), (alH % 12) + (alPM ? 12 : 0), alM, 0, 0).getTime()
                        readonly property bool pickOk: pickTs > bar.now.getTime() + 1000 || alRep !== "none"
                        function sameDay(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate() }
                        function setDay(plus) {
                            var n = new Date()
                            pickDate = new Date(n.getFullYear(), n.getMonth(), n.getDate() + plus)
                            viewMonth = pickDate
                            showCal = false
                        }
                        // the reminder time always starts at the current time (the next minute, so it's never already in the past)
                        function resetToNow() {
                            var d = new Date(Date.now() + 2000)
                            d.setSeconds(0, 0)
                            d.setMinutes(d.getMinutes() + 1)
                            var h = d.getHours()
                            alPM = h >= 12
                            alH = (h % 12) === 0 ? 12 : h % 12
                            alM = d.getMinutes()
                            pickDate = new Date(d.getFullYear(), d.getMonth(), d.getDate())
                            viewMonth = pickDate
                            showCal = false
                        }
                        // editing an existing reminder: its values are loaded into this form, "Save changes" replaces it
                        property int editIdx: -1
                        function startEdit(i) {
                            var r = bar.alarms[i]
                            if (!r) return
                            var d = new Date(r.ts), h = d.getHours()
                            tab = "alarms"
                            alPM = h >= 12
                            alH = (h % 12) === 0 ? 12 : h % 12
                            alM = d.getMinutes()
                            pickDate = new Date(d.getFullYear(), d.getMonth(), d.getDate())
                            viewMonth = pickDate
                            showCal = false
                            alRep = r.rep
                            alText = r.t || ""
                            remInput.text = r.t || ""
                            editIdx = i
                        }
                        function cancelEdit() {
                            if (editIdx < 0) return
                            editIdx = -1
                            alText = ""
                            remInput.text = ""
                            alRep = "none"
                            resetToNow()
                        }
                        // number of time boxes being typed into (double-click), the popup keeps the keyboard while > 0
                        property int typingN: 0
                        function beginTyping() { typingN++; bar.clockTyping = true }
                        function endTyping() {
                            typingN = Math.max(0, typingN - 1)
                            if (typingN === 0 && !remInput.activeFocus) bar.clockTyping = false
                            closeDelay.restart()
                        }
                        function addReminder() {
                            if (!pickOk) return
                            var ts = pickTs
                            if (ts <= Date.now()) ts = bar.nextTs(ts, alRep)       // a repeating reminder set for a time that has passed starts at its next turn
                            if (editIdx >= 0) { bar.alarmReplace(editIdx, ts, alRep, alText.trim()); editIdx = -1 }
                            else bar.alarmAdd(ts, alRep, alText.trim())
                            alText = ""
                            remInput.text = ""
                            remInput.focus = false
                            if (typingN === 0) bar.clockTyping = false
                            resetToNow()
                        }
                        readonly property bool timerIdle: bar.timerEnd === 0 && bar.timerPausedLeft === 0

                        Column {
                            id: clkCol
                            x: 16
                            y: 14
                            width: 298
                            spacing: 10

                            // ---- time + date ----
                            Column {
                                width: parent.width
                                spacing: 0
                                Text {
                                    x: 2
                                    text: Qt.formatDateTime(bar.now, "hh:mm:ss AP")
                                    color: "white"
                                    font.family: bar.uiFont
                                    font.pixelSize: 26
                                    font.weight: Font.Bold
                                }
                                Text {
                                    x: 2
                                    text: Qt.formatDate(bar.now, "dddd, d MMMM yyyy")
                                    color: bar.muted
                                    font.family: bar.uiFont
                                    font.pixelSize: 11
                                }
                            }

                            // ---- ringing banner ----
                            Rectangle {
                                visible: bar.ringing !== ""
                                width: parent.width
                                height: 56
                                radius: 8
                                antialiasing: true
                                color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.25)
                                border.width: 1
                                border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.8)
                                Text {
                                    x: 12; y: 9
                                    textFormat: bar.noteFmt(bar.ringing)
                                    text: bar.noteHtml(bar.ringing)
                                    color: "white"
                                    font.family: bar.uiFont
                                    font.pixelSize: 13
                                }
                                Row {
                                    x: 12; y: 26
                                    spacing: 6
                                    ClkBtn { height: 24; text: "Dismiss"; primary: true; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.dismissRing() }
                                    ClkBtn { height: 24; text: "Snooze 5 min"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.snoozeRing() }
                                }
                            }

                            // ---- tabs ----
                            Row {
                                spacing: 6
                                ClkBtn { width: (298 - 6) / 2; text: "Timer"; icon: "\uE916"; selected: clockPage.tab === "timer"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.tab = "timer" }
                                ClkBtn { width: (298 - 6) / 2; text: "Reminders"; icon: "\uE787"; selected: clockPage.tab === "alarms"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: { if (clockPage.tab !== "alarms" && clockPage.editIdx < 0) clockPage.resetToNow(); clockPage.tab = "alarms" } }
                            }

                            // ---- timer: set it ----
                            Column {
                                visible: clockPage.tab === "timer" && clockPage.timerIdle
                                width: parent.width
                                spacing: 10
                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    spacing: 6
                                    ClkSpin { value: clockPage.tmH; max: 23; label: "HOURS"; accent: bar.accent; fontFamily: bar.uiFont; onEdited: (v) => clockPage.tmH = v; onEditStarted: clockPage.beginTyping(); onEditEnded: clockPage.endTyping() }
                                    ClkSpin { value: clockPage.tmM; label: "MINUTES"; accent: bar.accent; fontFamily: bar.uiFont; onEdited: (v) => clockPage.tmM = v; onEditStarted: clockPage.beginTyping(); onEditEnded: clockPage.endTyping() }
                                    ClkSpin { value: clockPage.tmS; label: "SECONDS"; accent: bar.accent; fontFamily: bar.uiFont; onEdited: (v) => clockPage.tmS = v; onEditStarted: clockPage.beginTyping(); onEditEnded: clockPage.endTyping() }
                                }
                                Row {
                                    spacing: 6
                                    Repeater {
                                        model: [1, 5, 10, 15, 30]
                                        ClkBtn {
                                            required property int modelData
                                            width: (298 - 4 * 6) / 5
                                            text: modelData + "m"
                                            accent: bar.accent; fontFamily: bar.uiFont
                                            onClicked: { clockPage.tmH = 0; clockPage.tmM = modelData; clockPage.tmS = 0 }
                                        }
                                    }
                                }
                                Row {
                                    spacing: 6
                                    ClkBtn {
                                        width: parent.parent.width - 96 - 6
                                        text: "Start timer"; icon: "\uE768"; primary: true
                                        accent: bar.accent; fontFamily: bar.uiFont
                                        onClicked: bar.timerStart(clockPage.tmH * 3600 + clockPage.tmM * 60 + clockPage.tmS)
                                    }
                                    ClkBtn {
                                        width: 96
                                        text: "Test alert"
                                        accent: bar.accent; fontFamily: bar.uiFont
                                        onClicked: bar.ring("Test alert", "This is how a timer or reminder looks")
                                    }
                                }
                            }

                            // ---- timer: running / paused ----
                            Column {
                                visible: clockPage.tab === "timer" && !clockPage.timerIdle
                                width: parent.width
                                spacing: 10
                                Text {
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: bar.fmtDur(bar.timerLeft)
                                    color: bar.timerEnd > 0 ? "white" : bar.muted
                                    font.family: bar.uiFont
                                    font.pixelSize: 40
                                    font.weight: Font.Bold
                                }
                                Rectangle {
                                    width: parent.width
                                    height: 8
                                    radius: 4
                                    antialiasing: true
                                    color: Qt.rgba(1, 1, 1, 0.12)
                                    Rectangle {
                                        height: parent.height
                                        radius: 4
                                        antialiasing: true
                                        width: parent.width * (bar.timerTotal > 0 ? bar.timerLeft / bar.timerTotal : 0)
                                        color: bar.accent
                                        Behavior on width { NumberAnimation { duration: 900 } }
                                    }
                                }
                                Row {
                                    spacing: 6
                                    ClkBtn {
                                        width: (298 - 12) / 3
                                        text: bar.timerEnd > 0 ? "Pause" : "Resume"; icon: bar.timerEnd > 0 ? "\uE769" : "\uE768"; primary: true
                                        accent: bar.accent; fontFamily: bar.uiFont
                                        onClicked: bar.timerTogglePause()
                                    }
                                    ClkBtn { width: (298 - 12) / 3; text: "+1 min"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.timerAdd(60) }
                                    ClkBtn { width: (298 - 12) / 3; text: "Cancel"; icon: "\uE711"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.timerCancel() }
                                }
                            }

                            // ---- reminders ----
                            Column {
                                visible: clockPage.tab === "alarms"
                                width: parent.width
                                spacing: 10

                                // ---- your reminders ----
                                Item {
                                    width: parent.width
                                    height: bar.alarms.length === 0 ? 40 : Math.min(bar.alarms.length * 48, 192)
                                    clip: true
                                    Text {
                                        visible: bar.alarms.length === 0
                                        anchors.centerIn: parent
                                        text: "No reminders yet"
                                        color: bar.muted
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                    }
                                    Flickable {
                                        anchors.fill: parent
                                        contentWidth: width
                                        contentHeight: alarmCol.height
                                        boundsBehavior: Flickable.StopAtBounds
                                        Column {
                                            id: alarmCol
                                            width: parent.width
                                            spacing: 4
                                            Repeater {
                                                model: bar.alarms
                                                Rectangle {
                                                    id: arow
                                                    required property var modelData
                                                    required property int index
                                                    readonly property bool done: !modelData.on && modelData.rep === "none" && modelData.ts <= bar.now.getTime()
                                                    width: alarmCol.width
                                                    height: 44
                                                    radius: 8
                                                    antialiasing: true
                                                    color: Qt.rgba(1, 1, 1, 0.06)
                                                    Text {
                                                        x: 12
                                                        y: 6
                                                        width: parent.width - 12 - 150
                                                        elide: Text.ElideRight
                                                        textFormat: bar.noteFmt(arow.modelData.t)
                                                        text: arow.modelData.t && arow.modelData.t !== "" ? bar.noteHtml(arow.modelData.t) : "Reminder"
                                                        color: arow.modelData.on ? "white" : Qt.rgba(1, 1, 1, 0.45)
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 13
                                                    }
                                                    Text {
                                                        x: 12
                                                        y: 26
                                                        width: parent.width - 12 - 150
                                                        elide: Text.ElideRight
                                                        text: arow.done ? "done" : bar.fmtReminder(arow.modelData.ts, arow.modelData.rep)
                                                        color: Qt.rgba(1, 1, 1, 0.55)
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 10
                                                    }
                                                    // on / off: on = filled with the accent + "ON", off = empty outline + "OFF"
                                                    Rectangle {
                                                        id: swTrack
                                                        x: parent.width - 138
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 52
                                                        height: 24
                                                        radius: 12
                                                        antialiasing: true
                                                        readonly property color ink: ((0.299 * bar.accent.r + 0.587 * bar.accent.g + 0.114 * bar.accent.b) > 0.5) ? "#14141c" : "#ffffff"
                                                        color: arow.modelData.on ? bar.accent : Qt.rgba(1, 1, 1, 0.06)
                                                        border.width: 1.5
                                                        border.color: arow.modelData.on ? bar.accent : Qt.rgba(1, 1, 1, 0.35)
                                                        Behavior on color { ColorAnimation { duration: 110 } }
                                                        Text {
                                                            anchors.verticalCenter: parent.verticalCenter
                                                            x: arow.modelData.on ? 9 : parent.width - width - 9
                                                            text: arow.modelData.on ? "ON" : "OFF"
                                                            color: arow.modelData.on ? swTrack.ink : Qt.rgba(1, 1, 1, 0.5)
                                                            font.family: bar.uiFont
                                                            font.pixelSize: 9
                                                            font.weight: Font.Bold
                                                        }
                                                        Rectangle {
                                                            y: 4
                                                            width: 16
                                                            height: 16
                                                            radius: 8
                                                            antialiasing: true
                                                            color: arow.modelData.on ? swTrack.ink : Qt.rgba(1, 1, 1, 0.55)
                                                            x: arow.modelData.on ? parent.width - width - 4 : 4
                                                            Behavior on x { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                                                        }
                                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmToggle(arow.index) }
                                                    }
                                                    // edit: loads this reminder into the form below
                                                    Rectangle {
                                                        x: parent.width - 78
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 22
                                                        height: 22
                                                        radius: 6
                                                        antialiasing: true
                                                        color: Qt.rgba(1, 1, 1, editMouse.containsMouse || clockPage.editIdx === arow.index ? 0.16 : 0.08)
                                                        Text { anchors.centerIn: parent; text: "\uE70F"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: clockPage.editIdx === arow.index ? bar.accent : "white" }
                                                        MouseArea { id: editMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: clockPage.startEdit(arow.index) }
                                                    }
                                                    // repeat: once -> every day -> every week -> every month
                                                    Rectangle {
                                                        x: parent.width - 52
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 22
                                                        height: 22
                                                        radius: 6
                                                        antialiasing: true
                                                        color: Qt.rgba(1, 1, 1, repMouse.containsMouse ? 0.16 : 0.08)
                                                        Text { anchors.centerIn: parent; text: "\uE895"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: arow.modelData.rep !== "none" ? bar.accent : Qt.rgba(1, 1, 1, 0.5) }
                                                        MouseArea { id: repMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmRepeat(arow.index) }
                                                    }
                                                    Rectangle {
                                                        x: parent.width - 26
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 22
                                                        height: 22
                                                        radius: 6
                                                        antialiasing: true
                                                        color: Qt.rgba(1, 1, 1, delMouse.containsMouse ? 0.16 : 0.08)
                                                        Text { anchors.centerIn: parent; text: "\uE74D"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "#ff6b7a" }
                                                        MouseArea { id: delMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmDelete(arow.index) }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.1) }

                                // ---- new reminder: text ----
                                Rectangle {
                                    id: remBox
                                    width: parent.width
                                    height: 36
                                    radius: 10
                                    antialiasing: true
                                    color: Qt.rgba(0, 0, 0, 0.28)
                                    border.width: 1
                                    border.color: remInput.activeFocus ? bar.accent : Qt.rgba(1, 1, 1, 0.14)
                                    Behavior on border.color { ColorAnimation { duration: 90 } }
                                    // live preview: the styled copy of the text, right in the box
                                    LiveLine { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; input: remInput }
                                    TextInput {
                                        id: remInput
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: "transparent"
                                        selectedTextColor: "transparent"
                                        selectionColor: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.35)
                                        cursorDelegate: Rectangle { width: 1.5; color: "white"; opacity: remInput.activeFocus ? 1 : 0 }
                                        selectByMouse: true
                                        clip: true
                                        maximumLength: 80
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                        onTextEdited: clockPage.alText = text
                                        Keys.onPressed: (e) => { if (sidePanel.autoClose(remInput, e)) { clockPage.alText = remInput.text; e.accepted = true } }
                                        onAccepted: clockPage.addReminder()
                                        onActiveFocusChanged: if (!activeFocus && clockPage.typingN === 0) bar.clockTyping = false
                                    }
                                    Text {
                                        visible: remInput.text === ""
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 12
                                        text: "Remind me to..."
                                        color: Qt.rgba(1, 1, 1, 0.38)
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !remInput.activeFocus
                                        cursorShape: Qt.IBeamCursor
                                        onClicked: { bar.clockTyping = true; remFocus.restart() }
                                    }
                                    Timer {
                                        id: remFocus
                                        interval: 90
                                        onTriggered: {
                                            if (remBox.Window.window) remBox.Window.window.requestActivate()
                                            remInput.forceActiveFocus()
                                        }
                                    }
                                }

                                // ---- new reminder: day ----
                                Row {
                                    spacing: 6
                                    ClkBtn { width: 64; text: "Today"; selected: clockPage.sameDay(clockPage.pickDate, bar.now); accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.setDay(0) }
                                    ClkBtn { width: 88; text: "Tomorrow"; selected: clockPage.sameDay(clockPage.pickDate, new Date(bar.now.getFullYear(), bar.now.getMonth(), bar.now.getDate() + 1)); accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.setDay(1) }
                                    ClkBtn { width: 298 - 64 - 88 - 12; text: Qt.formatDate(clockPage.pickDate, "ddd d MMM yyyy"); icon: "\uE787"; selected: clockPage.showCal; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.showCal = !clockPage.showCal }
                                }

                                // ---- date picker (month grid), folded until you press the date button ----
                                Item {
                                    width: parent.width
                                    height: clockPage.showCal ? calCol.implicitHeight : 0
                                    visible: height > 0.5
                                    clip: true
                                    Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                                    Column {
                                        id: calCol
                                        width: parent.width
                                        spacing: 4
                                        Item {
                                            width: parent.width
                                            height: 30
                                            Text {
                                                x: 2
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: Qt.formatDate(clockPage.viewMonth, "MMMM yyyy")
                                                color: "white"
                                                font.family: bar.uiFont
                                                font.pixelSize: 13
                                                font.weight: Font.Bold
                                            }
                                            Row {
                                                anchors.right: parent.right
                                                anchors.verticalCenter: parent.verticalCenter
                                                spacing: 4
                                                ClkBtn { width: 30; height: 26; icon: "\uE76B"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.viewMonth = new Date(clockPage.vy, clockPage.vm - 1, 1) }
                                                ClkBtn { width: 30; height: 26; icon: "\uE76C"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.viewMonth = new Date(clockPage.vy, clockPage.vm + 1, 1) }
                                            }
                                        }
                                        Row {
                                            Repeater {
                                                model: ["S", "M", "T", "W", "T", "F", "S"]
                                                Text {
                                                    required property string modelData
                                                    width: 298 / 7
                                                    horizontalAlignment: Text.AlignHCenter
                                                    text: modelData
                                                    color: bar.muted
                                                    font.family: bar.uiFont
                                                    font.pixelSize: 10
                                                    font.weight: Font.DemiBold
                                                }
                                            }
                                        }
                                        Grid {
                                            columns: 7
                                            Repeater {
                                                model: 42
                                                Item {
                                                    id: dayCell
                                                    required property int index
                                                    readonly property date d: new Date(clockPage.vy, clockPage.vm, index - clockPage.firstDow + 1)
                                                    readonly property bool past: d.getTime() < new Date(bar.now.getFullYear(), bar.now.getMonth(), bar.now.getDate()).getTime()
                                                    readonly property bool picked: clockPage.sameDay(d, clockPage.pickDate)
                                                    readonly property bool today: clockPage.sameDay(d, bar.now)
                                                    width: 298 / 7
                                                    height: 32
                                                    Rectangle {
                                                        anchors.centerIn: parent
                                                        width: 32
                                                        height: 28
                                                        radius: 8
                                                        antialiasing: true
                                                        color: dayCell.picked ? bar.accent : (dayMouse.containsMouse && !dayCell.past ? Qt.rgba(1, 1, 1, 0.14) : "transparent")
                                                        border.width: dayCell.today && !dayCell.picked ? 1 : 0
                                                        border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.8)
                                                    }
                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: dayCell.d.getDate()
                                                        color: dayCell.picked ? ((0.299 * bar.accent.r + 0.587 * bar.accent.g + 0.114 * bar.accent.b) > 0.5 ? "#14141c" : "#ffffff")
                                                             : dayCell.past ? Qt.rgba(1, 1, 1, 0.22)
                                                             : (dayCell.d.getMonth() === clockPage.vm ? "white" : Qt.rgba(1, 1, 1, 0.4))
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 12
                                                        font.weight: dayCell.picked || dayCell.today ? Font.Bold : Font.Normal
                                                    }
                                                    MouseArea {
                                                        id: dayMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        enabled: !dayCell.past
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: { clockPage.pickDate = dayCell.d; clockPage.showCal = false }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                // ---- new reminder: time + repeat + add ----
                                Row {
                                    spacing: 8
                                    Row {
                                        spacing: 2
                                        ClkSpin { value: clockPage.alH; min: 1; max: 12; label: "HOUR"; accent: bar.accent; fontFamily: bar.uiFont; onEdited: (v) => clockPage.alH = v; onEditStarted: clockPage.beginTyping(); onEditEnded: clockPage.endTyping() }
                                        ClkSpin { value: clockPage.alM; label: "MIN"; accent: bar.accent; fontFamily: bar.uiFont; onEdited: (v) => clockPage.alM = v; onEditStarted: clockPage.beginTyping(); onEditEnded: clockPage.endTyping() }
                                    }
                                    Column {
                                        spacing: 6
                                        topPadding: 4
                                        Row {
                                            spacing: 6
                                            ClkBtn { width: 72; text: "AM"; selected: !clockPage.alPM; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.alPM = false }
                                            ClkBtn { width: 72; text: "PM"; selected: clockPage.alPM; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.alPM = true }
                                        }
                                        ClkBtn { width: 150; text: bar.repLabel(clockPage.alRep); icon: "\uE895"; selected: clockPage.alRep !== "none"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.alRep = bar.nextRep(clockPage.alRep) }
                                        ClkBtn { width: 150; text: clockPage.editIdx >= 0 ? "Save changes" : "Add reminder"; icon: clockPage.editIdx >= 0 ? "\uE74E" : "\uE710"; primary: clockPage.pickOk; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.addReminder() }
                                        ClkBtn { visible: clockPage.editIdx >= 0; width: 150; text: "Cancel edit"; icon: "\uE711"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: clockPage.cancelEdit() }
                                    }
                                }
                                Text {
                                    visible: !clockPage.pickOk
                                    width: parent.width
                                    text: "That time has already passed. Pick a later time or day."
                                    wrapMode: Text.WordWrap
                                    color: "#ffb86b"
                                    font.family: bar.uiFont
                                    font.pixelSize: 10
                                }
                            }
                        }
                    }
                }
        }
    }

    // ---- side panel ----
    // hover the slim handle in the middle of the right screen edge and a card slides out with two tabs: every
    // reminder (and the running timer), and a notes pad (saved in settings.json through the backend). the hover
    // handle lives in the right frame window and the card sits next to the frame, never on top of it, so no
    // window overlaps another one's glass outline.
    property bool sideWant: false          // mouse is on the edge handle or on the panel
    property bool sideTyping: false        // a notes box has the keyboard (the panel window then accepts focus)
    property string sideTab: "reminders"   // reminders | notes
    property real sideP: 0                 // 0 = tucked away, 1 = fully out
    readonly property bool sideShow: sideWant && shown && page !== "control" && !trayDragging
    readonly property int sideW: 330
    readonly property int sideH: Math.max(300, Math.min(500, B.fullH - 160))
    readonly property bool timerActive: timerEnd > 0 || timerPausedLeft > 0
    property var notes: []                 // [{title, t: text, ts: epoch ms}], newest first

    // geometry of the side card right now (the card, the frame's outline gap and the window all read these)
    readonly property real sidePv: Math.min(1, Math.max(0, sideP))
    readonly property real sideWinH: sideH + 2 * flare
    readonly property real sideCwNow: sidePv * sideW
    readonly property real sideChNow: 96 + (sideH - 96) * Math.min(1, sidePv * 1.25)
    readonly property real sideCrNow: Math.max(0, Math.min(22, sideCwNow / 2, sideChNow / 2))
    readonly property real sideFfNow: Math.max(0, Math.min(flare, sideCwNow - sideCrNow))
    readonly property real sideMidY: Math.round((B.fullH - sideWinH) / 2) + sideWinH / 2
    readonly property real sideCutY0: (sideP > 0.002 && sideCwNow > 2) ? sideMidY - sideChNow / 2 - sideFfNow : 0
    readonly property real sideCutY1: (sideP > 0.002 && sideCwNow > 2) ? sideMidY + sideChNow / 2 + sideFfNow : 0

    onSideShowChanged: {
        sideAnim.stop()
        sideAnim.to = sideShow ? 1 : 0
        sideAnim.duration = (sideShow ? 380 : 240) * popSpeed
        sideAnim.easing.bezierCurve = sideShow ? curveSpatial : curveExit
        sideAnim.start()
    }
    onShownChanged: if (!shown) { sideWant = false; sideTyping = false; dockWant = false }
    NumberAnimation { id: sideAnim; target: bar; property: "sideP"; easing.type: Easing.BezierSpline }
    Timer { id: sideOpenDelay; interval: 110; onTriggered: bar.sideWant = true }
    Timer { id: sideCloseDelay; interval: 60; onTriggered: if (!edgeR.handleHovered && !sidePanelHover.hovered && !sidePanel.composing) bar.sideWant = false }
    // panel folded away: the note editor closes with it (unsaved text is dropped) and "New note" has to be pressed again
    onSideWantChanged: if (!sideWant) { sidePanel.closeComposer(); sideTyping = false }
    // a click / focus loss somewhere that isn't the panel or its edge handle: this is what closes the panel while a note is open
    function sideOutside() {
        if (sideWant && sidePanel.composing && !sidePanelHover.hovered && !edgeR.handleHovered) sideWant = false
    }
    function sideHover(on) {
        if (on) { sideCloseDelay.stop(); if (!sideWant) sideOpenDelay.restart() }
        else { sideOpenDelay.stop(); sideCloseDelay.restart() }
    }

    // ---- notes ----
    function notesLoad() {
        try {
            var l = JSON.parse(B.notesLoad() || "[]")
            notes = Array.isArray(l) ? l : []
        } catch (e) { notes = [] }
    }
    function notesSave() { B.notesSave(JSON.stringify(notes)) }
    // idx >= 0 replaces that note (it moves to the top), returns false when title and text are both empty
    function noteSave(title, text, idx) {
        var h = (title || "").trim(), t = (text || "").trim()
        if (h === "" && t === "") return false
        var a = notes.slice()
        if (idx >= 0 && idx < a.length) a.splice(idx, 1)
        a.unshift({ title: h, t: t, ts: Date.now() })
        notes = a
        notesSave()
        return true
    }
    function noteDelete(i) {
        var a = notes.slice()
        a.splice(i, 1)
        notes = a
        notesSave()
    }
    // same text with the markup removed (for places that can't show styled text)
    function noteText(s) {
        return String(s === undefined || s === null ? "" : s).replace(/\{\/?([a-zA-Z]*|#[0-9a-fA-F]{3,8})\}/g, "").replace(/\*+/g, "").replace(/~~/g, "")
    }
    // note text -> Qt styled text:  **bold**   *italic*   {red}coloured{/red}  ({/} also closes, names or {#ff8800} work)
    readonly property var noteColors: ({ red: "#ff6b7a", green: "#7be08f", blue: "#6bb8ff", yellow: "#ffd86b", orange: "#ffb86b", pink: "#ff8fd0",
                                         purple: "#b79bff", cyan: "#6be3e3", white: "#ffffff", gray: "#9aa0b4", grey: "#9aa0b4" })
    function noteHtml(s) {
        var t = String(s === undefined || s === null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        var names = noteColors
        var open = 0
        t = t.replace(/\{(\/?)([a-zA-Z]*|#[0-9a-fA-F]{3,8})\}/g, function (m, close, name) {
            if (close) { if (open > 0) { open--; return "</font>" } return "" }
            var c = names[name.toLowerCase()] || (name.charAt(0) === "#" ? name : "")
            if (!c) return m
            open++
            return "<font color=\"" + c + "\">"
        })
        while (open-- > 0) t += "</font>"
        t = t.replace(/~~([\s\S]+?)~~/g, "<s>$1</s>")
        t = t.replace(/\*\*([\s\S]+?)\*\*/g, "<b>$1</b>")
        t = t.replace(/\*([^*\n]+?)\*/g, "<i>$1</i>")
        return t.replace(/\n/g, "<br>")
    }
    // Qt's StyledText has no reliable strike-through tag, so text that has ~~strike~~ in it is drawn as RichText
    // (which does). everything else keeps the StyledText it always had (so elide still works)
    function noteFmt(s) {
        return /~~[\s\S]+?~~/.test(String(s === undefined || s === null ? "" : s)) ? Text.RichText : Text.StyledText
    }

    // ---- live preview inside the text box (like Discord) ----
    // the very same characters as typed, with the markers (** * {red} {/red}) dimmed and the bold / italic / colour
    // applied. the real input on top has transparent text, so you only see this layer. it lines up with the cursor
    // because CaskaydiaCove is monospaced (bold and italic keep the same character width).
    function liveHtml(s) {
        var dim = "#6f7590"
        function D(x) { return "<span style=\"color:" + dim + "\">" + x + "</span>" }
        var t = String(s === undefined || s === null ? "" : s).replace(/[\u0001-\u0003]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        var open = 0
        t = t.replace(/\{(\/?)([a-zA-Z]*|#[0-9a-fA-F]{3,8})\}/g, function (m, close, name) {
            if (close) { if (open > 0) { open--; return "</span>" + D(m) } return D(m) }
            var c = noteColors[name.toLowerCase()] || (name.charAt(0) === "#" ? name : "")
            if (!c) return m
            open++
            return D(m) + "<span style=\"color:" + c + "\">"
        })
        while (open-- > 0) t += "</span>"
        t = t.replace(/~~([\s\S]+?)~~/g, "\u0003<s>$1</s>\u0003")
        t = t.replace(/\*\*([\s\S]+?)\*\*/g, "\u0001<b>$1</b>\u0001")
        t = t.replace(/\*([^*\n]+?)\*/g, "\u0002<i>$1</i>\u0002")
        t = t.replace(/\u0001/g, D("**")).replace(/\u0002/g, D("*")).replace(/\u0003/g, D("~~"))
        return "<div style=\"white-space:pre-wrap\">" + t + "</div>"
    }
    // ---- a card that grows out of a screen edge ----
    // rounded on the free side, flat on the frame side, with a concave join (radius ff) at both ends where it meets
    // the frame. drawn on a Canvas (one path: fill + outline). bottomEdge false = attached to the right edge of this
    // item, true = attached to its bottom edge. cw = how far the card sticks out from the frame, cl = its length
    // along the frame (centred), cr = rounded corners
    component EdgeCard: Canvas {
        id: ec
        property bool bottomEdge: false
        property real cw: 0
        property real cl: 0
        property real cr: 0
        property real ff: 0
        property color fill: "black"
        property color line: "white"
        onCwChanged: requestPaint()
        onClChanged: requestPaint()
        onCrChanged: requestPaint()
        onFfChanged: requestPaint()
        onFillChanged: requestPaint()
        onLineChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.clearRect(0, 0, width, height)
            if (width < 1 || height < 1 || cw < 1 || cl < 1) return
            var W = bottomEdge ? height : width         // across: from the open side to the frame
            var L = bottomEdge ? width : height         // along the frame
            if (bottomEdge) { c.translate(width, 0); c.rotate(Math.PI / 2) }
            var Y0 = (L - cl) / 2, Y1 = Y0 + cl, X0 = W - cw
            var f = Math.max(0, ff), P = Math.PI
            // i = 0: the glass edge (fill), i = 0.5: the hairline, kept inside the glass (same as Glass.qml).
            // the side that touches the frame is never stroked, so the card melts into the frame.
            var trace = function (i) {
                var r = Math.max(0, cr - i)
                var y0 = Y0 + i, y1 = Y1 - i, x0 = X0 + i
                c.beginPath()
                c.moveTo(W + i, Y0 - f)
                c.arc(W - f, Y0 - f, f + i, 0, P / 2, false)
                c.lineTo(x0 + r, y0)
                c.arc(x0 + r, y0 + r, r, 3 * P / 2, P, true)
                c.lineTo(x0, y1 - r)
                c.arc(x0 + r, y1 - r, r, P, P / 2, true)
                c.lineTo(W - f, y1)
                c.arc(W - f, Y1 + f, f + i, 3 * P / 2, 2 * P, false)
            }
            trace(0)
            c.fillStyle = fill
            c.fill()
            trace(0.5)
            c.strokeStyle = line
            c.lineWidth = 1
            c.stroke()
        }
    }
    // styled layer that sits under a transparent-text input (src = the TextEdit / TextInput it mirrors)
    component LiveText: Text {
        property var src: null
        textFormat: Text.RichText
        text: bar.liveHtml(src ? src.text : "")
        color: "white"
        font.family: bar.uiFont
        font.pixelSize: 12
    }
    // same for a one-line TextInput, it follows the input's sideways scroll when the text is longer than the box
    component LiveLine: Item {
        id: ll
        property var input: null
        property real px: 0
        clip: true
        Connections {
            target: ll.input
            function onCursorRectangleChanged() { ll.px = ll.input.positionToRectangle(0).x }
            function onTextChanged() { ll.px = ll.input.positionToRectangle(0).x }
        }
        LiveText {
            src: ll.input
            x: ll.px
            anchors.verticalCenter: parent.verticalCenter
            wrapMode: Text.NoWrap
        }
    }

    // ---- the panel window (its right 8 px are an empty margin touching the frame, so the mouse never "falls off") ----
    Window {
        id: sideWin
        title: "Vapor Side Panel"
        visible: bar.sideP > 0.002 && bar.shown
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | (bar.sideTyping ? 0 : Qt.WindowDoesNotAcceptFocus)
        // while a note is being edited the panel ignores the mouse leaving; clicking somewhere else (the window
        // loses the keyboard) is what closes it. the short timer skips the focus flicker when the window flags change
        onActiveChanged: if (!active && sidePanel.composing) outsideClick.restart()
        Timer { id: outsideClick; interval: 220; onTriggered: if (!sideWin.active) bar.sideOutside() }
        width: bar.sideW                         // its right edge sits right on the frame's inner edge
        height: bar.sideH + 2 * bar.flare        // + room for the two concave joins above and below the card
        x: B.screenX + B.screenW - bar.frameW - width
        y: B.screenY + Math.round((B.fullH - height) / 2)

        Item {
            id: sideRoot
            anchors.fill: parent
            HoverHandler { id: sidePanelHover; onHoveredChanged: bar.sideHover(hovered) }

            // ---- the card: one shape that grows out of the right frame, with concave joins (like the bar's popups) ----
            readonly property real cw: bar.sideCwNow                  // card width right now
            readonly property real ch: bar.sideChNow                  // card height, grows from the handle
            readonly property real y0: (height - ch) / 2
            readonly property real y1: y0 + ch
            readonly property real cr: bar.sideCrNow                  // rounded corners (free side)
            readonly property real ff: bar.sideFfNow                  // join radius at the frame
            EdgeCard { anchors.fill: parent; cw: sideRoot.cw; cl: sideRoot.ch; cr: sideRoot.cr; ff: sideRoot.ff; fill: bar.glassFill; line: bar.glassLine }

            // content is clipped to the card while it grows
            Item {
                id: sideClip
                x: sideRoot.width - sideRoot.cw
                y: sideRoot.y0
                width: sideRoot.cw
                height: sideRoot.ch
                clip: true

                Item {
                    id: sidePanel
                    width: bar.sideW
                    height: bar.sideH
                    x: sideClip.width - bar.sideW          // stays against the frame while the card grows out of it
                    y: -(bar.sideH - sideClip.height) / 2
                    opacity: Math.min(1, bar.sideP * 2)
                    readonly property real bodyH: height - 14 - 32 - 10 - 14
                    property int editIndex: -1
                    property bool composing: false         // title + text editor is open (the + button opens it)
                    property var focusTarget: null

                    // VS Code style: typing the } of {red} (or {#ff8800}) also writes {/red} and leaves the cursor between them
                    function autoClose(ed, e) {
                        if (e.text !== "}" || ed.selectedText !== "") return false
                        var pos = ed.cursorPosition
                        var m = /\{([a-zA-Z]+|#[0-9a-fA-F]{3,8})$/.exec(ed.text.substring(0, pos))
                        if (!m) return false
                        var key = m[1]
                        if (!(bar.noteColors.hasOwnProperty(key.toLowerCase()) || key.charAt(0) === "#")) return false
                        var ins = "}{/" + key + "}"
                        var room = (ed.maximumLength !== undefined ? ed.maximumLength : 1000000) - ed.length
                        if (room < ins.length) return false
                        ed.insert(pos, ins)
                        ed.cursorPosition = pos + 1
                        return true
                    }
                    function focusInput(t) { bar.sideTyping = true; focusTarget = t; noteFocus.restart() }
                    function newNote() {
                        titleEdit.text = ""
                        noteEdit.text = ""
                        editIndex = -1
                        composing = true
                        focusInput(titleEdit)
                    }
                    // clears the editor and folds it away again
                    function closeComposer() {
                        titleEdit.text = ""
                        noteEdit.text = ""
                        editIndex = -1
                        composing = false
                        typingCheck.restart()
                    }
                    function saveNote() {
                        if (bar.noteSave(titleEdit.text, noteEdit.text, editIndex)) closeComposer()
                    }
                    function editNote(i) {
                        var n = bar.notes[i]
                        titleEdit.text = n.title || ""
                        noteEdit.text = n.t || ""
                        editIndex = i
                        composing = true
                        focusInput(noteEdit)
                    }
                    Timer {
                        id: noteFocus
                        interval: 90
                        onTriggered: {
                            sideWin.requestActivate()
                            if (sidePanel.focusTarget) sidePanel.focusTarget.forceActiveFocus()
                        }
                    }
                    // moving from the title box to the text box briefly drops focus, so only hand the keyboard back after a pause
                    Timer {
                        id: typingCheck
                        interval: 160
                        onTriggered: if (!titleEdit.activeFocus && !noteEdit.activeFocus) { bar.sideTyping = false; sideCloseDelay.restart(); if (composing) bar.sideOutside() }
                    }

                    MouseArea { anchors.fill: parent }

                    Column {
                        x: 16
                        y: 14
                        width: parent.width - 16 - 14
                        spacing: 10

                        Row {
                            spacing: 6
                            ClkBtn { width: (300 - 6) / 2; text: "Reminders" + (bar.alarms.length > 0 ? "  " + bar.alarms.length : ""); icon: "\uE787"; selected: bar.sideTab === "reminders"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.sideTab = "reminders" }
                            ClkBtn { width: (300 - 6) / 2; text: "Notes" + (bar.notes.length > 0 ? "  " + bar.notes.length : ""); icon: "\uE70F"; selected: bar.sideTab === "notes"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.sideTab = "notes" }
                        }

                        // ---- tab 1: running timer + every reminder ----
                        Item {
                            visible: bar.sideTab === "reminders"
                            width: parent.width
                            height: sidePanel.bodyH
                            clip: true
                            Text {
                                visible: bar.alarms.length === 0 && !bar.timerActive
                                anchors.centerIn: parent
                                text: "No reminders or timers yet"
                                color: bar.muted
                                font.family: bar.uiFont
                                font.pixelSize: 12
                            }
                            Flickable {
                                anchors.fill: parent
                                contentWidth: width
                                contentHeight: sideAlarmCol.height
                                boundsBehavior: Flickable.StopAtBounds
                                Column {
                                    id: sideAlarmCol
                                    width: parent.width
                                    spacing: 4

                                    // ---- running / paused timer ----
                                    Rectangle {
                                        visible: bar.timerActive
                                        width: sideAlarmCol.width
                                        height: 78
                                        radius: 8
                                        antialiasing: true
                                        color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.14)
                                        border.width: 1
                                        border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.5)
                                        Text {
                                            x: 12; y: 8
                                            text: bar.timerEnd > 0 ? "TIMER" : "TIMER  \u00B7  PAUSED"
                                            color: bar.muted
                                            font.family: bar.uiFont
                                            font.pixelSize: 9
                                            font.weight: Font.DemiBold
                                            font.letterSpacing: 1.2
                                        }
                                        Text {
                                            x: 12; y: 20
                                            text: bar.fmtDur(bar.timerLeft)
                                            color: bar.timerEnd > 0 ? "white" : bar.muted
                                            font.family: bar.uiFont
                                            font.pixelSize: 26
                                            font.weight: Font.Bold
                                        }
                                        Row {
                                            anchors.right: parent.right
                                            anchors.rightMargin: 10
                                            y: 14
                                            spacing: 4
                                            ClkBtn { width: 34; height: 28; icon: bar.timerEnd > 0 ? "\uE769" : "\uE768"; primary: true; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.timerTogglePause() }
                                            ClkBtn { width: 34; height: 28; text: "+1m"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.timerAdd(60) }
                                            ClkBtn { width: 34; height: 28; icon: "\uE711"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.timerCancel() }
                                        }
                                        Rectangle {
                                            x: 12; y: 62
                                            width: parent.width - 24
                                            height: 5
                                            radius: 2.5
                                            antialiasing: true
                                            color: Qt.rgba(1, 1, 1, 0.12)
                                            Rectangle {
                                                height: parent.height
                                                radius: 2.5
                                                antialiasing: true
                                                width: parent.width * (bar.timerTotal > 0 ? Math.min(1, bar.timerLeft / bar.timerTotal) : 0)
                                                color: bar.accent
                                                Behavior on width { NumberAnimation { duration: 900 } }
                                            }
                                        }
                                    }

                                    // ---- reminders ----
                                    Repeater {
                                        model: bar.alarms
                                        Rectangle {
                                            id: srow
                                            required property var modelData
                                            required property int index
                                            readonly property bool done: !modelData.on && modelData.rep === "none" && modelData.ts <= bar.now.getTime()
                                            width: sideAlarmCol.width
                                            height: 48
                                            radius: 8
                                            antialiasing: true
                                            color: Qt.rgba(1, 1, 1, 0.06)
                                            Text {
                                                x: 12
                                                y: 8
                                                width: parent.width - 12 - 150
                                                elide: Text.ElideRight
                                                textFormat: bar.noteFmt(srow.modelData.t)
                                                text: srow.modelData.t && srow.modelData.t !== "" ? bar.noteHtml(srow.modelData.t) : "Reminder"
                                                color: srow.modelData.on ? "white" : Qt.rgba(1, 1, 1, 0.45)
                                                font.family: bar.uiFont
                                                font.pixelSize: 13
                                            }
                                            Text {
                                                x: 12
                                                y: 28
                                                width: parent.width - 12 - 150
                                                elide: Text.ElideRight
                                                text: srow.done ? "done" : bar.fmtReminder(srow.modelData.ts, srow.modelData.rep)
                                                color: Qt.rgba(1, 1, 1, 0.55)
                                                font.family: bar.uiFont
                                                font.pixelSize: 10
                                            }
                                            Rectangle {
                                                id: sTrack
                                                x: parent.width - 138
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 52
                                                height: 24
                                                radius: 12
                                                antialiasing: true
                                                readonly property color ink: ((0.299 * bar.accent.r + 0.587 * bar.accent.g + 0.114 * bar.accent.b) > 0.5) ? "#14141c" : "#ffffff"
                                                color: srow.modelData.on ? bar.accent : Qt.rgba(1, 1, 1, 0.06)
                                                border.width: 1.5
                                                border.color: srow.modelData.on ? bar.accent : Qt.rgba(1, 1, 1, 0.35)
                                                Behavior on color { ColorAnimation { duration: 110 } }
                                                Text {
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    x: srow.modelData.on ? 9 : parent.width - width - 9
                                                    text: srow.modelData.on ? "ON" : "OFF"
                                                    color: srow.modelData.on ? sTrack.ink : Qt.rgba(1, 1, 1, 0.5)
                                                    font.family: bar.uiFont
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                }
                                                Rectangle {
                                                    y: 4
                                                    width: 16
                                                    height: 16
                                                    radius: 8
                                                    antialiasing: true
                                                    color: srow.modelData.on ? sTrack.ink : Qt.rgba(1, 1, 1, 0.55)
                                                    x: srow.modelData.on ? parent.width - width - 4 : 4
                                                    Behavior on x { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                                                }
                                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmToggle(srow.index) }
                                            }
                                            Rectangle {
                                                x: parent.width - 78
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 22
                                                height: 22
                                                radius: 6
                                                antialiasing: true
                                                color: Qt.rgba(1, 1, 1, seditMouse.containsMouse ? 0.16 : 0.08)
                                                Text { anchors.centerIn: parent; text: "\uE70F"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "white" }
                                                MouseArea { id: seditMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.openReminderEdit(srow.index) }
                                            }
                                            Rectangle {
                                                x: parent.width - 52
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 22
                                                height: 22
                                                radius: 6
                                                antialiasing: true
                                                color: Qt.rgba(1, 1, 1, srepMouse.containsMouse ? 0.16 : 0.08)
                                                Text { anchors.centerIn: parent; text: "\uE895"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: srow.modelData.rep !== "none" ? bar.accent : Qt.rgba(1, 1, 1, 0.5) }
                                                MouseArea { id: srepMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmRepeat(srow.index) }
                                            }
                                            Rectangle {
                                                x: parent.width - 26
                                                anchors.verticalCenter: parent.verticalCenter
                                                width: 22
                                                height: 22
                                                radius: 6
                                                antialiasing: true
                                                color: Qt.rgba(1, 1, 1, sdelMouse.containsMouse ? 0.16 : 0.08)
                                                Text { anchors.centerIn: parent; text: "\uE74D"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "#ff6b7a" }
                                                MouseArea { id: sdelMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.alarmDelete(srow.index) }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ---- tab 2: notes ----
                        Column {
                            visible: bar.sideTab === "notes"
                            width: parent.width
                            height: sidePanel.bodyH
                            spacing: 10

                            // ---- the + button opens the editor ----
                            ClkBtn {
                                visible: !sidePanel.composing
                                width: parent.width
                                text: "New note"
                                icon: "\uE710"
                                accent: bar.accent; fontFamily: bar.uiFont
                                onClicked: sidePanel.newNote()
                            }

                            // ---- editor (title + text + save), only while composing / editing ----
                            Column {
                                id: composer
                                visible: sidePanel.composing
                                width: parent.width
                                spacing: 8

                                // ---- title ----
                                Rectangle {
                                    width: parent.width
                                    height: 32
                                    radius: 10
                                    antialiasing: true
                                    color: Qt.rgba(0, 0, 0, 0.28)
                                    border.width: 1
                                    border.color: titleEdit.activeFocus ? bar.accent : Qt.rgba(1, 1, 1, 0.14)
                                    Behavior on border.color { ColorAnimation { duration: 90 } }
                                    // live preview: the styled copy of the title, right in the box
                                    LiveLine { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; input: titleEdit }
                                    TextInput {
                                        id: titleEdit
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: "transparent"
                                        selectedTextColor: "transparent"
                                        selectionColor: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.35)
                                        cursorDelegate: Rectangle { width: 1.5; color: "white"; opacity: titleEdit.activeFocus ? 1 : 0 }
                                        selectByMouse: true
                                        clip: true
                                        maximumLength: 60
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                        Keys.onPressed: (e) => { if (sidePanel.autoClose(titleEdit, e)) e.accepted = true }
                                        Keys.onReturnPressed: noteEdit.forceActiveFocus()
                                        Keys.onEnterPressed: noteEdit.forceActiveFocus()
                                        KeyNavigation.tab: noteEdit
                                        onActiveFocusChanged: if (!activeFocus) typingCheck.restart()
                                    }
                                    Text {
                                        visible: titleEdit.text === ""
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 12
                                        text: "Title (optional)"
                                        color: Qt.rgba(1, 1, 1, 0.38)
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !titleEdit.activeFocus
                                        cursorShape: Qt.IBeamCursor
                                        onClicked: sidePanel.focusInput(titleEdit)
                                    }
                                }

                                // ---- text ----
                                Rectangle {
                                    width: parent.width
                                    height: 84
                                    radius: 10
                                    antialiasing: true
                                    color: Qt.rgba(0, 0, 0, 0.28)
                                    border.width: 1
                                    border.color: noteEdit.activeFocus ? bar.accent : Qt.rgba(1, 1, 1, 0.14)
                                    Behavior on border.color { ColorAnimation { duration: 90 } }
                                    Flickable {
                                        id: noteFlick
                                        anchors.fill: parent
                                        anchors.margins: 10
                                        contentWidth: width
                                        contentHeight: Math.max(noteEdit.contentHeight, liveNote.contentHeight)
                                        clip: true
                                        boundsBehavior: Flickable.StopAtBounds
                                        function clampY() {
                                            var m = Math.max(0, contentHeight - height)
                                            if (contentY > m) contentY = m
                                            if (contentY < 0) contentY = 0
                                        }
                                        function ensureVisible(r) {
                                            if (contentY >= r.y) contentY = r.y
                                            else if (contentY + height <= r.y + r.height) contentY = r.y + r.height - height
                                            clampY()
                                        }
                                        // deleting a lot of text leaves the old scroll offset behind: the leftover text slides out of the box
                                        // (still there, but you can't reach it). pull the view back whenever the text gets shorter
                                        onContentHeightChanged: clampY()
                                        onHeightChanged: clampY()
                                        // live preview: the styled copy of the text, right in the box
                                        LiveText { id: liveNote; src: noteEdit; width: noteEdit.width; wrapMode: Text.Wrap }
                                        TextEdit {
                                            id: noteEdit
                                            width: noteFlick.width
                                            height: Math.max(contentHeight, noteFlick.height)
                                            wrapMode: TextEdit.Wrap
                                            color: "transparent"
                                            selectedTextColor: "transparent"
                                            selectionColor: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.35)
                                            cursorDelegate: Rectangle { width: 1.5; color: "white"; opacity: noteEdit.activeFocus ? 1 : 0 }
                                            selectByMouse: true
                                            font.family: bar.uiFont
                                            font.pixelSize: 12
                                            onCursorRectangleChanged: noteFlick.ensureVisible(cursorRectangle)
                                            onActiveFocusChanged: if (!activeFocus) typingCheck.restart()
                                            Keys.onPressed: (e) => {
                                                if (sidePanel.autoClose(noteEdit, e)) { e.accepted = true; return }
                                                if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && (e.modifiers & Qt.ControlModifier)) {
                                                    sidePanel.saveNote()
                                                    e.accepted = true
                                                }
                                            }
                                        }
                                    }
                                    Text {
                                        visible: noteEdit.text === ""
                                        x: 10
                                        y: 10
                                        width: parent.width - 20
                                        wrapMode: Text.Wrap
                                        text: "Write a note..."
                                        color: Qt.rgba(1, 1, 1, 0.38)
                                        font.family: bar.uiFont
                                        font.pixelSize: 12
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !noteEdit.activeFocus
                                        cursorShape: Qt.IBeamCursor
                                        onClicked: sidePanel.focusInput(noteEdit)
                                    }
                                }

                                Row {
                                    spacing: 6
                                    ClkBtn {
                                        width: 300 - 6 - 80
                                        text: sidePanel.editIndex >= 0 ? "Update note" : "Save note"
                                        icon: "\uE74E"
                                        primary: noteEdit.text.trim() !== "" || titleEdit.text.trim() !== ""
                                        accent: bar.accent; fontFamily: bar.uiFont
                                        onClicked: sidePanel.saveNote()
                                    }
                                    ClkBtn {
                                        width: 80
                                        text: "Cancel"
                                        accent: bar.accent; fontFamily: bar.uiFont
                                        onClicked: sidePanel.closeComposer()
                                    }
                                }
                            }

                            // ---- saved notes (a note with a title shows only the title, click it to open / close the rest, pencil edits) ----
                            Item {
                                width: parent.width
                                height: sidePanel.bodyH - 10 - (sidePanel.composing ? composer.implicitHeight : 32)
                                clip: true
                                Text {
                                    visible: bar.notes.length === 0
                                    anchors.centerIn: parent
                                    text: "No notes yet"
                                    color: bar.muted
                                    font.family: bar.uiFont
                                    font.pixelSize: 12
                                }
                                Flickable {
                                    id: noteListFlick
                                    anchors.fill: parent
                                    contentWidth: width
                                    contentHeight: noteCol.height
                                    boundsBehavior: Flickable.StopAtBounds
                                    onContentHeightChanged: { var m = Math.max(0, contentHeight - height); if (contentY > m) contentY = m }
                                    onHeightChanged: { var m = Math.max(0, contentHeight - height); if (contentY > m) contentY = m }
                                    Column {
                                        id: noteCol
                                        width: parent.width
                                        spacing: 4
                                        Repeater {
                                            model: bar.notes
                                            Rectangle {
                                                id: nrow
                                                required property var modelData
                                                required property int index
                                                readonly property string title: modelData.title || ""
                                                readonly property string body: modelData.t || ""
                                                property bool expanded: false
                                                // a note with a title is folded down to just its title until you click it
                                                readonly property bool showBody: nrow.body !== "" && (nrow.title === "" || nrow.expanded)
                                                width: noteCol.width
                                                height: Math.max(34, ncol.implicitHeight + 16)
                                                radius: 8
                                                antialiasing: true
                                                clip: true
                                                color: nrowMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(1, 1, 1, 0.06)
                                                border.width: sidePanel.editIndex === nrow.index ? 1 : 0
                                                border.color: bar.accent
                                                Behavior on color { ColorAnimation { duration: 90 } }
                                                Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                                                MouseArea { id: nrowMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: nrow.expanded = !nrow.expanded }
                                                Column {
                                                    id: ncol
                                                    x: 12
                                                    y: 8
                                                    width: parent.width - 12 - 66
                                                    spacing: 3
                                                    Text {
                                                        visible: nrow.title !== ""
                                                        width: parent.width
                                                        elide: Text.ElideRight
                                                        textFormat: bar.noteFmt(nrow.title)
                                                        text: bar.noteHtml(nrow.title)
                                                        color: "white"
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 13
                                                    }
                                                    Text {
                                                        visible: nrow.showBody
                                                        width: parent.width
                                                        wrapMode: Text.Wrap
                                                        maximumLineCount: nrow.expanded ? 1000 : 4
                                                        elide: Text.ElideRight
                                                        textFormat: bar.noteFmt(nrow.body)
                                                        text: bar.noteHtml(nrow.body)
                                                        color: "white"
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 12
                                                    }
                                                    Text {
                                                        visible: nrow.title === "" || nrow.expanded
                                                        text: Qt.formatDateTime(new Date(nrow.modelData.ts), "d MMM, h:mm AP")
                                                        color: Qt.rgba(1, 1, 1, 0.45)
                                                        font.family: bar.uiFont
                                                        font.pixelSize: 10
                                                    }
                                                }
                                                Rectangle {
                                                    x: parent.width - 54
                                                    y: 6
                                                    width: 22
                                                    height: 22
                                                    radius: 6
                                                    antialiasing: true
                                                    color: Qt.rgba(1, 1, 1, neditMouse.containsMouse ? 0.16 : 0.08)
                                                    Text { anchors.centerIn: parent; text: "\uE70F"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: sidePanel.editIndex === nrow.index ? bar.accent : "white" }
                                                    MouseArea { id: neditMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: sidePanel.editNote(nrow.index) }
                                                }
                                                Rectangle {
                                                    x: parent.width - 28
                                                    y: 6
                                                    width: 22
                                                    height: 22
                                                    radius: 6
                                                    antialiasing: true
                                                    color: Qt.rgba(1, 1, 1, ndelMouse.containsMouse ? 0.16 : 0.08)
                                                    Text { anchors.centerIn: parent; text: "\uE74D"; font.family: "Segoe Fluent Icons"; font.pixelSize: 11; color: "#ff6b7a" }
                                                    MouseArea {
                                                        id: ndelMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: {
                                                            if (sidePanel.editIndex === nrow.index) sidePanel.closeComposer()
                                                            else if (sidePanel.editIndex > nrow.index) sidePanel.editIndex--
                                                            bar.noteDelete(nrow.index)
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
                }
            }
        }
    }

    // ---- dock ----
    // hover the slim handle in the middle of the bottom edge and a card slides up with a weather widget (left)
    // and a music widget (right). weather comes from open-meteo.com (no key needed), set your place below.
    property real weatherLat: 0                    // 0 and 0 = find the place automatically (from your IP), or put your own latitude here
    property real weatherLon: 0                    // <- your longitude
    property bool weatherF: false                  // true = Fahrenheit + mph (switched on automatically for the US when the place is auto-detected)
    property bool weatherLocating: false
    property bool weatherOk: false
    property real weatherStamp: 0
    property real wTemp: 0
    property real wFeels: 0
    property real wHi: 0
    property real wLo: 0
    property real wHum: 0
    property real wWind: 0
    property int wCode: 0
    function weatherInfo(c) {
        if (c === 0) return ["\u2600\uFE0F", "Clear sky"]
        if (c === 1) return ["\uD83C\uDF24\uFE0F", "Mostly clear"]
        if (c === 2) return ["\u26C5", "Partly cloudy"]
        if (c === 3) return ["\u2601\uFE0F", "Overcast"]
        if (c === 45 || c === 48) return ["\uD83C\uDF2B\uFE0F", "Fog"]
        if (c >= 51 && c <= 57) return ["\uD83C\uDF26\uFE0F", "Drizzle"]
        if (c >= 61 && c <= 67) return ["\uD83C\uDF27\uFE0F", "Rain"]
        if (c >= 71 && c <= 77) return ["\uD83C\uDF28\uFE0F", "Snow"]
        if (c >= 80 && c <= 82) return ["\uD83C\uDF26\uFE0F", "Showers"]
        if (c === 85 || c === 86) return ["\uD83C\uDF28\uFE0F", "Snow showers"]
        if (c >= 95) return ["\u26C8\uFE0F", "Thunderstorm"]
        return ["\uD83C\uDF21\uFE0F", "Weather"]
    }
    // the place from config.json (vaporctl set location), no place there = find it from the IP
    property bool placeLoaded: false
    function applyPlace(reset) {
        placeLoaded = true
        try {
            var s = B.weatherPlace()
            if (s !== "") {
                var d = JSON.parse(s)
                weatherLat = d.lat; weatherLon = d.lon; weatherF = !!d.fahrenheit
                return
            }
        } catch (e) { console.log("weather place failed:", e) }
        if (reset) { weatherLat = 0; weatherLon = 0 }
    }
    function weatherFetch() {
        if (!placeLoaded) applyPlace(false)
        if (weatherLat === 0 && weatherLon === 0) {
            if (weatherLocating) return
            weatherLocating = true
            var g = new XMLHttpRequest()
            g.onreadystatechange = function () {
                if (g.readyState !== XMLHttpRequest.DONE) return
                bar.weatherLocating = false
                try {
                    var p = JSON.parse(g.responseText)
                    if (p.success !== false && p.latitude !== undefined) {
                        bar.weatherLat = p.latitude
                        bar.weatherLon = p.longitude
                        bar.weatherF = p.country_code === "US"
                        bar.weatherFetch()
                    }
                } catch (e) { }
            }
            g.open("GET", "https://ipwho.is/")
            g.send()
            return
        }
        var url = "https://api.open-meteo.com/v1/forecast?latitude=" + weatherLat + "&longitude=" + weatherLon
                + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
                + "&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1"
                + (weatherF ? "&temperature_unit=fahrenheit&wind_speed_unit=mph" : "")
        var x = new XMLHttpRequest()
        x.onreadystatechange = function () {
            if (x.readyState !== XMLHttpRequest.DONE || x.status !== 200) return
            try {
                var j = JSON.parse(x.responseText)
                bar.wTemp = j.current.temperature_2m
                bar.wFeels = j.current.apparent_temperature
                bar.wHum = j.current.relative_humidity_2m
                bar.wWind = j.current.wind_speed_10m
                bar.wCode = j.current.weather_code
                bar.wHi = j.daily.temperature_2m_max[0]
                bar.wLo = j.daily.temperature_2m_min[0]
                bar.weatherOk = true
                bar.weatherStamp = Date.now()
            } catch (e) { }
        }
        x.open("GET", url)
        x.send()
    }
    Timer { interval: 1200000; running: true; repeat: true; triggeredOnStart: true; onTriggered: bar.weatherFetch() }

    // ---- profile card (dock dashboard) ----
    property url profilePic: {                               // the Windows account picture (from the backend), profile.png next to Vapor.qml is the fallback
        var a = (typeof B.userAvatar === "string") ? B.userAvatar : ""
        if (a === "") return Qt.resolvedUrl("profile.png")
        return a.indexOf("file:") === 0 ? a : "file:///" + a.replace(/\\/g, "/")
    }
    property string profileName: (typeof B.userName === "string" && B.userName !== "") ? B.userName : "User"   // the Windows user name when the backend has one
    property string profileIcon: "\uE77B"                    // profile glyph (Segoe Fluent Icons)
    property string profileSub: "Vapor"
    property string profileSubIcon: "\uE7C4"                 // placeholder icon, swap for any glyph you like

    // uptime comes from the backend ("up 1 hour, 23 minutes", refreshed every 30 s), if it's empty it's the time since Vapor started
    readonly property real startedMs: Date.now()
    function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s") }
    function fmtUptime(sec) {
        var d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60)
        if (sec < 60) return "up less than a minute"
        if (d > 0) return "up " + plural(d, "day") + ", " + plural(h, "hour")
        if (h > 0) return "up " + plural(h, "hour") + ", " + plural(m, "minute")
        return "up " + plural(m, "minute")
    }
    readonly property string uptimeText: {
        if (typeof B.uptime === "string" && B.uptime !== "") return B.uptime
        bar.now
        return fmtUptime(Math.floor((Date.now() - startedMs) / 1000))
    }

    property bool dockWant: false          // mouse is on the bottom handle or on the dock
    property real dockP: 0                 // 0 = tucked away, 1 = fully out
    readonly property bool dockShow: dockWant && shown && !trayDragging
    readonly property int dockW: 760
    readonly property int dockH: 460
    readonly property int dockSeam: 2      // the dock window reaches this many px into the bottom frame so the card covers the frame's hairline
    property string dockTab: "dash"       // dash | media | ws
    readonly property real dockPv: Math.min(1, Math.max(0, dockP))
    readonly property real dockWinW: dockW + 2 * flare
    readonly property real dockCwidNow: dockPv * dockW
    readonly property real dockChNow: 56 + (dockH - 56) * Math.min(1, dockPv * 1.25)
    readonly property real dockCrNow: Math.max(0, Math.min(22, dockCwidNow / 2, dockChNow / 2))
    readonly property real dockFfNow: Math.max(0, Math.min(flare, dockChNow - dockCrNow))
    readonly property real dockMidX: Math.round((B.screenW - dockWinW) / 2) + dockWinW / 2
    // where the card's curved join meets the frame, the curve hugs the frame line for the last few px and fades out,
    // which used to leave a small gap between the frame's hairline and the curve. the hairline is now left in for
    // dockJoinInset px under each join, so the two overlap and meet.
    readonly property real dockJoinInset: Math.min(4, dockFfNow)
    readonly property real dockCutX0: (dockP > 0.002 && dockCwidNow > 2) ? dockMidX - dockCwidNow / 2 - dockFfNow + dockJoinInset : 0
    readonly property real dockCutX1: (dockP > 0.002 && dockCwidNow > 2) ? dockMidX + dockCwidNow / 2 + dockFfNow - dockJoinInset : 0

    onDockShowChanged: {
        dockAnim.stop()
        dockAnim.to = dockShow ? 1 : 0
        dockAnim.duration = (dockShow ? 380 : 240) * popSpeed
        dockAnim.easing.bezierCurve = dockShow ? curveSpatial : curveExit
        dockAnim.start()
        if (dockShow && Date.now() - weatherStamp > 900000) weatherFetch()
    }
    NumberAnimation { id: dockAnim; target: bar; property: "dockP"; easing.type: Easing.BezierSpline }
    Timer { id: dockOpenDelay; interval: 110; onTriggered: bar.dockWant = true }
    Timer { id: dockCloseDelay; interval: 320; onTriggered: if (!edgeB.handleHovered && !dockHoverH.hovered) bar.dockWant = false }
    function dockHover(on) {
        if (on) { dockCloseDelay.stop(); if (!dockWant) dockOpenDelay.restart() }
        else { dockOpenDelay.stop(); dockCloseDelay.restart() }
    }

    Window {
        id: dockWin
        title: "Vapor Dock"
        visible: bar.dockP > 0.002 && bar.shown
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        width: bar.dockW + 2 * bar.flare         // + room for the two concave joins left and right of the card
        height: bar.dockH + bar.dockSeam         // the card's bottom edge sits on the frame's inner edge, the last dockSeam px overlap the frame
        x: B.screenX + Math.round((B.screenW - width) / 2)
        y: B.screenY + B.fullH - bar.frameW - bar.dockH

        Item {
            id: dockRoot
            anchors.fill: parent
            HoverHandler { id: dockHoverH; onHoveredChanged: bar.dockHover(hovered) }

            // ---- the card: one shape that grows out of the bottom frame, with concave joins (like the bar's popups) ----
            readonly property real cwid: bar.dockCwidNow             // card width right now
            readonly property real ch: bar.dockChNow                 // card height right now
            readonly property real cr: bar.dockCrNow                 // rounded top corners
            readonly property real ff: bar.dockFfNow                 // join radius at the frame
            EdgeCard { x: 0; y: 0; width: dockRoot.width; height: bar.dockH; bottomEdge: true; cw: dockRoot.ch; cl: dockRoot.cwid; cr: dockRoot.cr; ff: dockRoot.ff; fill: bar.glassFill; line: bar.glassLine }
            // seam cover: hides the frame's hairline right under the card so the card melts into the frame (the joins stay as they are)
            Rectangle {
                visible: dockRoot.cwid > 2
                x: (dockRoot.width - dockRoot.cwid) / 2 - dockRoot.ff + bar.dockJoinInset
                y: bar.dockH
                width: dockRoot.cwid + 2 * dockRoot.ff - 2 * bar.dockJoinInset
                height: bar.dockSeam
                color: bar.glassFill
            }

            // content is clipped to the card while it grows
            Item {
                id: dockClip
                x: (dockRoot.width - dockRoot.cwid) / 2
                y: bar.dockH - dockRoot.ch
                width: dockRoot.cwid
                height: dockRoot.ch
                clip: true

                Item {
                    id: dockPanel
                    width: bar.dockW
                    height: bar.dockH
                    x: -(bar.dockW - dockClip.width) / 2        // stays centred while the card grows out of the bottom frame
                    y: dockClip.height - bar.dockH
                    opacity: Math.min(1, bar.dockP * 2)
                    MouseArea { anchors.fill: parent }

                    // calendar state: opens on the current month
                property int calYear: new Date().getFullYear()
                property int calMonth: new Date().getMonth()
                function cellDate(i) {
                    var first = new Date(calYear, calMonth, 1)
                    var off = (first.getDay() + 6) % 7            // weeks start on Monday
                    return new Date(calYear, calMonth, 1 - off + i)
                }
                function calStep(n) {
                    var d = new Date(calYear, calMonth + n, 1)
                    calYear = d.getFullYear()
                    calMonth = d.getMonth()
                }
                Connections {
                    target: bar
                    function onDockShowChanged() {
                        if (bar.dockShow) { dockPanel.calYear = new Date().getFullYear(); dockPanel.calMonth = new Date().getMonth() }
                    }
                }

                // ---- tabs ----
                Item {
                    id: dockTabs
                    x: 18; y: 10
                    width: parent.width - 36
                    height: 46
                    Repeater {
                        model: [ { key: "dash", icon: "\uE80F", label: "Dashboard" },
                                 { key: "media", icon: "\uE8D6", label: "Media" },
                                 { key: "ws", icon: "\uE7C4", label: "Workspaces" } ]
                        Item {
                            id: tab
                            required property var modelData
                            required property int index
                            readonly property bool on: bar.dockTab === modelData.key
                            x: index * (dockTabs.width / 3)
                            width: dockTabs.width / 3
                            height: dockTabs.height
                            Column {
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 3
                                spacing: 3
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: tab.modelData.icon; font.family: "Segoe Fluent Icons"; font.pixelSize: 16; color: tab.on ? "white" : bar.muted }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: tab.modelData.label; font.family: bar.uiFont; font.pixelSize: 12; color: tab.on ? "white" : bar.muted }
                            }
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.bottom: parent.bottom
                                width: tab.on ? 84 : 0
                                height: 2
                                radius: 1
                                color: bar.accent
                                Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bar.dockTab = tab.modelData.key }
                        }
                    }
                }
                Rectangle { x: 18; y: 57; width: parent.width - 36; height: 1; color: Qt.rgba(1, 1, 1, 0.12) }

                // ---- dashboard ----
                Item {
                    id: dashPage
                    visible: bar.dockTab === "dash"
                    x: 18; y: 68
                    width: parent.width - 36
                    height: parent.height - 68 - 18

                    // ---- weather ----
                    Rectangle {
                        x: 0; y: 0; width: 220; height: 100
                        radius: 18; antialiasing: true
                        color: Qt.rgba(1, 1, 1, 0.06)
                        readonly property var info: bar.weatherInfo(bar.wCode)
                        readonly property string deg: bar.weatherF ? "\u00B0F" : "\u00B0C"
                        Text { visible: !bar.weatherOk; anchors.centerIn: parent; text: "Loading weather..."; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 12 }
                        Item {
                            visible: bar.weatherOk
                            anchors.fill: parent
                            Text { x: 14; y: 16; text: parent.parent.info[0]; font.family: "Segoe UI Emoji"; font.pixelSize: 40 }
                            Text { x: 76; y: 12; text: Math.round(bar.wTemp) + parent.parent.deg; color: "white"; font.family: bar.uiFont; font.pixelSize: 28; font.weight: Font.Bold }
                            Text { x: 76; y: 50; text: parent.parent.info[1]; color: "white"; font.family: bar.uiFont; font.pixelSize: 12 }
                            Text { x: 14; y: 76; text: "Feels " + Math.round(bar.wFeels) + "\u00B0   H " + Math.round(bar.wHi) + "\u00B0  L " + Math.round(bar.wLo) + "\u00B0"; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 10 }
                        }
                    }

                    // ---- profile ----
                    Rectangle {
                        id: profileCard
                        x: 228; y: 0; width: 280; height: 100
                        radius: 18; antialiasing: true
                        color: Qt.rgba(1, 1, 1, 0.06)

                        // avatar: round picture with an accent ring (the glyph shows if the picture is missing)
                        Rectangle {
                            x: 14
                            anchors.verticalCenter: parent.verticalCenter
                            width: 68; height: 68; radius: 34
                            antialiasing: true
                            color: Qt.rgba(1, 1, 1, 0.08)
                            border.width: 2
                            border.color: bar.accent
                            Text { anchors.centerIn: parent; text: bar.profileIcon; font.family: "Segoe Fluent Icons"; font.pixelSize: 28; color: Qt.rgba(1, 1, 1, 0.3) }
                            RoundImage { anchors.fill: parent; anchors.margins: 3; radius: width / 2; cover: true; source: bar.profilePic }
                        }

                        Column {
                            x: 98
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 98 - 12
                            spacing: 9
                            ProfileRow { width: parent.width; glyph: bar.profileIcon;    label: bar.profileName }
                            ProfileRow { width: parent.width; glyph: bar.profileSubIcon; label: bar.profileSub }
                            ProfileRow { width: parent.width; glyph: "\uE916";           label: bar.uptimeText }
                        }
                    }

                    // ---- time ----
                    Rectangle {
                        x: 0; y: 108; width: 104; height: parent.height - 108
                        radius: 18; antialiasing: true
                        color: Qt.rgba(1, 1, 1, 0.06)
                        Column {
                            anchors.centerIn: parent
                            spacing: 6
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: Qt.formatDateTime(bar.now, "hh AP").substring(0, 2); color: "white"; font.family: bar.uiFont; font.pixelSize: 34; font.weight: Font.Bold }
                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 4
                                Repeater { model: 3; Rectangle { width: 5; height: 5; radius: 2.5; color: bar.accent } }
                            }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: Qt.formatDateTime(bar.now, "mm"); color: "white"; font.family: bar.uiFont; font.pixelSize: 34; font.weight: Font.Bold }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: Qt.formatDateTime(bar.now, "AP"); color: bar.muted; font.family: bar.uiFont; font.pixelSize: 12 }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; topPadding: 8; text: Qt.formatDateTime(bar.now, "ddd, d"); color: bar.muted; font.family: bar.uiFont; font.pixelSize: 12 }
                        }
                    }

                    // ---- calendar ----
                    Rectangle {
                        id: calCard
                        x: 112; y: 108; width: 396; height: parent.height - 108
                        radius: 18; antialiasing: true
                        color: Qt.rgba(1, 1, 1, 0.06)
                        Item {
                            x: 16; y: 10
                            width: parent.width - 32
                            height: 34
                            ClkBtn { x: 0; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 28; icon: "\uE76B"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: dockPanel.calStep(-1) }
                            Text {
                                anchors.centerIn: parent
                                text: Qt.locale().monthName(dockPanel.calMonth) + " " + dockPanel.calYear
                                color: "white"; font.family: bar.uiFont; font.pixelSize: 14; font.weight: Font.Bold
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { dockPanel.calYear = new Date().getFullYear(); dockPanel.calMonth = new Date().getMonth() } }
                            }
                            ClkBtn { x: parent.width - 32; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 28; icon: "\uE76C"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: dockPanel.calStep(1) }
                        }
                        Row {
                            x: 16; y: 48
                            Repeater {
                                model: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                                Text { required property string modelData; width: (calCard.width - 32) / 7; horizontalAlignment: Text.AlignHCenter; text: modelData; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 11; font.weight: Font.DemiBold }
                            }
                        }
                        Grid {
                            x: 16; y: 72
                            columns: 7
                            Repeater {
                                model: 42
                                Item {
                                    id: cell
                                    required property int index
                                    readonly property var d: dockPanel.cellDate(index)
                                    readonly property bool cur: d.getMonth() === dockPanel.calMonth
                                    readonly property bool today: d.getDate() === bar.now.getDate() && d.getMonth() === bar.now.getMonth() && d.getFullYear() === bar.now.getFullYear()
                                    width: (calCard.width - 32) / 7
                                    height: (calCard.height - 72 - 10) / 6
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: Math.min(parent.width, parent.height) - 2
                                        height: width
                                        radius: width / 2
                                        antialiasing: true
                                        color: cell.today ? bar.accent : "transparent"
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: cell.d.getDate()
                                        font.family: bar.uiFont
                                        font.pixelSize: 13
                                        font.weight: cell.today ? Font.Bold : Font.Normal
                                        color: cell.today ? ((0.299 * bar.accent.r + 0.587 * bar.accent.g + 0.114 * bar.accent.b) > 0.55 ? "#000000" : "#ffffff") : (cell.cur ? "white" : Qt.rgba(1, 1, 1, 0.28))
                                    }
                                }
                            }
                        }
                    }

                    // ---- music ----
                    Rectangle {
                        id: musicCard
                        x: 516; y: 0; width: parent.width - 516; height: parent.height
                        radius: 18; antialiasing: true
                        color: Qt.rgba(1, 1, 1, 0.06)
                        readonly property bool has: B.mediaTitle !== ""
                        MediaWheel { }          // scroll anywhere on the card: previous / next playing app
                        Text { visible: !musicCard.has; anchors.centerIn: parent; text: "Nothing playing"; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 12 }
                        Item {
                            visible: musicCard.has
                            anchors.fill: parent
                            Rectangle {
                                x: (parent.width - 150) / 2; y: 20
                                width: 150; height: 150; radius: 75
                                antialiasing: true
                                color: Qt.rgba(1, 1, 1, 0.08)
                                Text { anchors.centerIn: parent; text: "\uE8D6"; font.family: "Segoe Fluent Icons"; font.pixelSize: 36; color: Qt.rgba(1, 1, 1, 0.3) }
                                RoundImage { anchors.fill: parent; radius: width / 2; cover: true; source: B.mediaArt }
                            }
                            Text { x: 12; y: 186; width: parent.width - 24; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: B.mediaTitle; color: "white"; font.family: bar.uiFont; font.pixelSize: 14; font.weight: Font.Bold }
                            Text { x: 12; y: 210; width: parent.width - 24; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: B.mediaArtist; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 12 }
                            Text { x: 12; y: 230; width: parent.width - 24; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: B.mediaSource; color: Qt.rgba(1, 1, 1, 0.4); font.family: bar.uiFont; font.pixelSize: 10 }
                            Row {
                                x: (parent.width - 136) / 2; y: 258
                                spacing: 8
                                ClkBtn { width: 36; height: 34; icon: "\uE892"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaPrev() }
                                ClkBtn { width: 48; height: 34; icon: B.mediaPlaying ? "\uE769" : "\uE768"; primary: true; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaPlayPause() }
                                ClkBtn { width: 36; height: 34; icon: "\uE893"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaNext() }
                            }
                            Rectangle {
                                x: 20; y: 318; width: parent.width - 40; height: 5; radius: 2.5
                                color: Qt.rgba(1, 1, 1, 0.12)
                                Rectangle { height: parent.height; radius: 2.5; width: parent.width * Math.max(0, Math.min(1, B.mediaProgress)); color: bar.accent }
                                MouseArea { anchors.fill: parent; anchors.topMargin: -6; anchors.bottomMargin: -6; cursorShape: Qt.PointingHandCursor; onClicked: (m) => B.mediaSeek(Math.max(0, Math.min(1, m.x / width))) }
                            }
                            Text { x: 0; y: 330; width: parent.width; horizontalAlignment: Text.AlignHCenter; text: B.mediaTime; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 10 }
                        }
                    }
                }

                // ---- media: big round art with the audio ring ----
                Item {
                    id: mediaPage
                    visible: bar.dockTab === "media"
                    x: 18; y: 68
                    width: parent.width - 36
                    height: parent.height - 68 - 18
                    readonly property bool has: B.mediaTitle !== ""
                    MediaWheel { }              // scroll anywhere on the page: previous / next playing app
                    Text { visible: !mediaPage.has; anchors.centerIn: parent; text: "Nothing playing"; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 13 }
                    Item {
                        visible: mediaPage.has
                        anchors.fill: parent

                        // the ring: 36 spokes around the art, driven by the live audio bands (B.vizBars)
                        Item {
                            id: vizRing
                            x: 20; y: (parent.height - height) / 2
                            width: 340; height: 340
                            Repeater {
                                model: 36
                                Item {
                                    id: spoke
                                    required property int index
                                    x: vizRing.width / 2
                                    y: vizRing.height / 2
                                    rotation: index * 10
                                    readonly property int k: index <= 18 ? index : 36 - index
                                    readonly property int band: Math.min(5, Math.floor(k / 3.2))
                                    readonly property real v: (B.vizActive && B.vizBars.length > band ? B.vizBars[band] : 0) * (0.72 + 0.28 * Math.sin(index * 1.9))
                                    Rectangle {
                                        x: -2.5
                                        y: -(100 + height)
                                        width: 5
                                        height: 8 + spoke.v * 56
                                        radius: 2.5
                                        antialiasing: true
                                        color: bar.mix(bar.accent, bar.lavender, spoke.k / 18)
                                        Behavior on height { NumberAnimation { duration: 70 } }
                                    }
                                }
                            }
                            Rectangle {
                                anchors.centerIn: parent
                                width: 186; height: 186; radius: 93
                                antialiasing: true
                                color: Qt.rgba(1, 1, 1, 0.08)
                                Text { anchors.centerIn: parent; text: "\uE8D6"; font.family: "Segoe Fluent Icons"; font.pixelSize: 44; color: Qt.rgba(1, 1, 1, 0.3) }
                                RoundImage { anchors.fill: parent; radius: width / 2; cover: true; source: B.mediaArt }
                            }
                        }

                        Item {
                            x: 400; y: 0
                            width: parent.width - 400; height: parent.height
                            Text { x: 0; y: 86; width: parent.width; elide: Text.ElideRight; text: B.mediaTitle; color: "white"; font.family: bar.uiFont; font.pixelSize: 22; font.weight: Font.Bold }
                            Text { x: 0; y: 122; width: parent.width; elide: Text.ElideRight; text: B.mediaArtist; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 15 }
                            Text { x: 0; y: 148; width: parent.width; elide: Text.ElideRight; text: B.mediaSource; color: Qt.rgba(1, 1, 1, 0.4); font.family: bar.uiFont; font.pixelSize: 11 }
                            Row {
                                x: 0; y: 186
                                spacing: 10
                                ClkBtn { width: 46; height: 42; icon: "\uE892"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaPrev() }
                                ClkBtn { width: 60; height: 42; icon: B.mediaPlaying ? "\uE769" : "\uE768"; primary: true; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaPlayPause() }
                                ClkBtn { width: 46; height: 42; icon: "\uE893"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: B.mediaNext() }
                            }
                            Rectangle {
                                x: 0; y: 252; width: parent.width; height: 6; radius: 3
                                color: Qt.rgba(1, 1, 1, 0.12)
                                Rectangle { height: parent.height; radius: 3; width: parent.width * Math.max(0, Math.min(1, B.mediaProgress)); color: bar.accent }
                                MouseArea { anchors.fill: parent; anchors.topMargin: -7; anchors.bottomMargin: -7; cursorShape: Qt.PointingHandCursor; onClicked: (m) => B.mediaSeek(Math.max(0, Math.min(1, m.x / width))) }
                            }
                            Text { x: 0; y: 266; text: B.mediaTime; color: bar.muted; font.family: bar.uiFont; font.pixelSize: 11 }
                        }
                    }
                }

                // ---- workspaces ----
                Item {
                    id: wsPage
                    visible: bar.dockTab === "ws"
                    x: 18; y: 68
                    width: parent.width - 36
                    height: parent.height - 68 - 18
                    Flow {
                        width: parent.width
                        spacing: 10
                        Repeater {
                            model: B.wsCount
                            Rectangle {
                                id: wst
                                required property int index
                                readonly property bool act: B.wsActive === index
                                readonly property bool pop: B.wsPopulated[index] === true
                                width: (wsPage.width - 30) / 4
                                height: 90
                                radius: 18
                                antialiasing: true
                                color: act ? Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.3) : Qt.rgba(1, 1, 1, wstMouse.containsMouse ? 0.12 : (pop ? 0.08 : 0.04))
                                border.width: act ? 1 : 0
                                border.color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.7)
                                Behavior on color { ColorAnimation { duration: 110 } }
                                Column {
                                    anchors.centerIn: parent
                                    spacing: 2
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: wst.index + 1; color: "white"; font.family: bar.uiFont; font.pixelSize: 26; font.weight: Font.Bold }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: wst.act ? "active" : (wst.pop ? "in use" : "empty"); color: bar.muted; font.family: bar.uiFont; font.pixelSize: 10 }
                                }
                                MouseArea {
                                    id: wstMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: B.focusWorkspaceAt(wst.index)
                                    onWheel: (w) => B.stepWorkspace(w.angleDelta.y > 0 ? -1 : 1)
                                }
                            }
                        }
                    }
                }

                }
            }
        }
    }

    // ---- alarm notification ----
    // when a reminder or the timer goes off, a small pill grows out of the bar (centre) and unfolds into a card with
    // Dismiss / Snooze. it shrinks back into the bar when dismissed.
    property real toastP: 0
    readonly property bool toastShow: ringing !== ""
    onToastShowChanged: {
        toastAnim.stop()
        toastAnim.to = toastShow ? 1 : 0
        toastAnim.duration = (toastShow ? 560 : 260) * popSpeed
        toastAnim.easing.bezierCurve = toastShow ? curveSpatial : curveExit
        toastAnim.start()
    }
    NumberAnimation { id: toastAnim; target: bar; property: "toastP"; easing.type: Easing.BezierSpline }

    Window {
        id: toastWin
        title: "Vapor Alarm"
        visible: bar.toastP > 0.002
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
        width: 380
        height: 116
        x: B.screenX + Math.round((B.screenW - width) / 2)
        y: B.screenY + bar.barH + 6

        Rectangle {
            id: toastCard
            readonly property real p: Math.max(0, Math.min(1.05, bar.toastP))
            property real pulse: 0
            anchors.horizontalCenter: parent.horizontalCenter
            y: 0
            width: 64 + 292 * p
            height: 44 + 60 * p
            radius: Math.min(height / 2, 24)
            antialiasing: true
            clip: true
            color: bar.glassFill
            border.width: 1.5
            border.color: bar.mix(bar.glassLine, bar.accent, pulse)
            SequentialAnimation on pulse {
                running: bar.toastShow
                loops: Animation.Infinite
                NumberAnimation { to: 1; duration: 650; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0; duration: 650; easing.type: Easing.InOutSine }
            }

            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 356
                height: 104
                opacity: Math.max(0, Math.min(1, (toastCard.p - 0.45) / 0.4))

                Rectangle {
                    x: 16; y: 18
                    width: 44; height: 44; radius: 22
                    antialiasing: true
                    color: Qt.rgba(bar.accent.r, bar.accent.g, bar.accent.b, 0.22)
                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width; height: parent.height; radius: width / 2
                        antialiasing: true
                        color: "transparent"
                        border.width: 2
                        border.color: bar.accent
                        opacity: 0.6 * (1 - toastCard.pulse)
                        scale: 1 + 0.5 * toastCard.pulse
                    }
                    Text { anchors.centerIn: parent; text: "\uE823"; font.family: "Segoe Fluent Icons"; font.pixelSize: 20; color: bar.accent }
                }
                Text {
                    x: 72; y: 14
                    width: parent.width - 72 - 16
                    elide: Text.ElideRight
                    textFormat: bar.noteFmt(bar.ringTitle)
                    text: bar.noteHtml(bar.ringTitle)
                    color: "white"
                    font.family: bar.uiFont
                    font.pixelSize: 15
                }
                Text {
                    visible: bar.ringSub !== ""
                    x: 72; y: 36
                    width: parent.width - 72 - 16
                    elide: Text.ElideRight
                    text: bar.ringSub
                    color: bar.muted
                    font.family: bar.uiFont
                    font.pixelSize: 11
                }
                Row {
                    x: 72; y: 66
                    spacing: 6
                    ClkBtn { height: 26; text: "Dismiss"; primary: true; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.dismissRing() }
                    ClkBtn { height: 26; text: "Snooze 5 min"; accent: bar.accent; fontFamily: bar.uiFont; onClicked: bar.snoozeRing() }
                }
            }
        }
    }

}
