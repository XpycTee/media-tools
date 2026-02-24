from flask import Blueprint, send_file, request, jsonify
from pypdf import PdfWriter, PdfReader
from PIL import Image
import io
import math
from datetime import datetime

pdf = Blueprint('pdf', __name__, url_prefix='/pdf')

@pdf.route("/merge", methods=["POST"])
def merge():
    try:
        # Get files (they come in the correct order already)
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        # Create PDF writer
        pdf_writer = PdfWriter()
        
        # Process each file in order
        for file in files:
            file_bytes = file.read()
            
            try:
                # First try to read as PDF
                pdf_reader = PdfReader(io.BytesIO(file_bytes))
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            except:
                # If not a PDF, try to open as image and convert to PDF
                try:
                    img = Image.open(io.BytesIO(file_bytes))
                    
                    # Convert RGBA/LA/P to RGB
                    if img.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = rgb_img
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Convert image to PDF page
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PDF')
                    img_bytes.seek(0)
                    
                    # Add image as page to output PDF
                    img_pdf = PdfReader(img_bytes)
                    pdf_writer.add_page(img_pdf.pages[0])
                    
                except Exception as e:
                    print(f"Error processing file: {e}")
                    continue
        
        # Create output PDF
        output = io.BytesIO()
        pdf_writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'merged_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        
    except Exception as e:
        print(f"Merge error: {e}")
        return jsonify({'error': str(e)}), 500


def compress_file_pypdf(in_pdf, quality=75, resize=100) -> bytes:
    """Compress PDF by reducing image quality and resizing images."""
    from pypdf import PdfReader, PdfWriter
    
    start_size = in_pdf.getbuffer().nbytes
    resize = resize / 100

    reader = PdfReader(in_pdf)
    writer = PdfWriter()

    # Add all pages
    for page in reader.pages:
        writer.add_page(page)

    # Process images in each page
    for i, page in enumerate(writer.pages):
        try:
            for img_f in page.images:
                img = img_f.image

                width, height = img.size
                pixels = width * height
                if pixels > 512**2:
                    new_size = math.ceil(width * resize), math.ceil(height * resize)
                    new_img = img.resize(new_size)
                    img_f.replace(new_img, quality=quality, optimize=True)

            page.compress_content_streams()
        except Exception as e:
            print(f"Error processing page {i}: {e}")
            continue

    # Copy metadata
    if reader.metadata:
        writer.add_metadata(reader.metadata)

    # Write to bytes
    with io.BytesIO() as pdf_buf:
        writer.write(pdf_buf)
        compress_size = pdf_buf.getbuffer().nbytes
        data = pdf_buf.getvalue()

    compression_ratio = 1 - (compress_size / start_size) if start_size > 0 else 0
    print(f"[+] PDF Compression:")
    print(f"    - Original size: {start_size / 1024 / 1024:.2f} MB")
    print(f"    - Compressed size: {compress_size / 1024 / 1024:.2f} MB")
    print(f"    - Compression ratio: {compression_ratio:.1%}")

    return data


@pdf.route("/compress", methods=["POST"])
def compress():
    try:
        # Get PDF file and parameters
        if 'pdf_file' not in request.files:
            return jsonify({'error': 'No PDF file provided'}), 400
        
        pdf_file = request.files['pdf_file']
        quality = int(request.form.get('quality', 75))
        resize = int(request.form.get('resize', 100))
        
        # Validate parameters
        quality = max(1, min(100, quality))
        resize = max(10, min(100, resize))
        
        file_bytes = pdf_file.read()
        in_pdf = io.BytesIO(file_bytes)
        
        # Compress PDF
        compressed_data = compress_file_pypdf(in_pdf, quality=quality, resize=resize)
        
        output = io.BytesIO(compressed_data)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'compressed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        
    except Exception as e:
        print(f"Compress error: {e}")
        return jsonify({'error': str(e)}), 500

