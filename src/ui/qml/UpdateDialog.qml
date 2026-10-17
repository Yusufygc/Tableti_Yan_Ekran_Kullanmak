import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Uygulama içi güncelleme penceresi (UpdateViewModel: "updateViewModel" bağlam özelliği).
Popup {
    id: dlg
    objectName: "updateDialog"
    modal: true
    focus: true
    padding: 20
    anchors.centerIn: Overlay.overlay
    width: Math.min(Overlay.overlay ? Overlay.overlay.width - 40 : 520, 540)
    closePolicy: (updateViewModel && updateViewModel.busy) ? Popup.NoAutoClose : Popup.CloseOnEscape

    readonly property string st: updateViewModel ? updateViewModel.state : "idle"

    Connections {
        target: updateViewModel
        function onChanged() {
            if (updateViewModel.dialogOpen && !dlg.opened)
                dlg.open()
            else if (!updateViewModel.dialogOpen && dlg.opened)
                dlg.close()
        }
    }

    onClosed: if (updateViewModel && updateViewModel.dialogOpen) updateViewModel.closeDialog()

    background: Rectangle {
        color: "#161F30"
        radius: 12
        border.width: 1
        border.color: "#334155"
    }

    Overlay.modal: Rectangle { color: "#99000000" }

    component DialogButton: Rectangle {
        id: btn
        property string text: ""
        property bool primary: false
        signal activated()

        Layout.fillWidth: true
        implicitHeight: Math.max(40, label.implicitHeight + 18)
        radius: 8
        activeFocusOnTab: true
        color: primary ? (area.containsMouse ? "#7DD3FC" : "#38BDF8") : (area.containsMouse ? "#334155" : "#26334D")
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? "#F8FAFC" : (primary ? "transparent" : "#334155")

        Accessible.role: Accessible.Button
        Accessible.name: btn.text
        Accessible.focusable: true

        Keys.onReturnPressed: btn.activated()
        Keys.onEnterPressed: btn.activated()
        Keys.onSpacePressed: btn.activated()

        Text {
            id: label
            anchors.centerIn: parent
            width: parent.width - 20
            horizontalAlignment: Text.AlignHCenter
            text: btn.text
            font.family: "Segoe UI"
            font.pixelSize: 14
            font.bold: true
            color: btn.primary ? "#0B0F19" : "#F8FAFC"
            wrapMode: Text.WordWrap
        }

        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                btn.forceActiveFocus()
                btn.activated()
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: dlg.st === "available" ? "Yeni sürüm var" : "Güncelleme"
            font.family: "Segoe UI"
            font.pixelSize: 18
            font.bold: true
            color: "#F8FAFC"
            Accessible.role: Accessible.Heading
            Accessible.name: text
        }

        Text {
            objectName: "updateMessage"
            Layout.fillWidth: true
            visible: text.length > 0
            text: {
                if (!updateViewModel) return ""
                if (dlg.st === "available")
                    return "Sürüm " + updateViewModel.newVersion + " yayınlandı (yüklü sürüm: " + updateViewModel.currentVersion + ")."
                return updateViewModel.message
            }
            font.family: "Segoe UI"
            font.pixelSize: 14
            color: dlg.st === "error" ? "#FBBF24" : "#E2E8F0"
            wrapMode: Text.WordWrap
        }

        // Sürüm notları (düz metin)
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 130
            visible: dlg.st === "available" && updateViewModel && updateViewModel.notes.length > 0
            clip: true
            TextArea {
                readOnly: true
                text: updateViewModel ? updateViewModel.notes : ""
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                font.family: "Segoe UI"
                font.pixelSize: 12
                color: "#E2E8F0"
                background: Rectangle { color: "#0F172A"; radius: 6 }
                Accessible.name: "Sürüm notları"
            }
        }

        ProgressBar {
            objectName: "updateProgress"
            Layout.fillWidth: true
            visible: dlg.st === "downloading"
            from: 0
            to: 1
            value: updateViewModel ? updateViewModel.progress : 0
            Accessible.name: "İndirme ilerlemesi"
        }

        BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: dlg.st === "checking" || dlg.st === "installing" || dlg.st === "waiting"
            visible: running
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            DialogButton {
                objectName: "updateNowButton"
                visible: dlg.st === "available"
                text: "Güncelle"
                primary: true
                onActivated: if (updateViewModel) updateViewModel.startUpdate()
            }
            DialogButton {
                objectName: "skipVersionButton"
                visible: dlg.st === "available"
                text: "Bu Sürümü Atla"
                onActivated: if (updateViewModel) updateViewModel.skipVersion()
            }
            DialogButton {
                objectName: "stopWaitingButton"
                visible: dlg.st === "waiting"
                text: "Beklemeyi Bırak"
                onActivated: if (updateViewModel) updateViewModel.stopWaiting()
            }
            DialogButton {
                objectName: "releasePageButton"
                visible: dlg.st === "blocked" || dlg.st === "error"
                text: "Sürüm Sayfası"
                onActivated: if (updateViewModel) updateViewModel.openReleasePage()
            }
            DialogButton {
                objectName: "closeUpdateButton"
                visible: dlg.st !== "downloading" && dlg.st !== "installing" && dlg.st !== "checking"
                text: dlg.st === "available" ? "Sonra" : "Kapat"
                onActivated: if (updateViewModel) updateViewModel.closeDialog()
            }
        }
    }
}
