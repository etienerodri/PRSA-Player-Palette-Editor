import struct
from pathlib import Path
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class CharacterRenderer:

    def __init__(self, folder_path: Path):
        self.folder_path = Path(folder_path)
        self.palette = []
        self.all_colors = []
        self.frames = []
        self.nclr_path = None
        self.color_start = 40

    def load_character_frames(self) -> list[QPixmap]:
        self.frames.clear()
        if not self.folder_path.exists() or not self.folder_path.is_dir():
            return []
        nclr_paths = [p for p in self.folder_path.iterdir() if p.is_file() and p.suffix.lower() == '.nclr']
        if not nclr_paths:
            print(f'[RENDER] No .NCLR file found in {self.folder_path.name}')
            return []
        self.nclr_path = nclr_paths[0]
        with open(self.nclr_path, 'rb') as f:
            self.palette = self._parse_nclr(f.read())
        ncbr_paths = [p for p in self.folder_path.iterdir() if p.is_file() and p.suffix.lower() == '.ncbr']
        ncbr_paths.sort()
        for ncbr_path in ncbr_paths:
            with open(ncbr_path, 'rb') as f:
                pixmap = self._parse_ncbr(f.read())
                if pixmap:
                    self.frames.append(pixmap)
        return self.frames

    def _parse_nclr(self, data: bytes) -> list[tuple[int, int, int, int]]:
        self.all_colors = []
        if len(data) < 16 or data[:4] != b'RLCN':
            print('[RENDER] Invalid RLCN/NCLR format.')
            return []
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
            return []
        data_size = struct.unpack_from('<I', data, ttlp_offset + 16)[0]
        data_offset = struct.unpack_from('<I', data, ttlp_offset + 20)[0]
        self.color_start = ttlp_offset + 8 + data_offset
        num_colors = data_size // 2
        for i in range(num_colors):
            bgr555 = struct.unpack('<H', data[self.color_start + i * 2:self.color_start + i * 2 + 2])[0]
            r5 = bgr555 & 31
            g5 = bgr555 >> 5 & 31
            b5 = bgr555 >> 10 & 31
            r = r5 << 3
            g = g5 << 3
            b = b5 << 3
            a = 0 if i == 0 else 255
            self.all_colors.append((r, g, b, a))
        self.palette = self.all_colors[:16]
        return self.palette

    def update_color(self, index: int, r: int, g: int, b: int, a: int=255):
        if 0 <= index < len(self.palette):
            if index == 0:
                a = 0
            self.palette[index] = (r, g, b, a)
            self.all_colors[index] = (r, g, b, a)
            self.save_palette()

    def save_palette(self):
        if not self.nclr_path or not self.nclr_path.exists():
            print('[RENDER] Cannot save palette: .NCLR file path is invalid.')
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
        logical_name = f'{self.folder_path.name}.NCLR'
        print(f'[RENDER] Successfully saved updated palette to {logical_name}')

    def _parse_ncbr(self, data: bytes) -> QPixmap:
        if len(data) < 48:
            return None
        height_tiles = struct.unpack_from('<H', data, 24)[0]
        width_tiles = struct.unpack_from('<H', data, 26)[0]
        mapping_flag = struct.unpack_from('<I', data, 36)[0]
        is_linear = mapping_flag == 1
        pixel_data = data[48:]
        width_px = width_tiles * 8
        height_px = height_tiles * 8
        total_tiles = width_tiles * height_tiles
        indices = []
        for byte in pixel_data:
            indices.append(byte & 15)
            indices.append(byte >> 4 & 15)
        img = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        if is_linear:
            for y in range(height_px):
                for x in range(width_px):
                    idx = y * width_px + x
                    if idx >= len(indices):
                        break
                    color_idx = indices[idx]
                    if 0 < color_idx < len(self.palette):
                        r, g, b, a = self.palette[color_idx]
                        argb = a << 24 | r << 16 | g << 8 | b
                        img.setPixel(x, y, argb)
        else:
            for tile_idx in range(total_tiles):
                grid_x = tile_idx % width_tiles * 8
                grid_y = tile_idx // width_tiles * 8
                for p in range(64):
                    px_x = p % 8
                    px_y = p // 8
                    idx = tile_idx * 64 + p
                    if idx >= len(indices):
                        break
                    color_idx = indices[idx]
                    if 0 < color_idx < len(self.palette):
                        r, g, b, a = self.palette[color_idx]
                        argb = a << 24 | r << 16 | g << 8 | b
                        img.setPixel(grid_x + px_x, grid_y + px_y, argb)
        return QPixmap.fromImage(img)
