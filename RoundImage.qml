import QtQuick
import QtQuick.Window

// Image with rounded corners, drawn on a Canvas (no shader/effect modules needed).
// Used for the album art (vapor.pyw saves it as a 256x256 square) and for the profile picture (vapor.pyw hands over a
// square copy shrunk to ~1.5x the pixels the card shows, see avatar_path()).
//
// Same properties as before (source, radius, cover), so Vapor.qml needs no change.
Item {
    id: root

    property string source: ""
    property real radius: 12
    property bool cover: false     // crop-to-fill instead of stretching (also used for the faint bar backdrop)

    readonly property real artSize: 256     // only used until the real picture size is known

    // Screen scaling (125 %, 150 %, 200 % ...). The canvas below is drawn in DEVICE pixels and shrunk back to the item's
    // size by the scene graph. A canvas at logical size gets stretched up on a scaled display, and a small round picture
    // then looks soft and blocky.
    readonly property real dpr: Math.max(1, Screen.devicePixelRatio)

    // The real size of the picture. `cover` used to assume 256x256, which is right for album art but crops (and zooms
    // into) the top-left corner of any bigger profile picture.
    Image {
        id: probe
        visible: false
        asynchronous: true
        source: root.source
        onStatusChanged: if (status === Image.Ready) c.requestPaint()
    }

    // A Canvas keeps every image it has ever loaded until unloadImage() is called. Every new song's art used to
    // stay in memory forever (3 copies each: bar backdrop, bar chip, popup); now the previous one is dropped.
    property string _loaded: ""
    onSourceChanged: {
        if (_loaded !== "" && _loaded !== source) c.unloadImage(_loaded)
        _loaded = source
        if (source !== "") c.loadImage(source)
        c.requestPaint()
    }
    onRadiusChanged: c.requestPaint()
    onCoverChanged: c.requestPaint()
    Component.onCompleted: if (source !== "") { _loaded = source; c.loadImage(source) }

    Canvas {
        id: c
        x: 0
        y: 0
        width: Math.max(1, Math.ceil(root.width * root.dpr))
        height: Math.max(1, Math.ceil(root.height * root.dpr))
        // back to the item's size (origin is the top-left corner)
        transform: Scale { xScale: root.width / c.width; yScale: root.height / c.height }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onImageLoaded: requestPaint()

        onPaint: {
            var w = width, h = height
            var ctx = getContext("2d")
            ctx.reset()
            if (w < 2 || h < 2) return
            ctx.clearRect(0, 0, w, h)
            try { ctx.imageSmoothingEnabled = true } catch (e) {}
            try { ctx.imageSmoothingQuality = "high" } catch (e) {}

            var src = root.source
            if (src !== "" && isImageLoaded(src)) {
                if (root.cover) {
                    var ready = probe.status === Image.Ready && probe.implicitWidth > 0 && probe.implicitHeight > 0
                    var iw = ready ? probe.implicitWidth : root.artSize
                    var ih = ready ? probe.implicitHeight : root.artSize
                    var k = Math.max(w / iw, h / ih)
                    var sw = w / k, sh = h / k
                    ctx.drawImage(src, (iw - sw) / 2, (ih - sh) / 2, sw, sh, 0, 0, w, h)
                } else {
                    ctx.drawImage(src, 0, 0, w, h)
                }
            } else {
                ctx.fillStyle = Qt.rgba(1, 1, 1, 0.08)
                ctx.fillRect(0, 0, w, h)
            }

            // Round the corners by erasing everything OUTSIDE the rounded rectangle. Unlike clip(), a fill is
            // anti-aliased, so the edge of a circle is smooth instead of staircased.
            var pxPerUnit = w / Math.max(1, root.width)        // device pixels per logical pixel
            var r = Math.max(0, Math.min(root.radius * pxPerUnit, w / 2, h / 2))
            ctx.globalCompositeOperation = "destination-out"
            ctx.fillStyle = "black"
            ctx.beginPath()
            ctx.moveTo(-2, -2)                    // the whole item (a bit bigger, so no edge line is left), clockwise ...
            ctx.lineTo(w + 2, -2)
            ctx.lineTo(w + 2, h + 2)
            ctx.lineTo(-2, h + 2)
            ctx.closePath()
            ctx.moveTo(r, 0)                      // ... minus the rounded rectangle, counter-clockwise
            if (r > 0.5) ctx.arcTo(0, 0, 0, r, r); else ctx.lineTo(0, 0)
            ctx.lineTo(0, h - r)
            if (r > 0.5) ctx.arcTo(0, h, r, h, r); else ctx.lineTo(0, h)
            ctx.lineTo(w - r, h)
            if (r > 0.5) ctx.arcTo(w, h, w, h - r, r); else ctx.lineTo(w, h)
            ctx.lineTo(w, r)
            if (r > 0.5) ctx.arcTo(w, 0, w - r, 0, r); else ctx.lineTo(w, 0)
            ctx.closePath()
            ctx.fill()
        }
    }
}
