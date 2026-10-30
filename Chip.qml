import QtQuick

// A bar button: icon + optional text. Width animates when text reveals or the chip
// appears/disappears, hover lights a soft pill, press squishes with a spring.
Item {
    id: chip

    property string icon: ""
    property string text: ""
    property bool shown: true
    property bool showText: false          // text always visible
    property bool revealOnHover: false     // text slides open while hovered
    property bool hoverFx: true            // light the soft pill while hovered
    property color iconColor: B.themeBlue
    property color textColor: "white"
    property color fillColor: "transparent"
    property color hoverColor: B.themeHover
    property string iconFont: "Segoe Fluent Icons"
    property real iconSize: 16
    property real textSize: 12
    property real minWidth: 0
    property Component iconComponent: null
    property real hitPad: 0                // extra clickable / hoverable height above and below the 28px look (bar chips use 4)
    property alias hovered: mouse.containsMouse
    property alias pressed: mouse.pressed

    signal activated(int button)
    signal wheeled(int delta)

    readonly property bool _textCapable: showText || revealOnHover
    readonly property bool _textOn: text !== "" && (showText || (revealOnHover && mouse.containsMouse))
    readonly property real _iconW: iconComponent ? iconLoader.width : iconText.implicitWidth
    readonly property real _gap: _iconW > 0 ? 6 : 0
    readonly property real _contentW: _iconW + (_textOn ? _gap + label.implicitWidth : 0)

    height: 28 + 2 * hitPad
    width: shown ? Math.max(minWidth, _contentW + 16) : 0
    opacity: shown ? 1 : 0
    visible: shown || width > 0.5
    clip: true

    Behavior on width { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 200 } }

    Item {
        id: body
        anchors.fill: parent
        anchors.topMargin: chip.hitPad
        anchors.bottomMargin: chip.hitPad
        scale: mouse.pressed ? 0.92 : 1
        Behavior on scale { SpringAnimation { spring: 6; damping: 0.4; epsilon: 0.005 } }

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: chip.fillColor.a > 0 ? chip.fillColor : chip.hoverColor
            opacity: chip.fillColor.a > 0 ? (mouse.containsMouse ? 0.88 : 1) : (mouse.containsMouse && chip.hoverFx ? 1 : 0)
            Behavior on opacity { NumberAnimation { duration: 180 } }
        }

        Item {
            id: content
            x: chip._textCapable ? 8 : (chip.width - chip._contentW) / 2
            width: chip._contentW
            height: parent.height

            Loader {
                id: iconLoader
                sourceComponent: chip.iconComponent
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                id: iconText
                visible: !chip.iconComponent
                anchors.verticalCenter: parent.verticalCenter
                text: chip.icon
                color: chip.iconColor
                font.family: chip.iconFont
                font.pixelSize: chip.iconSize
                Behavior on color { ColorAnimation { duration: 200 } }
            }
            Text {
                id: label
                x: chip._iconW + chip._gap
                anchors.verticalCenter: parent.verticalCenter
                text: chip.text
                color: chip.textColor
                font.family: "CaskaydiaCove NFP"
                font.pixelSize: chip.textSize
                font.weight: Font.DemiBold
                opacity: chip._textOn ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: (m) => chip.activated(m.button)
        onWheel: (w) => chip.wheeled(w.angleDelta.y)
    }
}
