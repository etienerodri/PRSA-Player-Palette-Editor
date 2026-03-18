import struct
from pathlib import Path
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import QRect

class CharacterEditor:

    def __init__(self):
        self.nclr_path = None
        self.all_colors = []
        self.gui_colors = []
        self.color_start = 40

    def locate_nclr(self, target_dir: Path):
        if not target_dir.exists():
            return None
        potential = list(target_dir.glob('*.NCLR')) + list(target_dir.glob('*.nclr'))
        return potential[0] if potential else None

    def load_palette(self, folder_dir: Path) -> bool:
        self.nclr_path = self.locate_nclr(folder_dir)
        if not self.nclr_path:
            print(f'[EDITOR] No .NCLR file found in {folder_dir.name}')
            return False
        with open(self.nclr_path, 'rb') as f:
            data = f.read()
        if len(data) < 16 or data[:4] != b'RLCN':
            print('[EDITOR] Invalid RLCN/NCLR file format.')
            return False
        header_size = struct.unpack_from('<H', data, 12)[0]
        num_blocks = struct.unpack_from('<H', data, 14)[0]
        offset = header_size
        ttlp_offset = -1
        for _ in range(num_blocks):
            if offset + 8 > len(data):
                break
            magic = data[offset:offset + 4]
            block_size = struct.unpack_from('<I', data, offset + 4)[0]
            if magic == b'TTLP':
                ttlp_offset = offset
                break
            offset += block_size
        if ttlp_offset == -1:
            print('[EDITOR] No TTLP block found in NCLR.')
            return False
        data_size = struct.unpack_from('<I', data, ttlp_offset + 16)[0]
        data_offset = struct.unpack_from('<I', data, ttlp_offset + 20)[0]
        self.color_start = ttlp_offset + 8 + data_offset
        num_colors = data_size // 2
        self.all_colors = []
        for i in range(num_colors):
            bgr555 = struct.unpack('<H', data[self.color_start + i * 2:self.color_start + i * 2 + 2])[0]
            r5 = bgr555 & 31
            g5 = bgr555 >> 5 & 31
            b5 = bgr555 >> 10 & 31
            r8 = r5 << 3
            g8 = g5 << 3
            b8 = b5 << 3
            a = 0 if i == 0 else 255
            self.all_colors.append((r8, g8, b8, a))
        self.gui_colors = self.all_colors[:16]
        return True

    def get_hex_colors(self) -> list[str]:
        return [f'#{r:02X}{g:02X}{b:02X}' for r, g, b, a in self.gui_colors]

    def update_color(self, index: int, r: int, g: int, b: int, a: int=255):
        if 0 <= index < len(self.gui_colors):
            if index == 0:
                a = 0
            self.gui_colors[index] = (r, g, b, a)
            self.all_colors[index] = (r, g, b, a)
            self.save_palette()

    def save_palette(self):
        if not self.nclr_path or not self.nclr_path.exists():
            print('[EDITOR] Cannot save palette: .NCLR file path is invalid.')
            return
        color_bytes = bytearray()
        for r, g, b, a in self.all_colors:
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            r5 = r >> 3
            g5 = g >> 3
            b5 = b >> 3
            bgr555 = r5 | g5 << 5 | b5 << 10
            color_bytes.extend(struct.pack('<H', bgr555))
        with open(self.nclr_path, 'rb') as f:
            nclr_data = bytearray(f.read())
        end_idx = self.color_start + len(color_bytes)
        if end_idx <= len(nclr_data):
            nclr_data[self.color_start:end_idx] = color_bytes
        else:
            nclr_data[self.color_start:] = color_bytes[:len(nclr_data) - self.color_start]
        with open(self.nclr_path, 'wb') as f:
            f.write(nclr_data)
        print(f'[EDITOR] Successfully saved updated palette to {self.nclr_path.name}')

    def split_sprite(self, full_sprite_pixmap: QPixmap) -> dict:
        if full_sprite_pixmap.isNull():
            print('[CharacterEditor][ERROR] Input sprite QPixmap is null or invalid.')
            return {'head': None, 'torso': None, 'legs': None}
        full_width = full_sprite_pixmap.width()
        full_height = full_sprite_pixmap.height()
        print(f'[CharacterEditor] Loaded sprite: {full_width}x{full_height}px.')
        head_torso_y_split = -1
        torso_legs_y_split = -1
        img = full_sprite_pixmap.toImage()
        found_head_split = False
        found_torso_split = False
        for y in range(full_height):
            if not found_head_split:
                for x in range(full_width):
                    color = img.pixelColor(x, y)
                    if color.alpha() > 0 and self._is_red(color):
                        head_torso_y_split = y
                        found_head_split = True
                        break
            elif found_head_split and (not found_torso_split):
                yellow_count = 0
                for x in range(full_width):
                    color = img.pixelColor(x, y)
                    if color.alpha() > 0 and self._is_yellow(color):
                        yellow_count += 1
                if yellow_count >= 2:
                    torso_legs_y_split = y
                    found_torso_split = True
                    break
        if head_torso_y_split != -1 and torso_legs_y_split != -1 and (torso_legs_y_split > head_torso_y_split):
            print(f'[CharacterEditor] Color Scan Splits -> Head/Torso @ {head_torso_y_split}px, Torso/Legs @ {torso_legs_y_split}px.')
        else:
            FALLBACK_HEAD_RATIO = 0.35
            FALLBACK_TORSO_END_RATIO = 0.65
            head_torso_y_split = int(full_height * FALLBACK_HEAD_RATIO)
            torso_legs_y_split = int(full_height * FALLBACK_TORSO_END_RATIO)
            print(f'[CharacterEditor] Using Fallback Grid Splits -> Head/Torso @ {head_torso_y_split}px, Torso/Legs @ {torso_legs_y_split}px.')
        if head_torso_y_split >= full_height or torso_legs_y_split >= full_height or head_torso_y_split >= torso_legs_y_split:
            print('[CharacterEditor][ERROR] Invalid calculated split coordinates. Using fallbacks.')
            head_torso_y_split = int(full_height * 0.35)
            torso_legs_y_split = int(full_height * 0.65)
        head_pixmap = full_sprite_pixmap.copy(QRect(0, 0, full_width, head_torso_y_split))
        torso_height = torso_legs_y_split - head_torso_y_split
        torso_pixmap = full_sprite_pixmap.copy(QRect(0, head_torso_y_split, full_width, torso_height))
        legs_height = full_height - torso_legs_y_split
        legs_pixmap = full_sprite_pixmap.copy(QRect(0, torso_legs_y_split, full_width, legs_height))
        return {'head': head_pixmap, 'torso': torso_pixmap, 'legs': legs_pixmap}

    def _is_red(self, color: QColor) -> bool:
        return color.red() > 150 and color.green() < 90 and (color.blue() < 90)

    def _is_yellow(self, color: QColor) -> bool:
        return color.red() > 150 and color.green() > 150 and (color.blue() < 90)
