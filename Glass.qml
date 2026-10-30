import QtQuick

// Solid FRAME for the whole screen (Caelestia style): the bar across the top plus a thin border down both
// sides and along the bottom, with rounded inner corners. The popup panel grows out of the bar as part of the SAME
// shape. Everything is ONE closed path filled with ONE solid colour (taken from the wallpaper by fluid_bar.pyw)
// plus a hairline outline in a very light colour. No blur / acrylic / image: nothing is loaded or uploaded.
Item {
    id: root

    // this item draws the screen shape, but only the part that starts at (originX, originY)
    // (used by the thin frame windows and the popup window; the main window has 0, 0)
    property real originX: 0
    property real originY: 0

    property color fillColor: "#14141f"
    property color outline: "#ff7a8cff"
    Behavior on fillColor { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }
    Behavior on outline { ColorAnimation { duration: 700; easing.type: Easing.InOutQuad } }

    // the "hole": the transparent middle of the screen, a rounded rectangle
    property real holeX: 6
    property real holeY: 36
    property real holeW: 0
    property real holeH: 0
    property real holeR: 18

    // the popup panel hanging from the hole's top edge (panelH <= 0: none)
    property real panelX: 0            // left edge of the panel (without the flares)
    property real panelW: 0
    property real panelH: 0
    property real panelR: 22           // bottom corner radius
    property real flare: 14            // concave joins between the bar and the panel

    // gaps in the hairline: where the side panel (right edge) or the dock (bottom edge) grows out of the frame, the
    // outline is left out between cutRY0..cutRY1 (right edge, y) / cutBX0..cutBX1 (bottom edge, x), so the card melts
    // into the frame like the popups do. Screen coordinates; an empty range (end <= start) = no gap.
    property real cutRY0: 0
    property real cutRY1: 0
    property real cutBX0: 0
    property real cutBX1: 0

    property bool _ready: false

    function repaint() { if (_ready) cv.requestPaint() }

    Component.onCompleted: { _ready = true; repaint() }
    onWidthChanged: repaint()
    onHeightChanged: repaint()
    onHoleXChanged: repaint()
    onHoleYChanged: repaint()
    onHoleWChanged: repaint()
    onHoleHChanged: repaint()
    onHoleRChanged: repaint()
    onPanelXChanged: repaint()
    onPanelWChanged: repaint()
    onPanelHChanged: repaint()
    onPanelRChanged: repaint()
    onFlareChanged: repaint()
    onFillColorChanged: repaint()
    onOutlineChanged: repaint()
    onCutRY0Changed: repaint()
    onCutRY1Changed: repaint()
    onCutBX0Changed: repaint()
    onCutBX1Changed: repaint()

    function corner(ctx, x1, y1, x2, y2, r) {
        if (r < 0.5) ctx.lineTo(x1, y1)
        else ctx.arcTo(x1, y1, x2, y2, r)
    }

    // The boundary of the transparent hole (plus the panel notch), travelling counter-clockwise.
    // `i` moves the line into the glass: 0 for the fill, 0.5 for the hairline so the stroke stays inside the glass.
    // (the hole grows by i where it borders the frame; the panel shrinks by i; concave flares keep their centre)
    function holePath(ctx, i) {
        var xl = holeX - i, xr = holeX + holeW + i
        var y0 = holeY - i, yb = holeY + holeH + i
        var r = Math.max(0, Math.min(holeR + i, (xr - xl) / 2, (yb - y0) / 2))
        ctx.moveTo(xl + r, y0)
        corner(ctx, xl, y0, xl, y0 + r, r)
        ctx.lineTo(xl, yb - r)
        corner(ctx, xl, yb, xl + r, yb, r)
        ctx.lineTo(xr - r, yb)
        corner(ctx, xr, yb, xr, yb - r, r)
        ctx.lineTo(xr, y0 + r)
        corner(ctx, xr, y0, xr - r, y0, r)
        if (panelH >= 1.5 && panelW > 4) {
            var f = Math.min(flare, panelH / 2)           // flares grow with the panel
            var L = panelX, Rr = panelX + panelW, Bp = holeY + panelH
            var br = Math.max(0, Math.min(panelR - i, panelW / 2, panelH - f))
            ctx.lineTo(Rr + f, y0)
            ctx.arc(Rr + f, holeY + f, f + i, -Math.PI / 2, -Math.PI, true)
            ctx.lineTo(Rr - i, Bp - i - br)
            corner(ctx, Rr - i, Bp - i, Rr - i - br, Bp - i, br)
            ctx.lineTo(L + i + br, Bp - i)
            corner(ctx, L + i, Bp - i, L + i, Bp - i - br, br)
            ctx.lineTo(L + i, holeY + f)
            ctx.arc(L - f, holeY + f, f + i, 0, -Math.PI / 2, true)
        }
        ctx.lineTo(xl + r, y0)
        ctx.closePath()
    }

    // The hairline outline. Normally it is the same path as the glass edge. But when the popup panel runs out to the
    // right-hand frame (the control center is flush with the screen edge), the hole's top-right corner and the
    // right edge above the panel lie INSIDE the panel and used to show up as stray lines where the bar and panel
    // touch. In that case those parts are left out, so the panel melts into the bar and the frame, and only the
    // real glass boundary is stroked.
    function outlinePath(ctx) {
        var i = 0.5
        var xl = holeX - i, xr = holeX + holeW + i
        var y0 = holeY - i, yb = holeY + holeH + i
        var r = Math.max(0, Math.min(holeR + i, (xr - xl) / 2, (yb - y0) / 2))
        var hasPanel = panelH >= 1.5 && panelW > 4
        var f = Math.min(flare, panelH / 2)
        var L = panelX, Rr = panelX + panelW, Bp = holeY + panelH
        var br = Math.max(0, Math.min(panelR - i, panelW / 2, panelH - f))
        if (!hasPanel || Rr + f < xr - r) {
            holePath(ctx, i)
            return
        }
        var by = Math.min(Bp - i, yb - r)               // where the panel's bottom edge meets the frame
        ctx.moveTo(xl + r, y0)
        corner(ctx, xl, y0, xl, y0 + r, r)
        ctx.lineTo(xl, yb - r)
        corner(ctx, xl, yb, xl + r, yb, r)
        ctx.lineTo(xr - r, yb)
        corner(ctx, xr, yb, xr, yb - r, r)
        ctx.lineTo(xr, by)                              // right frame edge, only BELOW the panel
        ctx.lineTo(L + i + br, by)                      // panel bottom edge, running into the frame
        corner(ctx, L + i, by, L + i, by - br, br)
        ctx.lineTo(L + i, holeY + f)
        ctx.arc(L - f, holeY + f, f + i, 0, -Math.PI / 2, true)
        ctx.lineTo(xl + r, y0)                          // back along the bar's bottom edge
        ctx.closePath()
    }

    Canvas {
        id: cv
        anchors.fill: parent

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.translate(-root.originX, -root.originY)
            ctx.clearRect(root.originX, root.originY, width, height)
            if (root.holeW < 8 || root.holeH < 8) return

            // glass = the whole screen minus the hole (outer rectangle clockwise, hole counter-clockwise)
            ctx.beginPath()
            ctx.rect(root.originX, root.originY, width, height)
            root.holePath(ctx, 0)
            ctx.fillStyle = root.fillColor
            ctx.fill()

            ctx.lineWidth = 1
            ctx.strokeStyle = root.outline
            ctx.beginPath()
            root.outlinePath(ctx)
            ctx.stroke()

            // melt the side panel / dock into the frame: put plain glass back over the hairline where they join
            ctx.fillStyle = root.fillColor
            if (root.cutRY1 > root.cutRY0) {
                var gx = root.holeX + root.holeW
                ctx.clearRect(gx, root.cutRY0, 2, root.cutRY1 - root.cutRY0)
                ctx.fillRect(gx, root.cutRY0, 2, root.cutRY1 - root.cutRY0)
            }
            if (root.cutBX1 > root.cutBX0) {
                var gy = root.holeY + root.holeH
                ctx.clearRect(root.cutBX0, gy, root.cutBX1 - root.cutBX0, 2)
                ctx.fillRect(root.cutBX0, gy, root.cutBX1 - root.cutBX0, 2)
            }
        }
    }
}
