import mmap
import shutil
import struct
import traceback
from pathlib import Path
from typing import List
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox
MAGIC_TO_EXT = {b'RLCN': '.NCLR', b'RGCN': '.NCBR', b'RECN': '.NCER', b'RNAN': '.NANR', b'RMAP': '.NSCR'}

def decompress_lz10(data: bytes) -> bytes:
    if not data or data[0] != 16:
        return data
    dst_size = data[1] | data[2] << 8 | data[3] << 16
    src_i = 4
    out = bytearray()
    while len(out) < dst_size and src_i < len(data):
        flags = data[src_i]
        src_i += 1
        for bit in range(8):
            if len(out) >= dst_size or src_i >= len(data):
                break
            if flags & 128 >> bit == 0:
                out.append(data[src_i])
                src_i += 1
            else:
                if src_i + 1 >= len(data):
                    break
                b1, b2 = (data[src_i], data[src_i + 1])
                src_i += 2
                disp = (b1 & 15) << 8 | b2
                length = (b1 >> 4) + 3
                copy_pos = len(out) - (disp + 1)
                for _ in range(length):
                    if copy_pos < 0 or copy_pos >= len(out):
                        break
                    out.append(out[copy_pos])
                    copy_pos += 1
    return bytes(out[:dst_size])

def parse_narc(blob: bytes) -> List[bytes]:
    if blob[:4] != b'NARC':
        raise ValueError('Not a valid NARC file')
    btaf_off = 16
    if blob[btaf_off:btaf_off + 4] != b'BTAF':
        raise ValueError('NARC is missing BTAF section')
    btaf_size = struct.unpack_from('<I', blob, btaf_off + 4)[0]
    file_count = struct.unpack_from('<I', blob, btaf_off + 8)[0]
    entries_off = btaf_off + 12
    entries = []
    for i in range(file_count):
        start = struct.unpack_from('<I', blob, entries_off + i * 8)[0]
        end = struct.unpack_from('<I', blob, entries_off + i * 8 + 4)[0]
        entries.append((start, end))
    btnf_off = btaf_off + btaf_size
    btnf_size = struct.unpack_from('<I', blob, btnf_off + 4)[0]
    gmif_off = btnf_off + btnf_size
    base = gmif_off + 8
    return [blob[base + s:base + e] for s, e in entries]

class NDSHeader:

    def __init__(self, data: bytes):
        self.game_title = data[0:12].decode('ascii', errors='ignore').strip('\x00')
        self.game_code = data[12:16].decode('ascii', errors='ignore').strip('\x00')
        self.filename_table_addr = struct.unpack_from('<I', data, 64)[0]
        self.filename_size = struct.unpack_from('<I', data, 68)[0]
        self.fat_addr = struct.unpack_from('<I', data, 72)[0]
        self.fat_size = struct.unpack_from('<I', data, 76)[0]

class FatRange:

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    @property
    def size(self):
        return self.end - self.start

class FileIndexEntry:

    def __init__(self, path: str, fat_index: int):
        self.path = path
        self.fat_index = fat_index

class ExtractionWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, rom_path: str, out_path: Path):
        super().__init__()
        self.rom_path = rom_path
        self.out_path = out_path
        self._cancelled = False
        self.player_folder = None
        self.extracted_files = []

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.progress.emit('Reading ROM header...')
            header = self._read_header()
            if not header:
                self.finished.emit(False, 'Invalid NDS ROM — could not read header.')
                return
            print(f'Title: {header.game_title}  Code: {header.game_code}')
            if self.out_path.exists():
                shutil.rmtree(self.out_path)
            self.out_path.mkdir(parents=True, exist_ok=True)
            self.player_folder = self.out_path / 'data' / 'player'
            with open(self.rom_path, 'rb') as fh:
                with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as rom:
                    self.progress.emit('Loading FAT...')
                    fat_entries = self._load_fat(rom, header)
                    self.progress.emit('Walking file name table...')
                    fnt = rom[header.filename_table_addr:header.filename_table_addr + header.filename_size]
                    index = self._build_index(fnt)
                    self.progress.emit('Filtering player sprite files...')
                    player_files = self._filter_player_files(index)
                    if not player_files:
                        self.finished.emit(False, 'No player files found — is this a Shadows of Almia ROM?')
                        return
                    self.progress.emit('Extracting & Decompressing...')
                    ok = self._extract_and_unpack(rom, fat_entries, player_files)
                    if not ok:
                        self.finished.emit(False, 'Cancelled.' if self._cancelled else 'Extraction failed.')
                        return
            msg = f'Done — Extracted {len(self.extracted_files)} Player Sprite Archives.'
            self.progress.emit(msg)
            self.finished.emit(True, msg)
        except Exception as e:
            traceback.print_exc()
            self.finished.emit(False, f'Unexpected error: {e}')

    def _read_header(self):
        try:
            with open(self.rom_path, 'rb') as f:
                data = f.read(512)
            return NDSHeader(data) if len(data) >= 512 else None
        except Exception:
            return None

    def _load_fat(self, rom, header: NDSHeader):
        raw = rom[header.fat_addr:header.fat_addr + header.fat_size]
        entries = []
        for i in range(0, len(raw) - 7, 8):
            s = struct.unpack_from('<I', raw, i)[0]
            e = struct.unpack_from('<I', raw, i + 4)[0]
            entries.append(FatRange(s, e))
        return entries

    def _build_index(self, fnt: bytes):
        index = []
        self._walk_dir(fnt, 61440, '', index)
        return index

    def _walk_dir(self, fnt: bytes, folder_id: int, cur_path: str, index: list):
        slot = folder_id & 4095
        offset = slot * 8
        if offset + 8 > len(fnt):
            return
        entry_offset = struct.unpack_from('<I', fnt, offset)[0]
        first_file_id = struct.unpack_from('<H', fnt, offset + 4)[0]
        current_file_idx = first_file_id
        pos = entry_offset
        while pos < len(fnt):
            ctrl = fnt[pos]
            if ctrl == 0:
                break
            pos += 1
            name_len = ctrl & 127
            is_dir = bool(ctrl & 128)
            if pos + name_len > len(fnt):
                break
            name = fnt[pos:pos + name_len].decode('utf-8', errors='replace')
            pos += name_len
            new_path = f'{cur_path}/{name}' if cur_path else name
            if is_dir:
                if pos + 2 > len(fnt):
                    break
                sub_id = struct.unpack_from('<H', fnt, pos)[0]
                pos += 2
                self._walk_dir(fnt, sub_id, new_path, index)
            else:
                index.append(FileIndexEntry(new_path, current_file_idx))
                current_file_idx += 1

    def _filter_player_files(self, index: list):
        out = []
        target_names = ['player1', 'player2', 'player3', 'player4']
        for e in index:
            p = e.path.lower()
            if 'data/player/' in p or 'data/player\\' in p:
                filename = Path(p).stem.lower()
                if any((filename.startswith(target) for target in target_names)):
                    out.append(e)
        return out

    def _extract_and_unpack(self, rom, fat_entries: list, player_files: list):
        try:
            self.player_folder.mkdir(parents=True, exist_ok=True)
            total = len(player_files)
            for i, entry in enumerate(player_files):
                if self._cancelled:
                    return False
                if entry.fat_index >= len(fat_entries):
                    continue
                fat = fat_entries[entry.fat_index]
                if fat.size <= 0:
                    continue
                raw_bytes = rom[fat.start:fat.end]
                filename = Path(entry.path).name
                self.progress.emit(f'Unpacking {filename} ({i + 1}/{total})...')
                dec_bytes = decompress_lz10(raw_bytes)
                narc_folder = self.player_folder / Path(filename).stem
                narc_folder.mkdir(exist_ok=True)
                try:
                    inner_files = parse_narc(dec_bytes)
                    for file_idx, file_data in enumerate(inner_files):
                        ext = '.bin'
                        if len(file_data) >= 4:
                            magic_header = file_data[:4]
                            if magic_header in MAGIC_TO_EXT:
                                ext = MAGIC_TO_EXT[magic_header]
                        inner_path = narc_folder / f'{file_idx:04d}{ext}'
                        inner_path.write_bytes(file_data)
                    self.extracted_files.append(narc_folder)
                except ValueError as e:
                    print(f'Skipping {filename}: {e}')
            return True
        except Exception:
            traceback.print_exc()
            return False

class RomExtractorHandler(QObject):
    extraction_complete = pyqtSignal(list, Path)

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._worker = None
        self.player_folder = None
        self.extracted_folders = []
        self.rom_path = None
        window.top_toolbar.btn_load_rom.clicked.connect(self._on_rom_clicked)

    def _on_rom_clicked(self):
        rom_path, _ = QFileDialog.getOpenFileName(self._window, 'Select Pokémon Ranger: Shadows of Almia ROM', '', 'NDS ROM (*.nds);;All files (*.*)')
        if not rom_path:
            return
        self.rom_path = rom_path
        out_path = Path(rom_path).parent / f'{Path(rom_path).stem}_extracted'
        self._window.top_toolbar.btn_load_rom.setEnabled(False)
        self._window.top_toolbar.btn_load_rom.setText('EXTRACTING...')
        self._worker = ExtractionWorker(rom_path, out_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, msg: str):
        print(f'[RomExtractor] {msg}')
        self._window.top_toolbar.btn_load_rom.setText(msg[:20] + '...' if len(msg) > 20 else msg)

    def _on_finished(self, success: bool, msg: str):
        self._window.top_toolbar.btn_load_rom.setEnabled(True)
        self._window.top_toolbar.btn_load_rom.setText('LOAD ROM')
        if not success:
            QMessageBox.critical(self._window, 'ROM Extraction Failed', msg)
            return
        self.player_folder = self._worker.player_folder
        self.extracted_folders = self._worker.extracted_files
        print(f'[RomExtractor] {msg}')
        self.extraction_complete.emit(self.extracted_folders, self.player_folder)
