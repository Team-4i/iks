from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from .models import PDFDocument, Topic, Chapter, ContentPoint, GameContentMapping
from .forms import PDFUploadForm
import fitz  # PyMuPDF
from PIL import Image
import io
from django.core.files import File
import os
from django.contrib import messages
import gc
from .services import TextbookAnalyzer
from django.utils import timezone
import threading
import PyPDF2

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
                pdf_doc = PDFDocument(
                    title=form.cleaned_data['title'],
                    is_textbook=form.cleaned_data.get('is_textbook', False),
                    author=form.cleaned_data.get('author', '')
                )
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

                # If this is a textbook, start processing it in background
                if pdf_doc.is_textbook:
                    pdf_doc.processing_status = 'PENDING'
                    pdf_doc.save()
                    # Start background processing
                    thread = threading.Thread(target=process_textbook_in_background, args=(pdf_doc.id,))
                    thread.daemon = True
                    thread.start()
                    messages.success(request, f"Textbook uploaded successfully! Processing has started.")
                    return redirect('dynamicDB:textbook_status', pk=pdf_doc.pk)
                else:
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
        messages.error(request, f"Error during analysis: {str(e)}")
    
    return redirect('dynamicDB:view_pdf', pk=pdf_doc.pk)

def visualize_topics(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    topics = pdf_doc.topics.all()
    
    return render(request, 'dynamicDB/visualize.html', {
        'pdf_doc': pdf_doc,
        'topics': topics
    })

def process_textbook_in_background(pdf_id):
    """Process a textbook in the background"""
    try:
        pdf_doc = PDFDocument.objects.get(id=pdf_id)
        pdf_doc.processing_status = 'PROCESSING'
        pdf_doc.save()
        
        # Initialize analyzer
        analyzer = TextbookAnalyzer()
        
        # Extract chapters and topics
        result = analyzer.analyze_textbook_structure(pdf_doc.pdf_file.path)
        chapters_data = result['chapters']
        topics_data = result['topics']
        
        # Dictionary to track created chapters for later reference
        created_chapters = {}
        
        # Create chapters
        for chapter_data in chapters_data:
            # Create the chapter
            chapter = Chapter.objects.create(
                pdf_document=pdf_doc,
                title=chapter_data['title'],
                number=chapter_data['number'],
                start_page=chapter_data['start_page'],
                end_page=chapter_data['end_page'],
                confidence_score=0.9
            )
            
            # Track in our dictionary using chapter number as key
            created_chapters[chapter.number] = chapter
            
            # Extract text for this chapter
            chapter_text = ""
            try:
                with open(pdf_doc.pdf_file.path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page_num in range(chapter_data['start_page']-1, min(chapter_data['end_page'], len(reader.pages))):
                        page = reader.pages[page_num]
                        chapter_text += page.extract_text() + "\n\n"
            except Exception as e:
                print(f"Error extracting chapter text: {e}")
                chapter_text = f"Error extracting text: {str(e)}"
            
            # Save chapter content
            chapter.content = chapter_text
            chapter.save()
            
        # Now create topics with their associated chapters
        for topic_data in topics_data:
            # Create the topic first (not linked to a specific chapter since it may span multiple)
            topic = Topic.objects.create(
                pdf_document=pdf_doc,
                title=topic_data['title'],
                content=topic_data.get('summary', ''),
                start_page=1,  # Default value, will be updated
                end_page=1,    # Default value, will be updated
                confidence_score=0.85
            )
            
            # Get all the chapters associated with this topic
            chapter_numbers = topic_data.get('chapters', [])
            if chapter_numbers:
                # Find the actual chapters that belong to this topic
                topic_chapters = []
                for chapter_num in chapter_numbers:
                    if chapter_num in created_chapters:
                        topic_chapters.append(created_chapters[chapter_num])
                
                if topic_chapters:
                    # Update the topic's page range based on its chapters
                    topic.start_page = min(ch.start_page for ch in topic_chapters)
                    topic.end_page = max(ch.end_page for ch in topic_chapters)
                    
                    # Set the primary chapter (first one) for this topic
                    topic.chapter = topic_chapters[0]
                    
                    # Create content points from the associated chapters
                    all_chapter_content = ""
                    for chapter in topic_chapters:
                        all_chapter_content += chapter.content + "\n\n"
                    
                    # Extract key points from combined content
                    if all_chapter_content:
                        # Split into smaller chunks if too large
                        if len(all_chapter_content) > 5000:
                            all_chapter_content = all_chapter_content[:5000]
                            
                        points_data = analyzer.extract_key_points(all_chapter_content)
                        
                        # Create content points
                        for point_data in points_data:
                            content_point = ContentPoint.objects.create(
                                topic=topic,
                                text=point_data['text'],
                                is_key_point=point_data.get('is_key_point', False)
                            )
                            
                            # Create simplified version
                            simplified = analyzer.simplify_text(point_data['text'])
                            content_point.simplified_text = simplified
                            content_point.save()
                            
                            # Create game mappings
                            for game_type in ['SNAKE_LADDER', 'HOUSIE', 'SPINWHEEL', 'FLIPCARD']:
                                GameContentMapping.objects.create(
                                    content_point=content_point,
                                    game_type=game_type,
                                    difficulty=1,  # Default difficulty
                                    active=True
                                )
            
            # Save the topic with updated info
            topic.save()
        
        # Update processing status
        pdf_doc.processing_status = 'COMPLETED'
        pdf_doc.processed_at = timezone.now()
        pdf_doc.save()
        
    except Exception as e:
        # Update processing status to failed
        try:
            pdf_doc = PDFDocument.objects.get(id=pdf_id)
            pdf_doc.processing_status = 'FAILED'
            pdf_doc.processing_message = str(e)
            pdf_doc.save()
        except:
            pass
        print(f"Error processing textbook {pdf_id}: {e}")

def textbook_status(request, pk):
    """View to check textbook processing status"""
    pdf_doc = get_object_or_404(PDFDocument, pk=pk)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If AJAX request, return JSON response
        return JsonResponse({
            'status': pdf_doc.processing_status,
            'message': pdf_doc.processing_message,
            'processed_at': pdf_doc.processed_at.isoformat() if pdf_doc.processed_at else None,
            'chapter_count': pdf_doc.chapters.count(),
            'topic_count': pdf_doc.topics.count()
        })
    
    # Render full page for non-AJAX requests
    return render(request, 'dynamicDB/textbook_status.html', {
        'pdf_doc': pdf_doc
    })

def view_textbook(request, pk):
    """View textbook structure and content - grouped by topics"""
    pdf_doc = get_object_or_404(PDFDocument, pk=pk)
    
    # Get all chapters and topics
    chapters = list(pdf_doc.chapters.all())
    topics = list(pdf_doc.topics.all())
    
    # Structure for the template - topics with their chapters
    topic_structure = []
    
    for topic in topics:
        # Find chapters related to this topic
        topic_chapters = []
        
        # Direct relationship - topic.chapter is the primary chapter
        if topic.chapter:
            topic_chapters.append(topic.chapter)
            
        # Find any chapters with topics that match this topic's id
        for chapter in chapters:
            if chapter != topic.chapter and chapter.topics.filter(id=topic.id).exists():
                topic_chapters.append(chapter)
                
        # Sort chapters by number
        topic_chapters.sort(key=lambda ch: ch.number)
        
        topic_structure.append({
            'topic': topic,
            'chapters': topic_chapters
        })
    
    return render(request, 'dynamicDB/view_textbook.html', {
        'pdf_doc': pdf_doc,
        'topic_structure': topic_structure
    })

def chapter_detail(request, pk):
    """View details of a specific chapter"""
    chapter = get_object_or_404(Chapter, pk=pk)
    topics = chapter.topics.all().prefetch_related('content_points')
    
    return render(request, 'dynamicDB/chapter_detail.html', {
        'chapter': chapter,
        'topics': topics
    })

def topic_detail(request, pk):
    """View details of a specific topic"""
    topic = get_object_or_404(Topic, pk=pk)
    content_points = topic.content_points.all()
    
    # Count key points
    key_points_count = sum(1 for point in content_points if point.is_key_point)
    
    return render(request, 'dynamicDB/topic_detail.html', {
        'topic': topic,
        'content_points': content_points,
        'key_points_count': key_points_count
    })

def content_for_game(request, game_type):
    """API endpoint to get content for a specific game"""
    if game_type not in [choice[0] for choice in GameContentMapping.GAME_CHOICES]:
        return JsonResponse({'error': 'Invalid game type'}, status=400)
    
    mappings = GameContentMapping.objects.filter(
        game_type=game_type,
        active=True
    ).select_related(
        'content_point', 
        'content_point__topic', 
        'content_point__topic__chapter',
        'content_point__topic__pdf_document'
    )
    
    content = []
    for mapping in mappings:
        point = mapping.content_point
        topic = point.topic
        
        content_item = {
            'id': point.id,
            'text': point.text,
            'simplified_text': point.simplified_text or point.text,
            'is_key_point': point.is_key_point,
            'topic': topic.title,
            'difficulty': mapping.difficulty
        }
        
        if topic.chapter:
            content_item.update({
                'chapter_title': topic.chapter.title,
                'chapter_number': topic.chapter.number,
                'textbook_title': topic.chapter.pdf_document.title
            })
        
        content.append(content_item)
    
    return JsonResponse({
        'content': content
    })
