import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: rootWindow
    visible: false
    width: 860
    height: 660
    minimumWidth: 620
    minimumHeight: 520
    color: "#0B0F19"
    title: viewModel ? viewModel.windowTitle : "TabScreen USB"

    // Pencere daraldığında (veya küçük/yüksek ölçekli monitörde) 3 sütun yerine tek sütuna geçiş
    readonly property bool isCompact: rootWindow.width < 740

    // --- Erişilebilir ve Odak Halkalı Özel Bileşenler ---

    component ActionButton: Rectangle {
        id: btnRoot
        property string text: ""
        property string accessibleLabel: text
        property bool primary: false
        property bool warningStyle: false
        property bool boldText: false
        signal activated()

        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(40, btnLabel.implicitHeight + 18)
        implicitHeight: Math.max(40, btnLabel.implicitHeight + 18)
        implicitWidth: Math.max(120, btnLabel.implicitWidth + 24)
        radius: 8
        activeFocusOnTab: true
        color: {
            if (!enabled) return "#1E293B"
            if (warningStyle) return btnMouse.containsMouse ? "#FCD34D" : "#FBBF24"
            if (primary) return btnMouse.containsMouse ? "#7DD3FC" : "#38BDF8"
            return btnMouse.containsMouse ? "#334155" : "#26334D"
        }
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? "#F8FAFC" : (primary || warningStyle ? "transparent" : "#334155")

        Accessible.role: Accessible.Button
        Accessible.name: btnRoot.accessibleLabel
        Accessible.focusable: true

        Keys.onReturnPressed: if (enabled) btnRoot.activated()
        Keys.onEnterPressed: if (enabled) btnRoot.activated()
        Keys.onSpacePressed: if (enabled) btnRoot.activated()

        Text {
            id: btnLabel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: btnRoot.text
            font.family: "Segoe UI"
            font.pixelSize: 13
            font.bold: btnRoot.boldText || btnRoot.primary || btnRoot.warningStyle
            color: (btnRoot.primary || btnRoot.warningStyle) ? "#0B0F19" : "#F8FAFC"
        }

        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                btnRoot.forceActiveFocus()
                if (btnRoot.enabled) btnRoot.activated()
            }
        }
    }

    component ModeOptionCard: Rectangle {
        id: modeCard
        property string modeKey: "auto"
        property string titleText: ""
        property string subtitleText: ""
        property bool selected: viewModel ? (viewModel.mode === modeKey) : false

        Layout.fillWidth: true
        Layout.preferredHeight: modeCol.implicitHeight + 22
        implicitHeight: modeCol.implicitHeight + 22
        radius: 8
        activeFocusOnTab: true
        color: selected ? "#1E293B" : "#0F172A"
        border.width: activeFocus || selected ? 2 : 1
        border.color: activeFocus ? "#F8FAFC" : (selected ? "#38BDF8" : "#26334D")

        Accessible.role: Accessible.RadioButton
        Accessible.name: titleText + " - " + subtitleText
        Accessible.checked: selected
        Accessible.focusable: true

        Keys.onReturnPressed: if (viewModel) viewModel.setMode(modeKey)
        Keys.onEnterPressed: if (viewModel) viewModel.setMode(modeKey)
        Keys.onSpacePressed: if (viewModel) viewModel.setMode(modeKey)

        ColumnLayout {
            id: modeCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 11
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    width: 14
                    height: 14
                    radius: 7
                    color: modeCard.selected ? "#38BDF8" : "transparent"
                    border.width: 2
                    border.color: modeCard.selected ? "#38BDF8" : "#94A3B8"
                }

                Text {
                    Layout.fillWidth: true
                    text: modeCard.titleText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    font.bold: true
                    color: "#F8FAFC"
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                Layout.fillWidth: true
                text: modeCard.subtitleText
                font.family: "Segoe UI"
                font.pixelSize: 12
                color: "#E2E8F0"
                wrapMode: Text.WordWrap
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                modeCard.forceActiveFocus()
                if (viewModel) viewModel.setMode(modeCard.modeKey)
            }
        }
    }

    // Doğrudan Flickable + ortalanmış maksimum genişlik sarmalayıcısı (Büyük/küçük her monitörde bozulmasız)
    Flickable {
        id: mainFlickable
        anchors.fill: parent
        contentWidth: width
        contentHeight: contentColumn.implicitHeight + 36
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }

        ColumnLayout {
            id: contentColumn
            width: Math.min(mainFlickable.width - 40, 1020)
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 18
            spacing: 14

            // --- ÜST BAŞLIK ---
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        Layout.fillWidth: true
                        text: "TabScreen USB — 3. Ekran (Android Tablet) Yöneticisi"
                        font.family: "Segoe UI"
                        font.pixelSize: 19
                        font.bold: true
                        color: "#F8FAFC"
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        radius: 999
                        color: (viewModel && viewModel.isRunning) ? "#14532D" : "#1E293B"
                        border.width: 1
                        border.color: (viewModel && viewModel.isRunning) ? "#4ADE80" : "#334155"
                        Layout.preferredWidth: liveBadgeText.implicitWidth + 24
                        Layout.preferredHeight: 28
                        implicitWidth: liveBadgeText.implicitWidth + 24
                        implicitHeight: 28

                        Text {
                            id: liveBadgeText
                            anchors.centerIn: parent
                            text: (viewModel && viewModel.isRunning) ? "● YAYIN AKTİF" : "● BEKLEMEDE"
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            font.bold: true
                            color: (viewModel && viewModel.isRunning) ? "#4ADE80" : "#E2E8F0"
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: "%100 Yerel (127.0.0.1 Loopback) · Sıfır Telemetri · Dokunmatik ve Fare İmleci Destekli"
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    color: "#E2E8F0"
                    wrapMode: Text.WordWrap
                }
            }

            // --- 1. KART: EKRAN TOPOLOJİSİ VE SEÇİMİ ---
            Rectangle {
                id: displayCard
                objectName: "displayCard"
                Layout.fillWidth: true
                Layout.preferredHeight: displayCol.implicitHeight + 32
                implicitHeight: displayCol.implicitHeight + 32
                radius: 12
                color: "#161F30"
                border.width: 1
                border.color: "#26334D"

                ColumnLayout {
                    id: displayCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        Layout.fillWidth: true
                        text: "1. Aktarılacak Ekran Seçimi ve Çoklu Monitör Dizilimi"
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#F8FAFC"
                        wrapMode: Text.WordWrap
                    }

                    // Görsel Tıklanabilir Ekran Kartları (Pencere genişliğine göre esnek GridLayout)
                    GridLayout {
                        id: monitorStrip
                        Layout.fillWidth: true
                        columns: rootWindow.isCompact ? 1 : Math.max(1, (viewModel && viewModel.monitorsModel) ? viewModel.monitorsModel.length : 3)
                        rowSpacing: 8
                        columnSpacing: 10

                        Repeater {
                            model: viewModel ? viewModel.monitorsModel : []

                            delegate: Rectangle {
                                id: monItem
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: monCardCol.implicitHeight + 20
                                implicitHeight: monCardCol.implicitHeight + 20
                                radius: 8
                                activeFocusOnTab: true
                                color: modelData.selected ? "#38BDF8" : "#0F172A"
                                border.width: activeFocus ? 2 : 1
                                border.color: activeFocus ? "#F8FAFC" : (modelData.selected ? "#38BDF8" : "#334155")

                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.label
                                Accessible.focusable: true

                                Keys.onReturnPressed: if (viewModel) viewModel.selectMonitor(modelData.index)
                                Keys.onEnterPressed: if (viewModel) viewModel.selectMonitor(modelData.index)
                                Keys.onSpacePressed: if (viewModel) viewModel.selectMonitor(modelData.index)

                                ColumnLayout {
                                    id: monCardCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.margins: 8
                                    spacing: 2

                                    Text {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignHCenter
                                        wrapMode: Text.WordWrap
                                        text: "[" + modelData.index + "] " + modelData.role
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                        font.bold: true
                                        color: modelData.selected ? "#0B0F19" : "#F8FAFC"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignHCenter
                                        text: modelData.resolution
                                        font.family: "Segoe UI"
                                        font.pixelSize: 12
                                        color: modelData.selected ? "#0B0F19" : "#E2E8F0"
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        monItem.forceActiveFocus()
                                        if (viewModel) viewModel.selectMonitor(modelData.index)
                                    }
                                }
                            }
                        }
                    }

                    // Ekran Aksiyon Düğmeleri
                    GridLayout {
                        Layout.fillWidth: true
                        columns: rootWindow.isCompact ? 1 : 3
                        rowSpacing: 8
                        columnSpacing: 10

                        ActionButton {
                            objectName: "refreshMonitorsButton"
                            text: "Ekranları Yenile"
                            onActivated: if (viewModel) viewModel.refreshTopology()
                        }

                        ActionButton {
                            objectName: "extendDisplaysButton"
                            text: "Masaüstünü Uzat (Extend)"
                            onActivated: if (viewModel) viewModel.extendDisplays()
                        }

                        ActionButton {
                            objectName: "installVddButton"
                            text: "3. Sanal Ekranı Kur (VDD)"
                            primary: true
                            boldText: true
                            onActivated: if (viewModel) viewModel.installVirtualDisplay()
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: viewModel ? viewModel.topologyMessage : ""
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        color: (viewModel && viewModel.isThirdScreenReady) ? "#4ADE80" : "#FBBF24"
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // --- 2. KART: GÖRÜNTÜ MODU VE DOKUNMATİK KONTROL ---
            Rectangle {
                id: optionsCard
                objectName: "optionsCard"
                Layout.fillWidth: true
                Layout.preferredHeight: optionsCol.implicitHeight + 32
                implicitHeight: optionsCol.implicitHeight + 32
                radius: 12
                color: "#161F30"
                border.width: 1
                border.color: "#26334D"

                ColumnLayout {
                    id: optionsCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 10

                    Text {
                        Layout.fillWidth: true
                        text: "2. Görüntü Modu ve Dokunmatik Kontrol"
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#F8FAFC"
                        wrapMode: Text.WordWrap
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: rootWindow.isCompact ? 1 : 3
                        rowSpacing: 8
                        columnSpacing: 10

                        ModeOptionCard {
                            objectName: "modeAutoButton"
                            modeKey: "auto"
                            titleText: "Otomatik Kip (Önerilen)"
                            subtitleText: "Akıcı 40 FPS · Durulunca q92 keskin kare"
                        }

                        ModeOptionCard {
                            objectName: "modeReadingButton"
                            modeKey: "reading"
                            titleText: "Okuma / Kod Modu"
                            subtitleText: "4:4:4 Keskin Metin · 30 FPS"
                        }

                        ModeOptionCard {
                            objectName: "modeVideoButton"
                            modeKey: "video"
                            titleText: "Video / Akıcı Mod"
                            subtitleText: "4:2:0 Hızlı Sıkıştırma · 45 FPS"
                        }
                    }

                    // Dokunmatik Anahtarı
                    Rectangle {
                        id: touchToggleRow
                        objectName: "touchToggleButton"
                        Layout.fillWidth: true
                        Layout.preferredHeight: touchRowLayout.implicitHeight + 20
                        implicitHeight: touchRowLayout.implicitHeight + 20
                        radius: 8
                        color: "#0F172A"
                        border.width: activeFocus ? 2 : 1
                        border.color: activeFocus ? "#F8FAFC" : "#26334D"
                        activeFocusOnTab: true

                        Accessible.role: Accessible.CheckBox
                        Accessible.name: "Tabletten Dokunmatik Kontrolü Etkinleştir"
                        Accessible.checked: viewModel ? viewModel.touchEnabled : true
                        Accessible.focusable: true

                        Keys.onReturnPressed: if (viewModel) viewModel.setTouchEnabled(!viewModel.touchEnabled)
                        Keys.onEnterPressed: if (viewModel) viewModel.setTouchEnabled(!viewModel.touchEnabled)
                        Keys.onSpacePressed: if (viewModel) viewModel.setTouchEnabled(!viewModel.touchEnabled)

                        RowLayout {
                            id: touchRowLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 10
                            spacing: 10

                            Rectangle {
                                width: 20
                                height: 20
                                radius: 4
                                color: (viewModel && viewModel.touchEnabled) ? "#38BDF8" : "transparent"
                                border.width: 2
                                border.color: (viewModel && viewModel.touchEnabled) ? "#38BDF8" : "#94A3B8"

                                Text {
                                    anchors.centerIn: parent
                                    visible: viewModel ? viewModel.touchEnabled : true
                                    text: "✓"
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: "#0B0F19"
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Tabletten Dokunmatik Kontrol (Tıklama, Sürükleme, 520 ms Uzun Basma Sağ Tık, İki Parmak Kaydırma)"
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                                color: "#E2E8F0"
                                wrapMode: Text.WordWrap
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                touchToggleRow.forceActiveFocus()
                                if (viewModel) viewModel.setTouchEnabled(!viewModel.touchEnabled)
                            }
                        }
                    }
                }
            }

            // --- 3. KART: USB ADB TÜNELİ VE YAYIN KONTROLÜ ---
            Rectangle {
                id: actionCard
                objectName: "actionCard"
                Layout.fillWidth: true
                Layout.preferredHeight: actionCol.implicitHeight + 32
                implicitHeight: actionCol.implicitHeight + 32
                radius: 12
                color: "#161F30"
                border.width: 1
                border.color: "#26334D"

                ColumnLayout {
                    id: actionCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 8

                    Text {
                        Layout.fillWidth: true
                        text: "3. USB ADB Tüneli ve Yayın Kontrolü"
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#F8FAFC"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: viewModel ? viewModel.adbStatusText : ""
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        color: "#E2E8F0"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: viewModel ? viewModel.statusText : ""
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        font.bold: true
                        color: "#4ADE80"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        text: viewModel ? viewModel.liveMetricsText : ""
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        color: "#E2E8F0"
                        wrapMode: Text.WordWrap
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        columns: rootWindow.isCompact ? 1 : 3
                        rowSpacing: 8
                        columnSpacing: 10

                        ActionButton {
                            objectName: "setupTunnelButton"
                            text: "1) USB ADB Tünelini Kur"
                            boldText: true
                            onActivated: if (viewModel) viewModel.setupUsbTunnel()
                        }

                        ActionButton {
                            objectName: "toggleStreamButton"
                            text: (viewModel && viewModel.isRunning) ? "Yayını Durdur" : "2) Yayını Başlat (127.0.0.1:8765)"
                            primary: !(viewModel && viewModel.isRunning)
                            warningStyle: (viewModel && viewModel.isRunning)
                            boldText: true
                            onActivated: if (viewModel) viewModel.toggleStreaming()
                        }

                        ActionButton {
                            objectName: "previewBrowserButton"
                            text: "Tarayıcıda Test Et"
                            onActivated: if (viewModel) viewModel.openBrowserPreview()
                        }
                    }
                }
            }

            // --- 4. KART: GÜNCELLEMELER ---
            Rectangle {
                id: updateCard
                objectName: "updateCard"
                Layout.fillWidth: true
                Layout.preferredHeight: updateCol.implicitHeight + 32
                implicitHeight: updateCol.implicitHeight + 32
                radius: 12
                color: "#161F30"
                border.width: 1
                border.color: "#26334D"

                ColumnLayout {
                    id: updateCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 10

                    Text {
                        Layout.fillWidth: true
                        text: "4. Güncellemeler"
                        font.family: "Segoe UI"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#F8FAFC"
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        objectName: "updateStatusText"
                        Layout.fillWidth: true
                        text: updateViewModel ? updateViewModel.statusLine : ""
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        color: "#E2E8F0"
                        wrapMode: Text.WordWrap
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: rootWindow.isCompact ? 1 : 2
                        rowSpacing: 8
                        columnSpacing: 10
                        uniformCellWidths: true

                        ActionButton {
                            objectName: "checkUpdateButton"
                            text: "Güncellemeleri Denetle"
                            enabled: updateViewModel ? !updateViewModel.busy : false
                            onActivated: if (updateViewModel) updateViewModel.checkNow()
                        }

                        Rectangle {
                            id: startupCheckRow
                            objectName: "startupCheckToggle"
                            Layout.fillWidth: true
                            implicitHeight: 40
                            implicitWidth: 260
                            radius: 8
                            color: "#0F172A"
                            border.width: activeFocus ? 2 : 1
                            border.color: activeFocus ? "#F8FAFC" : "#26334D"
                            activeFocusOnTab: true

                            Accessible.role: Accessible.CheckBox
                            Accessible.name: "Açılışta güncellemeleri denetle"
                            Accessible.checked: updateViewModel ? updateViewModel.checkOnStartup : true
                            Accessible.focusable: true

                            Keys.onReturnPressed: if (updateViewModel) updateViewModel.setCheckOnStartup(!updateViewModel.checkOnStartup)
                            Keys.onEnterPressed: if (updateViewModel) updateViewModel.setCheckOnStartup(!updateViewModel.checkOnStartup)
                            Keys.onSpacePressed: if (updateViewModel) updateViewModel.setCheckOnStartup(!updateViewModel.checkOnStartup)

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 10

                                Rectangle {
                                    width: 20
                                    height: 20
                                    radius: 4
                                    color: (updateViewModel && updateViewModel.checkOnStartup) ? "#38BDF8" : "transparent"
                                    border.width: 2
                                    border.color: (updateViewModel && updateViewModel.checkOnStartup) ? "#38BDF8" : "#94A3B8"

                                    Text {
                                        anchors.centerIn: parent
                                        visible: updateViewModel ? updateViewModel.checkOnStartup : true
                                        text: "✓"
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                        font.bold: true
                                        color: "#0B0F19"
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Açılışta güncellemeleri denetle"
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                    color: "#E2E8F0"
                                    elide: Text.ElideRight
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    startupCheckRow.forceActiveFocus()
                                    if (updateViewModel) updateViewModel.setCheckOnStartup(!updateViewModel.checkOnStartup)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    UpdateDialog { }
}
