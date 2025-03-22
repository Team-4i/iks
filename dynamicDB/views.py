from django.shortcuts import render, redirect
from django.conf import settings
from .models import PDFDocument, Topic
from .forms import PDFUploadForm
import fitz  # PyMuPDF
from PIL import Image
import io
from django.core.files import File
import os
from django.contrib import messages
import gc
from .services import TextbookAnalyzer

MAX_IMAGE_HEIGHT = 65000  # Slightly below PIL's limit of 65500

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_doc = None
            pdf_document = None
            temp_files = []
            try:
                # Save the model without the file first
                pdf_doc = PDFDocument(title=form.cleaned_data['title'])
                pdf_doc.save()

                # Now handle the file
                uploaded_file = request.FILES['pdf_file']
                temp_pdf_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'temp_{uploaded_file.name}')
                os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)

                # Save uploaded file to temp location
                with open(temp_pdf_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                # Process the PDF
                pdf_document = fitz.open(temp_pdf_path)
                
                # Calculate dimensions
                zoom = 1.2  # Reduced from 1.5 to allow for more pages
                mat = fitz.Matrix(zoom, zoom)
                
                # Get page dimensions
                pages_info = []
                max_width = 0
                total_height = 0
                
                for page in pdf_document:
                    rect = page.rect
                    width = int(rect.width * zoom)
                    height = int(rect.height * zoom)
                    max_width = max(max_width, width)
                    total_height += height
                    pages_info.append((width, height))

                # Calculate how many images we need
                num_images = (total_height + MAX_IMAGE_HEIGHT - 1) // MAX_IMAGE_HEIGHT

                # Process pages into multiple images if needed
                current_height = 0
                current_image = None
                y_offset = 0
                image_count = 0
                temp_image_paths = []

                for page_num, page in enumerate(pdf_document):
                    try:
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                        img = img.convert('RGB')
                        
                        # If we need to start a new image
                        if current_image is None:
                            remaining_height = min(MAX_IMAGE_HEIGHT, total_height - current_height)
                            current_image = Image.new('RGB', (max_width, remaining_height), 'white')
                            y_offset = 0

                        # If this page would exceed max height, save current image and start new one
                        if y_offset + img.height > MAX_IMAGE_HEIGHT:
                            # Save current image
                            temp_image_path = os.path.join(settings.MEDIA_ROOT, 'temp', 
                                                         f'temp_image_{pdf_doc.title}_{image_count}.jpg')
                            current_image.save(temp_image_path, format='JPEG', quality=85, optimize=True)
                            temp_image_paths.append(temp_image_path)
                            temp_files.append(temp_image_path)
                            
                            # Start new image
                            remaining_height = min(MAX_IMAGE_HEIGHT, total_height - current_height)
                            current_image = Image.new('RGB', (max_width, remaining_height), 'white')
                            y_offset = 0
                            image_count += 1

                        # Paste the page into current image
                        current_image.paste(img, (0, y_offset))
                        y_offset += img.height
                        current_height += img.height

                        del pix
                        del img
                        gc.collect()

                    except Exception as e:
                        print(f"Error processing page {page_num + 1}: {str(e)}")
                        continue

                # Save the last image if it exists
                if current_image:
                    temp_image_path = os.path.join(settings.MEDIA_ROOT, 'temp', 
                                                 f'temp_image_{pdf_doc.title}_{image_count}.jpg')
                    current_image.save(temp_image_path, format='JPEG', quality=85, optimize=True)
                    temp_image_paths.append(temp_image_path)
                    temp_files.append(temp_image_path)

                # Close and delete the temporary PDF
                pdf_document.close()
                del pdf_document
                gc.collect()

                # Save PDF file to model
                with open(temp_pdf_path, 'rb') as pdf_file:
                    pdf_doc.pdf_file.save(uploaded_file.name, File(pdf_file), save=False)

                # Save the first image as the main converted image
                if temp_image_paths:
                    with open(temp_image_paths[0], 'rb') as img_file:
                        pdf_doc.converted_image.save(f"{pdf_doc.title}_combined.jpg", File(img_file), save=True)

                # Clean up temporary files
                for temp_file in [temp_pdf_path] + temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

                return redirect('dynamicDB:view_pdf', pk=pdf_doc.pk)

            except Exception as e:
                # Clean up on error
                if pdf_document:
                    try:
                        pdf_document.close()
                    except:
                        pass
                
                if pdf_doc and pdf_doc.pk:
                    try:
                        pdf_doc.delete()
                    except:
                        pass

                # Clean up temp files
                for temp_file in [temp_pdf_path] + temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except:
                        pass

                messages.error(request, f"Error processing PDF: {str(e)}")
                return redirect('dynamicDB:upload_pdf')

            finally:
                # Final cleanup
                gc.collect()

    else:
        form = PDFUploadForm()
    
    return render(request, 'dynamicDB/upload.html', {'form': form})

def view_pdf(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    return render(request, 'dynamicDB/view.html', {'pdf_doc': pdf_doc})

def analyze_pdf(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    
    try:
        # Initialize analyzer
        analyzer = TextbookAnalyzer()
        
        # Get topics from QROG AI
        topics = analyzer.analyze_document(pdf_doc.converted_image.path)
        
        # Delete existing topics for this document
        pdf_doc.topics.all().delete()
        
        # Save new topics to database
        for topic_data in topics:
            Topic.objects.create(
                pdf_document=pdf_doc,
                title=topic_data['title'],
                content=topic_data['content'],
                start_page=1,  # Default value as QROG AI might not provide page numbers
                end_page=1,
                confidence_score=topic_data['confidence']
            )
        
        messages.success(request, "PDF analysis completed successfully!")
        
    except Exception as e:
        messages.error(request, f"Error analyzing PDF: {str(e)}")
    
    return redirect('dynamicDB:view_pdf', pk=pk)

def visualize_topics(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    topics = pdf_doc.topics.all()
    
    # Prepare data for D3.js
    topic_data = {
        "name": pdf_doc.title,
        "children": [
            {
                "name": topic.title,
                "value": topic.confidence_score,
                "content": topic.content
            } for topic in topics
        ]
    }
    
    return render(request, 'dynamicDB/visualize.html', {
        'pdf_doc': pdf_doc,
        'topic_data': topic_data
    })
