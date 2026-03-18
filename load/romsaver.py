import struct
import shutil
import math
import traceback
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from load.romextractor import decompress_lz10, parse_narc
CRC16_TABLE = [0, 49345, 49537, 320, 49921, 960, 640, 49729, 50689, 1728, 1920, 51009, 1280, 50625, 50305, 1088, 52225, 3264, 3456, 52545, 3840, 53185, 52865, 3648, 2560, 51905, 52097, 2880, 51457, 2496, 2176, 51265, 55297, 6336, 6528, 55617, 6912, 56257, 55937, 6720, 7680, 57025, 57217, 8000, 56577, 7616, 7296, 56385, 5120, 54465, 54657, 5440, 55041, 6080, 5760, 54849, 53761, 4800, 4992, 54081, 4352, 53697, 53377, 4160, 61441, 12480, 12672, 61761, 13056, 62401, 62081, 12864, 13824, 63169, 63361, 14144, 62721, 13760, 13440, 62529, 15360, 64705, 64897, 15680, 65281, 16320, 16000, 65089, 64001, 15040, 15232, 64321, 14592, 63937, 63617, 14400, 10240, 59585, 59777, 10560, 60161, 11200, 10880, 59969, 60929, 11968, 12160, 61249, 11520, 60865, 60545, 11328, 58369, 9408, 9600, 58689, 9984, 59329, 59009, 9792, 8704, 58049, 58241, 9024, 57601, 8640, 8320, 57409, 40961, 24768, 24960, 41281, 25344, 41921, 41601, 25152, 26112, 42689, 42881, 26432, 42241, 26048, 25728, 42049, 27648, 44225, 44417, 27968, 44801, 28608, 28288, 44609, 43521, 27328, 27520, 43841, 26880, 43457, 43137, 26688, 30720, 47297, 47489, 31040, 47873, 31680, 31360, 47681, 48641, 32448, 32640, 48961, 32000, 48577, 48257, 31808, 46081, 29888, 30080, 46401, 30464, 47041, 46721, 30272, 29184, 45761, 45953, 29504, 45313, 29120, 28800, 45121, 20480, 37057, 37249, 20800, 37633, 21440, 21120, 37441, 38401, 22208, 22400, 38721, 21760, 38337, 38017, 21568, 39937, 23744, 23936, 40257, 24320, 40897, 40577, 24128, 23040, 39617, 39809, 23360, 39169, 22976, 22656, 38977, 34817, 18624, 18816, 35137, 19200, 35777, 35457, 19008, 19968, 36545, 36737, 20288, 36097, 19904, 19584, 35905, 17408, 33985, 34177, 17728, 34561, 18368, 18048, 34369, 33281, 17088, 17280, 33601, 16640, 33217, 32897, 16448]

def calculate_crc16(data: bytes) -> int:
    crc = 65535
    for byte in data:
        crc = crc >> 8 & 255 ^ CRC16_TABLE[(crc ^ byte) & 255]
    return crc & 65535

def align4(value: int) -> int:
    return value + 3 & ~3

@dataclass
class NDSHeader:
    raw_data: bytearray = field(default_factory=lambda: bytearray(512))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NDSHeader':
        return cls(bytearray(data[:512]))

    def to_bytes(self) -> bytes:
        return bytes(self.raw_data)

    @property
    def filename_table_addr(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 64)[0]

    @property
    def filename_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 68)[0]

    @property
    def fat_addr(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 72)[0]

    @property
    def fat_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 76)[0]

    @property
    def rom_size(self) -> int:
        return struct.unpack_from('<I', self.raw_data, 128)[0]

    @rom_size.setter
    def rom_size(self, value: int):
        struct.pack_into('<I', self.raw_data, 128, value)

    def set_capacity(self, value: int):
        struct.pack_into('B', self.raw_data, 20, value)

    def update_crc(self):
        crc = calculate_crc16(self.raw_data[:350])
        struct.pack_into('<H', self.raw_data, 350, crc)

@dataclass
class FATEntry:
    start_addr: int
    end_addr: int

    @property
    def size(self) -> int:
        return self.end_addr - self.start_addr

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FATEntry':
        start, end = struct.unpack('<II', data[0:8])
        return cls(start, end)

    def to_bytes(self) -> bytes:
        return struct.pack('<II', self.start_addr, self.end_addr)

class FNTParser:

    def parse(self, rom_data: bytes, fnt_offset: int, fnt_size: int) -> Dict[str, int]:
        index: Dict[str, int] = {}
        self._walk_dir(rom_data, fnt_offset, fnt_size, dir_id=61440, parent_path='', index=index)
        return index

    def _walk_dir(self, rom: bytes, fnt_base: int, fnt_size: int, dir_id: int, parent_path: str, index: Dict[str, int]):
        dir_num = dir_id & 4095
        dir_entry_offset = fnt_base + dir_num * 8
        if dir_entry_offset + 8 > len(rom):
            return
        entries_rel = struct.unpack_from('<I', rom, dir_entry_offset)[0]
        first_idx = struct.unpack_from('<H', rom, dir_entry_offset + 4)[0]
        pos = fnt_base + entries_rel
        current_file_idx = first_idx
        fnt_end = fnt_base + fnt_size
        while pos < fnt_end and pos < len(rom):
            type_len = rom[pos]
            pos += 1
            if type_len == 0:
                break
            is_subdir = bool(type_len & 128)
            name_len = type_len & 127
            if pos + name_len > len(rom):
                break
            name = rom[pos:pos + name_len].decode('ascii', errors='replace')
            pos += name_len
            full_path = (f'{parent_path}/{name}' if parent_path else name).lower()
            if is_subdir:
                if pos + 2 > len(rom):
                    break
                sub_dir_id = struct.unpack_from('<H', rom, pos)[0]
                pos += 2
                self._walk_dir(rom, fnt_base, fnt_size, sub_dir_id, full_path, index)
            else:
                index[full_path] = current_file_idx
                current_file_idx += 1

class ArchiveBuilder:

    @staticmethod
    def pack_narc(files: List[bytes], original_narc: bytes) -> bytes:
        btaf_off = 16
        btaf_size = struct.unpack_from('<I', original_narc, btaf_off + 4)[0]
        btnf_off = btaf_off + btaf_size
        btnf_size = struct.unpack_from('<I', original_narc, btnf_off + 4)[0]
        fntb_bytes = original_narc[btnf_off:btnf_off + btnf_size]
        header_size = 16
        fatb_size = 12 + len(files) * 8
        fimg_size = 8 + sum((len(f) for f in files))
        total_size = header_size + fatb_size + len(fntb_bytes) + fimg_size
        out = bytearray()
        out.extend(b'NARC')
        out.extend(b'\xfe\xff\x00\x01')
        out.extend(struct.pack('<I', total_size))
        out.extend(struct.pack('<H', header_size))
        out.extend(struct.pack('<H', 3))
        out.extend(b'BTAF')
        out.extend(struct.pack('<I', fatb_size))
        out.extend(struct.pack('<I', len(files)))
        current_offset = 0
        for f in files:
            start = current_offset
            end = current_offset + len(f)
            out.extend(struct.pack('<II', start, end))
            current_offset = end
        out.extend(fntb_bytes)
        out.extend(b'GMIF')
        out.extend(struct.pack('<I', fimg_size))
        for f in files:
            out.extend(f)
        return bytes(out)

    @staticmethod
    def compress_lz10(data: bytes) -> bytes:
        n = len(data)
        out = bytearray([16, n & 255, n >> 8 & 255, n >> 16 & 255])
        if n == 0:
            return bytes(out)
        pos = 0
        while pos < n:
            flags_pos = len(out)
            out.append(0)
            flags = 0
            for bit in range(8):
                if pos >= n:
                    break
                window_start = max(0, pos - 4096)
                best_len = 0
                best_dist = 0
                max_possible_match = min(18, n - pos)
                if max_possible_match >= 3:
                    for l in range(max_possible_match, 2, -1):
                        idx = data.rfind(data[pos:pos + l], window_start, pos)
                        if idx != -1:
                            best_len = l
                            best_dist = pos - idx - 1
                            break
                if best_len >= 3:
                    flags |= 1 << 7 - bit
                    out.append(best_len - 3 << 4 | best_dist >> 8)
                    out.append(best_dist & 255)
                    pos += best_len
                else:
                    out.append(data[pos])
                    pos += 1
            out[flags_pos] = flags
        while len(out) % 4 != 0:
            out.append(255)
        return bytes(out)

class SaveWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, original_rom: Path, output_rom: Path, archive_name: str, modified_nclr: Path):
        super().__init__()
        self.original_rom = original_rom
        self.output_rom = output_rom
        self.archive_name = archive_name.lower()
        self.modified_nclr = modified_nclr

    def _load_fat(self, rom_data: bytes, header: NDSHeader) -> List[FATEntry]:
        fat_raw = rom_data[header.fat_addr:header.fat_addr + header.fat_size]
        entries = []
        for i in range(0, len(fat_raw), 8):
            if i + 8 <= len(fat_raw):
                entries.append(FATEntry.from_bytes(fat_raw[i:i + 8]))
        return entries

    def run(self):
        try:
            self.progress.emit('Reading original ROM...')
            with open(self.original_rom, 'rb') as f:
                rom_data = f.read()
            header = NDSHeader.from_bytes(rom_data[:512])
            self.progress.emit('Parsing File Name Table...')
            parser = FNTParser()
            fat_index_map = parser.parse(rom_data, header.filename_table_addr, header.filename_size)
            fat_idx = -1
            for path, idx in fat_index_map.items():
                if f'data/player/{self.archive_name}' in path:
                    fat_idx = idx
                    break
            if fat_idx == -1:
                self.finished.emit(False, f'Could not find {self.archive_name} in ROM directories.')
                return
            self.progress.emit('Loading File Allocation Table...')
            fat_entries = self._load_fat(rom_data, header)
            target_entry = fat_entries[fat_idx]
            self.progress.emit('Extracting & Unpacking Archive...')
            original_archive = rom_data[target_entry.start_addr:target_entry.end_addr]
            is_compressed = original_archive.startswith(b'\x10')
            decompressed = decompress_lz10(original_archive)
            new_nclr_data = self.modified_nclr.read_bytes()
            inner_files = parse_narc(decompressed)
            patched = False
            for i, file_data in enumerate(inner_files):
                if file_data.startswith(b'RLCN') or file_data.startswith(b'NCLR'):
                    inner_files[i] = new_nclr_data
                    patched = True
                    break
            if not patched:
                self.finished.emit(False, 'Could not find Palette block inside the NARC archive.')
                return
            self.progress.emit('Rebuilding Standard NARC Archive...')
            repacked_narc = ArchiveBuilder.pack_narc(inner_files, decompressed)
            self.progress.emit('Compressing Archive (LZ10)...')
            final_archive = bytes(repacked_narc)
            if is_compressed:
                final_archive = ArchiveBuilder.compress_lz10(final_archive)
            self.progress.emit('Writing new ROM file...')
            try:
                if self.original_rom.resolve() != self.output_rom.resolve():
                    shutil.copy2(self.original_rom, self.output_rom)
            except shutil.SameFileError:
                pass
            with open(self.output_rom, 'r+b') as out_file:
                original_size = target_entry.size
                new_size = len(final_archive)
                out_file.seek(0, 2)
                current_end = out_file.tell()
                if new_size <= original_size:
                    self.progress.emit('Writing in-place to prevent ROM bloat...')
                    out_file.seek(target_entry.start_addr)
                    out_file.write(final_archive)
                    padding_size = original_size - new_size
                    if padding_size > 0:
                        out_file.write(b'\xff' * padding_size)
                    fat_entries[fat_idx] = FATEntry(target_entry.start_addr, target_entry.start_addr + new_size)
                    new_rom_size = current_end
                elif target_entry.end_addr >= current_end - 128:
                    self.progress.emit('Extending file at the end of ROM...')
                    out_file.seek(target_entry.start_addr)
                    out_file.write(final_archive)
                    new_rom_size = target_entry.start_addr + new_size
                    fat_entries[fat_idx] = FATEntry(target_entry.start_addr, new_rom_size)
                else:
                    self.progress.emit('Appending to new block at ROM end...')
                    aligned_end = align4(current_end)
                    if aligned_end > current_end:
                        out_file.write(b'\xff' * (aligned_end - current_end))
                    out_file.seek(aligned_end)
                    out_file.write(final_archive)
                    new_rom_size = aligned_end + new_size
                    fat_entries[fat_idx] = FATEntry(aligned_end, new_rom_size)
                self.progress.emit('Updating FAT table...')
                fat_raw = bytearray()
                for entry in fat_entries:
                    fat_raw.extend(entry.to_bytes())
                out_file.seek(header.fat_addr)
                out_file.write(fat_raw)
                self.progress.emit('Finalizing Header...')
                header.rom_size = new_rom_size
                capacity_byte = max(0, math.ceil(math.log2(new_rom_size)) - 17)
                header.set_capacity(capacity_byte)
                header.update_crc()
                out_file.seek(0)
                out_file.write(header.to_bytes())
            self.finished.emit(True, f'ROM saved successfully to:\n{self.output_rom.name}')
        except Exception as e:
            traceback.print_exc()
            self.finished.emit(False, f'Save failed: {e}')

class RomSaverHandler(QObject):

    def __init__(self, window):
        super().__init__(window)
        self._win = window
        self._worker = None
        self._win.top_toolbar.btn_save_rom.clicked.connect(self._on_save_clicked)

    def _on_save_clicked(self):
        if not hasattr(self._win, 'rom_extractor') or not self._win.rom_extractor.rom_path:
            QMessageBox.warning(self._win, 'Save ROM', 'No ROM is currently loaded.')
            return
        if not self._win._current_renderer or not self._win._current_renderer.nclr_path:
            QMessageBox.warning(self._win, 'Save ROM', 'No character palette is currently active. Change colors first.')
            return
        save_path, _ = QFileDialog.getSaveFileName(self._win, 'Save Modified ROM', '', 'NDS ROM (*.nds)')
        if not save_path:
            return
        archive_name = self._win._current_renderer.folder_path.name
        self._win.top_toolbar.btn_save_rom.setEnabled(False)
        self._worker = SaveWorker(Path(self._win.rom_extractor.rom_path), Path(save_path), archive_name, self._win._current_renderer.nclr_path)
        self._worker.progress.connect(lambda msg: self._win.top_toolbar.btn_save_rom.setText(msg[:15] + '...'))
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success, msg):
        self._win.top_toolbar.btn_save_rom.setEnabled(True)
        self._win.top_toolbar.btn_save_rom.setText('SAVE ROM')
        if success:
            QMessageBox.information(self._win, 'Success', msg)
        else:
            QMessageBox.critical(self._win, 'Error', msg)
