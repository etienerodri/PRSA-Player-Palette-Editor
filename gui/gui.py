from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QLabel, QSizePolicy, QScrollArea, QGridLayout, QListWidget, QListWidgetItem, QLineEdit, QColorDialog, QMessageBox
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QFont, QColor, QPalette, QPixmap, QImage, QPainter, QWheelEvent, QRegularExpressionValidator
from pathlib import Path
from load.romextractor import RomExtractorHandler
from load.romsaver import RomSaverHandler
from render.characterrender import CharacterRenderer

class Theme:
    WIN_BG = '#111927'
    SIDEBAR_BG = '#161F35'
    CANVAS_BG = '#0F1622'
    BTN_ACTIVE_BG = '#1C2C4E'
    BTN_ACTIVE_BDR = '#6A8AB0'
    BTN_ACTIVE_TXT = '#D6E8FF'
    BTN_INACTIVE_BG = '#111927'
    BTN_INACTIVE_BDR = '#2B3D5C'
    BTN_INACTIVE_TXT = '#4A6282'
    BTN_HOVER_BG = '#243565'
    BTN_PRESS_BG = '#0D1526'
    PANEL_BG = '#111927'
    PANEL_OUTER_BDR = '#2B3D5C'
    PANEL_INNER_BDR = '#1E2E4A'
    DIVIDER = '#1E2E4A'
    CANVAS_TXT = '#2E4060'
    STATUS_BG = '#0D1526'
    STATUS_TXT = '#3A5478'
    STATUS_VAL = '#7A9EC0'
    ZOOM_BTN_BG = '#161F35'
    ZOOM_BTN_BDR = '#2B3D5C'
    ZOOM_BTN_TXT = '#7A9EC0'
    LOADING_TXT = '#3A5478'
    TOOLBAR_BG = '#161F35'
    TOOLBAR_BTN_BG = '#1C2C4E'
    TOOLBAR_BTN_BDR = '#2B3D5C'
    TOOLBAR_BTN_TXT = '#7A9EC0'
    TOOLBAR_BTN_ON_BG = '#1A3A5C'
    TOOLBAR_BTN_ON_BDR = '#4A8AB0'
    TOOLBAR_BTN_ON_TXT = '#90C8F0'
ZOOM_MIN = 0.5
ZOOM_MAX = 16.0
ZOOM_STEP = 0.5

class SidebarButton(QPushButton):

    def __init__(self, label: str, active: bool=True, parent=None):
        super().__init__(label, parent)
        self._active = active
        font = QFont('Segoe UI', 9)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_style()

    def _apply_style(self):
        bg = Theme.BTN_ACTIVE_BG if self._active else Theme.BTN_INACTIVE_BG
        bdr = Theme.BTN_ACTIVE_BDR if self._active else Theme.BTN_INACTIVE_BDR
        txt = Theme.BTN_ACTIVE_TXT if self._active else Theme.BTN_INACTIVE_TXT
        self.setStyleSheet(f'\n            QPushButton {{\n                background-color : {bg}; color : {txt};\n                border : 1px solid {bdr}; border-radius : 12px;\n                text-align : center; padding : 0 12px;\n            }}\n            QPushButton:hover {{ background-color : {Theme.BTN_HOVER_BG}; border-color : #8AAED4; color : #FFFFFF; }}\n            QPushButton:pressed {{ background-color : {Theme.BTN_PRESS_BG}; }}\n            QPushButton:disabled {{ background-color : {Theme.BTN_INACTIVE_BG}; color : {Theme.BTN_INACTIVE_TXT}; border-color : {Theme.BTN_INACTIVE_BDR}; }}\n        ')

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

class TopToolbarButton(QPushButton):

    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self._on = False
        font = QFont('Segoe UI', 8)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self.setMinimumWidth(72)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._apply_style()

    def _apply_style(self):
        bg = Theme.TOOLBAR_BTN_ON_BG if self._on else Theme.TOOLBAR_BTN_BG
        bdr = Theme.TOOLBAR_BTN_ON_BDR if self._on else Theme.TOOLBAR_BTN_BDR
        txt = Theme.TOOLBAR_BTN_ON_TXT if self._on else Theme.TOOLBAR_BTN_TXT
        self.setStyleSheet(f'\n            QPushButton {{ background-color : {bg}; color : {txt}; border : 1px solid {bdr}; border-radius : 6px; padding : 0 12px; }}\n            QPushButton:hover {{ background-color : {Theme.BTN_HOVER_BG}; border-color : #4A6890; color : #C8D8EC; }}\n            QPushButton:pressed {{ background-color : {Theme.BTN_PRESS_BG}; }}\n            QPushButton:disabled {{ background-color : {Theme.BTN_INACTIVE_BG}; color : {Theme.BTN_INACTIVE_TXT}; border-color : {Theme.BTN_INACTIVE_BDR}; }}\n        ')

    def set_on(self, state: bool):
        self._on = state
        self._apply_style()

class TopToolbar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f'QWidget {{ background-color : {Theme.TOOLBAR_BG}; border : 1px solid {Theme.PANEL_OUTER_BDR}; border-radius : 8px; }}')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        self.btn_load_rom = TopToolbarButton('LOAD ROM')
        self.btn_save_rom = TopToolbarButton('SAVE ROM')
        layout.addWidget(self.btn_load_rom)
        layout.addWidget(self.btn_save_rom)
        layout.addStretch()

class InsetPanel(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName('outerPanel')
        self.setStyleSheet(f'QFrame#outerPanel {{ background-color : {Theme.PANEL_BG}; border : 1px solid {Theme.PANEL_OUTER_BDR}; border-radius : 12px; }}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self._inner = QFrame(self)
        self._inner.setObjectName('innerPanel')
        self._inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._inner.setStyleSheet(f'QFrame#innerPanel {{ background-color : {Theme.PANEL_BG}; border : 1px solid {Theme.PANEL_INNER_BDR}; border-radius : 8px; }}')
        layout.addWidget(self._inner)

    def inner_frame(self) -> QFrame:
        return self._inner

class Sidebar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f'QWidget {{ background-color : {Theme.SIDEBAR_BG}; border-right : 1px solid {Theme.DIVIDER}; }}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)
        self.btn_sprites = SidebarButton('CHARACTER SPRITES', active=True)
        layout.addWidget(self.btn_sprites)
        self.sprite_list_panel = InsetPanel()
        self.sprite_list = QListWidget(self.sprite_list_panel.inner_frame())
        self.sprite_list.setStyleSheet(f'\n            QListWidget {{\n                background-color: transparent; border: none; outline: none;\n                color: {Theme.BTN_ACTIVE_TXT}; font-size: 13px; font-weight: bold;\n            }}\n            QListWidget::item {{\n                padding: 12px; border-bottom: 1px solid {Theme.DIVIDER};\n            }}\n            QListWidget::item:selected {{\n                background-color: {Theme.BTN_HOVER_BG};\n                border-left: 4px solid #8AAED4;\n                color: white;\n            }}\n            QListWidget::item:hover {{\n                background-color: {Theme.TOOLBAR_BTN_ON_BG};\n            }}\n        ')
        list_layout = QVBoxLayout(self.sprite_list_panel.inner_frame())
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self.sprite_list)
        layout.addWidget(self.sprite_list_panel, stretch=1)

class ZoomButton(QPushButton):

    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont('Segoe UI', 11))
        self.setStyleSheet(f'\n            QPushButton {{ background-color : {Theme.ZOOM_BTN_BG}; color : {Theme.ZOOM_BTN_TXT}; border : 1px solid {Theme.ZOOM_BTN_BDR}; border-radius : 6px; }}\n            QPushButton:hover {{ background-color : {Theme.BTN_HOVER_BG}; color : #FFFFFF; border-color : #4A6890; }}\n            QPushButton:pressed, QPushButton:checked {{ background-color : {Theme.BTN_ACTIVE_BG}; color : #FFFFFF; border-color : #8AAED4; }}\n        ')

class SpriteCanvas(QWidget):
    zoom_changed = pyqtSignal(float)
    frame_changed = pyqtSignal(int, int)
    pixmap_changed = pyqtSignal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmaps = []
        self._current_index = 0
        self._zoom = 4.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f'QScrollArea {{ background-color : {Theme.CANVAS_BG}; border : none; }}')
        self._container = QWidget()
        self._container.setStyleSheet('background-color: transparent;')
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label = QLabel()
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sprite_label.setStyleSheet('background-color: transparent; border: none;')
        self._layout.addWidget(self._sprite_label)
        self._scroll.setWidget(self._container)
        self._placeholder = QLabel('No Sprite Loaded\nSelect a ROM or Player file to begin.')
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setFont(QFont('Segoe UI', 12))
        self._placeholder.setStyleSheet(f'color: {Theme.CANVAS_TXT}; background: transparent; border: none;')
        layout.addWidget(self._placeholder)
        layout.addWidget(self._scroll)
        self._scroll.hide()

    def show_placeholder(self):
        self._pixmaps = []
        self._current_index = 0
        self._scroll.hide()
        self._placeholder.show()
        self.frame_changed.emit(0, 0)
        self.pixmap_changed.emit(QPixmap())

    def show_sprites(self, pixmaps: list[QPixmap]):
        self._pixmaps = pixmaps
        self._current_index = 0
        self._placeholder.hide()
        if not pixmaps:
            self.show_placeholder()
            return
        self._update_display()
        self._scroll.show()

    def update_sprites(self, pixmaps: list[QPixmap]):
        self._pixmaps = pixmaps
        if not self._pixmaps:
            self.show_placeholder()
            return
        if self._current_index >= len(self._pixmaps):
            self._current_index = 0
        self._update_display()

    def _update_display(self):
        if not self._pixmaps:
            return
        current_pixmap = self._pixmaps[self._current_index]
        w = int(current_pixmap.width() * self._zoom)
        h = int(current_pixmap.height() * self._zoom)
        scaled = current_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self._sprite_label.setPixmap(scaled)
        self._sprite_label.setFixedSize(scaled.size())
        self.zoom_changed.emit(self._zoom)
        self.frame_changed.emit(self._current_index + 1, len(self._pixmaps))
        self.pixmap_changed.emit(current_pixmap)

    def next_frame(self):
        if self._pixmaps and self._current_index < len(self._pixmaps) - 1:
            self._current_index += 1
            self._update_display()

    def prev_frame(self):
        if self._pixmaps and self._current_index > 0:
            self._current_index -= 1
            self._update_display()

    def zoom_in(self):
        self._set_zoom(min(self._zoom + ZOOM_STEP, ZOOM_MAX))

    def zoom_out(self):
        self._set_zoom(max(self._zoom - ZOOM_STEP, ZOOM_MIN))

    def zoom_reset(self):
        self._set_zoom(4.0)

    def _set_zoom(self, factor: float):
        self._zoom = round(factor, 4)
        self._update_display()

    def wheelEvent(self, event: QWheelEvent):
        if self._pixmaps and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

class SpriteStatusBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet(f'QWidget {{ background-color : {Theme.STATUS_BG}; border-top : 1px solid {Theme.PANEL_INNER_BDR}; border-bottom-left-radius : 8px; border-bottom-right-radius : 8px; }}')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        font = QFont('Segoe UI', 8)
        self._name_label = QLabel('—')
        self._zoom_label = QLabel('')
        for lbl in (self._name_label, self._zoom_label):
            lbl.setFont(font)
            lbl.setStyleSheet(f'color: {Theme.STATUS_VAL}; background: transparent; border: none;')
        layout.addWidget(self._name_label)
        layout.addStretch()
        layout.addWidget(self._zoom_label)

    def set_zoom(self, factor: float):
        self._zoom_label.setText(f'Zoom: {round(factor * 100)}%')

    def set_name(self, name: str):
        self._name_label.setText(name)

class SpriteRenderBox(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'QFrame {{ background-color : {Theme.PANEL_BG}; border : 1px solid {Theme.PANEL_OUTER_BDR}; border-radius : 14px; }}')
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        self._inner = QFrame(self)
        self._inner.setStyleSheet(f'QFrame {{ background-color : {Theme.CANVAS_BG}; border : 1px solid {Theme.PANEL_INNER_BDR}; border-radius : 10px; }}')
        outer_layout.addWidget(self._inner)
        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = self._build_toolbar()
        inner_layout.addWidget(toolbar)
        self.canvas = SpriteCanvas()
        inner_layout.addWidget(self.canvas, stretch=1)
        self.status_bar = SpriteStatusBar()
        inner_layout.addWidget(self.status_bar)
        self.canvas.zoom_changed.connect(self.status_bar.set_zoom)
        self.canvas.frame_changed.connect(self._update_frame_counter)
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        self.btn_zoom_reset.clicked.connect(self.canvas.zoom_reset)
        self.btn_prev_frame.clicked.connect(self.canvas.prev_frame)
        self.btn_next_frame.clicked.connect(self.canvas.next_frame)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f'QWidget {{ background-color : {Theme.STATUS_BG}; border-top-left-radius : 10px; border-top-right-radius : 10px; border-bottom : 1px solid {Theme.PANEL_INNER_BDR}; }}')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        self.btn_prev_frame = ZoomButton('◄')
        self.lbl_frame_counter = QLabel('0 / 0')
        self.lbl_frame_counter.setFont(QFont('Segoe UI', 9))
        self.lbl_frame_counter.setStyleSheet(f'color: {Theme.CANVAS_TXT}; font-weight: bold; background: transparent; border: none; padding: 0 5px;')
        self.btn_next_frame = ZoomButton('►')
        layout.addWidget(self.btn_prev_frame)
        layout.addWidget(self.lbl_frame_counter)
        layout.addWidget(self.btn_next_frame)
        layout.addStretch()
        self.btn_zoom_out = ZoomButton('−')
        self.btn_zoom_reset = ZoomButton('1:1')
        self.btn_zoom_in = ZoomButton('+')
        self.btn_zoom_reset.setFixedWidth(36)
        layout.addWidget(self.btn_zoom_out)
        layout.addWidget(self.btn_zoom_reset)
        layout.addWidget(self.btn_zoom_in)
        hint = QLabel('Ctrl+Scroll to zoom')
        hint.setStyleSheet(f'color: {Theme.CANVAS_TXT}; background: transparent; border: none;')
        layout.addSpacing(10)
        layout.addWidget(hint)
        return bar

    def _update_frame_counter(self, current: int, total: int):
        self.lbl_frame_counter.setText(f'{current} / {total}')

class PaletteEditorBox(QFrame):
    color_updated = pyqtSignal(int, QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'QFrame {{ background-color : {Theme.PANEL_BG}; border : 1px solid {Theme.PANEL_OUTER_BDR}; border-radius : 14px; }}')
        self.colors = [QColor('#FF00FF')] * 16
        self.buttons = []
        self.selected_index = 0
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        self._inner = QFrame(self)
        self._inner.setStyleSheet(f'QFrame {{ background-color : {Theme.CANVAS_BG}; border : 1px solid {Theme.PANEL_INNER_BDR}; border-radius : 10px; }}')
        outer_layout.addWidget(self._inner)
        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(15, 15, 15, 15)
        inner_layout.setSpacing(15)
        lbl_title = QLabel('PALETTE EDITOR')
        lbl_title.setStyleSheet(f'color: {Theme.BTN_ACTIVE_TXT}; font-weight: bold; font-size: 13px; letter-spacing: 2px; border: none; background: transparent;')
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(lbl_title)
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        for i in range(16):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._select_color_index(idx))
            grid_layout.addWidget(btn, i // 4, i % 4)
            self.buttons.append(btn)
        inner_layout.addLayout(grid_layout)
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)
        hex_layout = QHBoxLayout()
        lbl_hex = QLabel('HEX:')
        lbl_hex.setStyleSheet(f'color: {Theme.STATUS_TXT}; font-weight: bold; border: none; background: transparent;')
        self.txt_hex = QLineEdit()
        self.txt_hex.setMaxLength(7)
        self.txt_hex.setStyleSheet(f'\n            QLineEdit {{\n                background-color: {Theme.STATUS_BG}; color: {Theme.STATUS_VAL};\n                border: 1px solid {Theme.PANEL_INNER_BDR}; border-radius: 4px; padding: 4px 8px;\n            }}\n        ')
        rx = QRegularExpression('^#[0-9A-Fa-f]{6}$')
        validator = QRegularExpressionValidator(rx, self)
        self.txt_hex.setValidator(validator)
        self.txt_hex.textEdited.connect(self._on_hex_typed)
        hex_layout.addWidget(lbl_hex)
        hex_layout.addWidget(self.txt_hex)
        controls_layout.addLayout(hex_layout)
        self.btn_pick_color = QPushButton('CHOOSE COLOR')
        self.btn_pick_color.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_color.setFixedHeight(32)
        self.btn_pick_color.setStyleSheet(f'\n            QPushButton {{ background-color : {Theme.BTN_ACTIVE_BG}; color : {Theme.BTN_ACTIVE_TXT}; border : 1px solid {Theme.BTN_ACTIVE_BDR}; border-radius : 6px; font-weight: bold; }}\n            QPushButton:hover {{ background-color : {Theme.BTN_HOVER_BG}; color : #FFFFFF; border-color : #4A6890; }}\n            QPushButton:pressed {{ background-color : {Theme.BTN_PRESS_BG}; }}\n        ')
        self.btn_pick_color.clicked.connect(self._open_color_picker)
        controls_layout.addWidget(self.btn_pick_color)
        inner_layout.addLayout(controls_layout)
        inner_layout.addStretch()
        self._update_button_colors()
        self._select_color_index(0)

    def load_palette(self, palette_data: list[tuple[int, int, int, int]]):
        for i in range(min(16, len(palette_data))):
            r, g, b, a = palette_data[i]
            self.colors[i] = QColor(r, g, b, a)
        self._update_button_colors()
        self._select_color_index(0)

    def _select_color_index(self, index: int):
        self.selected_index = index
        self._update_button_colors()
        self.txt_hex.setText(self.colors[index].name().upper())

    def _update_button_colors(self):
        for i, btn in enumerate(self.buttons):
            color = self.colors[i].name()
            border = '2px solid white' if i == self.selected_index else '1px solid #111'
            btn.setStyleSheet(f'\n                QPushButton {{ background-color: {color}; border: {border}; border-radius: 4px; }}\n                QPushButton:hover {{ border: 2px solid #8AAED4; }}\n            ')

    def _on_hex_typed(self, text: str):
        if len(text) == 7 and text.startswith('#'):
            new_color = QColor(text)
            if new_color.isValid():
                self.colors[self.selected_index] = new_color
                self._update_button_colors()
                self.color_updated.emit(self.selected_index, new_color)

    def _open_color_picker(self):
        current_color = self.colors[self.selected_index]
        new_color = QColorDialog.getColor(current_color, self, 'Select Color')
        if new_color.isValid():
            self.colors[self.selected_index] = new_color
            self._update_button_colors()
            self.txt_hex.setText(new_color.name().upper())
            self.color_updated.emit(self.selected_index, new_color)

class PlayerSpriteEditor(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pokémon Ranger: Shadows of Almia - Player Sprite Editor')
        self.setMinimumSize(QSize(1024, 768))
        self.resize(QSize(1280, 800))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(Theme.WIN_BG))
        self.setPalette(palette)
        self.setStyleSheet(f'QMainWindow {{ background-color: {Theme.WIN_BG}; }}')
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 6, 10, 10)
        root.setSpacing(10)
        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.top_toolbar = TopToolbar()
        right_layout.addWidget(self.top_toolbar)
        workspace_layout = QHBoxLayout()
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(6)
        self.render_box = SpriteRenderBox()
        workspace_layout.addWidget(self.render_box, stretch=6)
        self.palette_box = PaletteEditorBox()
        workspace_layout.addWidget(self.palette_box, stretch=4)
        right_layout.addLayout(workspace_layout)
        root.addWidget(right, stretch=1)
        self._current_renderer = None
        self.rom_extractor = RomExtractorHandler(self)
        self.rom_saver = RomSaverHandler(self)
        self.rom_extractor.extraction_complete.connect(self._on_rom_extracted)
        self.sidebar.sprite_list.itemClicked.connect(self._on_sprite_selected)
        self.palette_box.color_updated.connect(self._on_palette_color_updated)

    def _on_rom_extracted(self, folders, player_root_path):
        list_widget = self.sidebar.sprite_list
        list_widget.clear()
        for folder in folders:
            item = QListWidgetItem(folder.name.upper())
            item.setData(Qt.ItemDataRole.UserRole, folder)
            list_widget.addItem(item)
        print(f'[GUI] Populated sprite list with {len(folders)} items.')

    def _on_sprite_selected(self, item: QListWidgetItem):
        folder_path = item.data(Qt.ItemDataRole.UserRole)
        if not folder_path:
            return
        self.render_box.status_bar.set_name(folder_path.name.upper())
        self._current_renderer = CharacterRenderer(folder_path)
        pixmaps = self._current_renderer.load_character_frames()
        self.render_box.canvas.show_sprites(pixmaps)
        if self._current_renderer.palette:
            self.palette_box.load_palette(self._current_renderer.palette)

    def _on_palette_color_updated(self, index: int, color: QColor):
        if not self._current_renderer:
            return
        self._current_renderer.update_color(index, color.red(), color.green(), color.blue(), color.alpha())
        pixmaps = self._current_renderer.load_character_frames()
        self.render_box.canvas.update_sprites(pixmaps)
