#!/usr/bin/env python3
"""
Generate stub BMP image files for the EPMS Server WiX installer.
Creates professional-colored placeholder images.
"""

import struct
from pathlib import Path

def create_bmp(width, height, r, g, b, filepath):
    """
    Create a BMP file with a solid color fill.
    BMP format: 24-bit uncompressed, 54-byte header + pixel data.
    """
    # Row size must be multiple of 4 bytes
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    # Pad row to 4-byte alignment with zeros
    padding = b'\x00' * (row_size - width * 3)

    with open(filepath, 'wb') as f:
        # BMP File Header (14 bytes)
        f.write(b'BM')                                                  # Signature
        f.write(struct.pack('<I', file_size))                           # File size
        f.write(struct.pack('<HH', 0, 0))                               # Reserved
        f.write(struct.pack('<I', 54))                                  # Data offset

        # DIB Header (40 bytes) - BITMAPINFOHEADER
        f.write(struct.pack('<I', 40))                                  # Header size
        f.write(struct.pack('<i', width))                               # Width
        f.write(struct.pack('<i', height))                              # Height (positive = bottom-up)
        f.write(struct.pack('<H', 1))                                   # Planes
        f.write(struct.pack('<H', 24))                                  # Bits per pixel
        f.write(struct.pack('<I', 0))                                   # Compression (none)
        f.write(struct.pack('<I', pixel_data_size))                     # Image size
        f.write(struct.pack('<i', 2835))                                # X pixels per meter (72 DPI)
        f.write(struct.pack('<i', 2835))                                # Y pixels per meter (72 DPI)
        f.write(struct.pack('<I', 0))                                   # Colors used
        f.write(struct.pack('<I', 0))                                   # Important colors

        # Pixel data — BMP with positive height is bottom-up.
        # The first row in the file corresponds to the bottom of the image.
        # For a solid-color image, iteration direction produces identical output.
        # For non-uniform content, use: for y in range(height - 1, -1, -1)
        for y in range(height):
            for x in range(width):
                # Write in BGR order
                f.write(bytes([b, g, r]))
            f.write(padding)

    print(f"  Created: {filepath} ({width}x{height}, #{r:02x}{g:02x}{b:02x})")


def main():
    resources_dir = Path(__file__).parent.parent / 'Resources'
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Banner: 500x60 - dark blue gradient (corporate feel)
    # Top section of the installer wizard
    create_bmp(500, 60, 0x2B, 0x57, 0x9A, resources_dir / 'banner.bmp')
    
    # Dialog: 500x370 - light gray background (clean, professional)
    # Main dialog background
    create_bmp(500, 370, 0xF0, 0xF0, 0xF0, resources_dir / 'dialog.bmp')

    print("\nDone! Stub BMP files created successfully.")


if __name__ == '__main__':
    main()
