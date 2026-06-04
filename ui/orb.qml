import QtQuick
import QtQuick.Controls

Window {
    id: root
    width: 350
    height: isExpanded ? 420 : 350
    visible: true
    title: "Aurora Core"
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

    property bool isExpanded: false

    // Window dragging logic
    MouseArea {
        id: dragArea
        anchors.fill: parent
        property point lastMousePos: "0,0"
        onPressed: (mouse) => {
            lastMousePos = Qt.point(mouse.x, mouse.y)
        }
        onPositionChanged: (mouse) => {
            var delta = Qt.point(mouse.x - lastMousePos.x, mouse.y - lastMousePos.y)
            root.x += delta.x
            root.y += delta.y
        }
    }

    // Dynamic states and properties of the orb
    Item {
        id: coreContainer
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: 350
        height: 350

        property string currentState: "sleeping" // "sleeping", "idle", "thinking", "executing", "speaking", "error"
        property double pulseVal: 0.0
        property double rotationAngle: 0.0
        
        // Connections to Python EventBridge
        Connections {
            target: eventBridge
            function onStateChanged(newState) {
                coreContainer.currentState = newState
            }
        }

        // Click on core area to toggle text input panel expansion
        MouseArea {
            anchors.centerIn: parent
            width: 150
            height: 150
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.isExpanded = !root.isExpanded
                if (root.isExpanded) {
                    textField.forceActiveFocus()
                }
            }
        }

        // Dynamic speed pulsing
        NumberAnimation {
            id: pulseAnimation
            target: coreContainer
            property: "pulseVal"
            from: 0.0
            to: 1.0
            duration: {
                if (coreContainer.currentState === "executing") return 600
                if (coreContainer.currentState === "thinking") return 800
                if (coreContainer.currentState === "speaking") return 300
                if (coreContainer.currentState === "sleeping") return 3000
                return 2000 // idle
            }
            loops: Animation.Infinite
            running: true
        }

        // Dynamic speed rotations
        NumberAnimation {
            id: rotationAnimation
            target: coreContainer
            property: "rotationAngle"
            from: 0.0
            to: 360.0
            duration: {
                if (coreContainer.currentState === "thinking") return 1500
                if (coreContainer.currentState === "executing") return 3000
                return 8000 // idle / speaking
            }
            loops: Animation.Infinite
            running: true
        }

        Canvas {
            id: canvas
            anchors.fill: parent
            
            onPulseValChanged: requestPaint()
            onRotationAngleChanged: requestPaint()
            onCurrentStateChanged: requestPaint()

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                
                var cx = width / 2
                var cy = height / 2
                var pulse = coreContainer.pulseVal
                var angle = (coreContainer.rotationAngle * Math.PI) / 180
                var state = coreContainer.currentState
                
                // Set color palettes dynamically based on state
                var coreColor = "rgba(59, 130, 246, 0.85)"  // Neon Blue
                var glowColor = "rgba(59, 130, 246, 0.35)"
                var ringColor = "rgba(96, 165, 250, 0.65)"
                
                if (state === "sleeping") {
                    coreColor = "rgba(100, 116, 139, 0.45)" // Slate Grey
                    glowColor = "rgba(100, 116, 139, 0.15)"
                    ringColor = "rgba(148, 163, 184, 0.25)"
                } else if (state === "thinking") {
                    coreColor = "rgba(168, 85, 247, 0.9)"  // Violet
                    glowColor = "rgba(168, 85, 247, 0.45)"
                    ringColor = "rgba(192, 132, 252, 0.7)"
                } else if (state === "executing") {
                    coreColor = "rgba(16, 185, 129, 0.95)" // Emerald Green
                    glowColor = "rgba(16, 185, 129, 0.5)"
                    ringColor = "rgba(52, 211, 153, 0.75)"
                } else if (state === "speaking") {
                    coreColor = "rgba(249, 115, 22, 0.95)"  // Safety Orange
                    glowColor = "rgba(249, 115, 22, 0.5)"
                    ringColor = "rgba(251, 146, 60, 0.75)"
                } else if (state === "error") {
                    coreColor = "rgba(239, 68, 68, 0.95)"  // Crimson Red
                    glowColor = "rgba(239, 68, 68, 0.45)"
                    ringColor = "rgba(248, 113, 113, 0.7)"
                }
                
                // 1. Draw dynamic background radial glow
                var radiusGlow = 60 + Math.sin(pulse * Math.PI) * 15
                if (state === "speaking") {
                    radiusGlow = 60 + Math.random() * 20 // Speaks jitter
                }
                var grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, radiusGlow * 1.7)
                grad.addColorStop(0, coreColor)
                grad.addColorStop(0.3, glowColor)
                grad.addColorStop(1, "rgba(0,0,0,0)")
                
                ctx.fillStyle = grad
                ctx.beginPath()
                ctx.arc(cx, cy, radiusGlow * 1.7, 0, Math.PI * 2)
                ctx.fill()
                
                // 2. Draw central orb sphere
                var radiusCore = 35 + Math.sin(pulse * Math.PI) * 3
                if (state === "speaking") {
                    radiusCore = 35 + Math.random() * 6
                }
                ctx.shadowBlur = 25
                ctx.shadowColor = coreColor
                ctx.fillStyle = coreColor
                ctx.beginPath()
                ctx.arc(cx, cy, radiusCore, 0, Math.PI * 2)
                ctx.fill()
                ctx.shadowBlur = 0 // Reset shadow
                
                // 3. Draw outer orbital rings
                ctx.strokeStyle = ringColor
                ctx.lineWidth = 2.5
                
                // Inner ring (Clockwise)
                ctx.save()
                ctx.translate(cx, cy)
                ctx.rotate(angle)
                ctx.beginPath()
                ctx.arc(0, 0, 85, 0, Math.PI * 1.4)
                ctx.stroke()
                
                // Satellite node
                ctx.fillStyle = ringColor
                ctx.beginPath()
                ctx.arc(85, 0, 5, 0, Math.PI * 2)
                ctx.fill()
                ctx.restore()
                
                // Nested counter-rotating rings (Double arcs)
                ctx.save()
                ctx.translate(cx, cy)
                ctx.rotate(-angle * 1.6)
                ctx.beginPath()
                ctx.arc(0, 0, 105, 0, Math.PI * 0.75)
                ctx.stroke()
                
                ctx.beginPath()
                ctx.arc(0, 0, 105, Math.PI, Math.PI * 1.75)
                ctx.stroke()
                ctx.restore()
                
                // Outer slow orbit
                ctx.save()
                ctx.translate(cx, cy)
                ctx.rotate(angle * 0.4)
                ctx.strokeStyle = "rgba(255, 255, 255, 0.12)"
                ctx.lineWidth = 1.5
                ctx.beginPath()
                ctx.arc(0, 0, 125, 0, Math.PI * 2)
                ctx.stroke()
                
                ctx.fillStyle = glowColor
                ctx.beginPath()
                ctx.arc(125, 0, 6, 0, Math.PI * 2)
                ctx.fill()
                ctx.restore()
            }
        }
    }

    // Sleek Expandable Text Command Panel
    Rectangle {
        id: inputPanel
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: 300
        height: 48
        color: "#131a26"
        border.color: "#1e293b"
        border.width: 1.5
        radius: 12
        visible: root.isExpanded
        opacity: root.isExpanded ? 1.0 : 0.0
        
        Behavior on opacity { NumberAnimation { duration: 200 } }
        
        TextField {
            id: textField
            anchors.fill: parent
            anchors.margins: 4
            placeholderText: "Type command and press Enter..."
            color: "#f8fafc"
            placeholderTextColor: "#64748b"
            verticalAlignment: TextInput.AlignVCenter
            leftPadding: 12
            background: Rectangle { color: "transparent" }
            font.family: "Segoe UI"
            font.pixelSize: 13
            
            onAccepted: {
                if (text.trim() !== "") {
                    eventBridge.submitCommand(text.trim())
                    text = ""
                    root.isExpanded = false
                }
            }
        }
    }
}
