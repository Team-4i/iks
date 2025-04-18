from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .models import PDFDocument, Chapter, Topic, MainTopic, ActivePDFSelection, ActiveTopicGroups, SubTopic
from .forms import PDFUploadForm, TopicExtractionForm
import fitz  # PyMuPDF
from PIL import Image
import io
from django.core.files import File
import os
from django.contrib import messages
import gc
from .services import TextbookAnalyzer
import json
import shutil  # For directory operations
import time  # For cache busting and delays
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
import uuid
import numpy as np
from collections import defaultdict
import re  # For regex pattern matching in Gemini response

# Try to import Google Generative AI library
try:
    import google.generativeai as genai
except ImportError:
    # If import fails, provide a message but continue without failing
    print("Google Generative AI library not found. Install with: pip install google-generativeai")
    genai = None

MAX_IMAGE_HEIGHT = 4000  # Further reduced to avoid any issues
MAX_PAGES_PER_IMAGE = 3  # Reduced for better processing of large PDFs

def index(request):
    documents = PDFDocument.objects.all().order_by('-upload_date')
    return render(request, 'dynamicDB/index.html', {'documents': documents})

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_doc = None
            pdf_document = None
            temp_files = []
            temp_dir = None
            try:
                # Save the model without the file first
                pdf_doc = PDFDocument(title=form.cleaned_data['title'])
                pdf_doc.save()

                # Create a temp directory specific to this upload
                temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', f'pdf_{pdf_doc.id}')
                os.makedirs(temp_dir, exist_ok=True)

                # Now handle the file
                uploaded_file = request.FILES['pdf_file']
                temp_pdf_path = os.path.join(temp_dir, f'temp_{uploaded_file.name}')

                # Save uploaded file to temp location
                with open(temp_pdf_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                # Process the PDF
                pdf_document = fitz.open(temp_pdf_path)
                
                # Calculate dimensions
                zoom = 1.2  # Adjusted zoom level
                mat = fitz.Matrix(zoom, zoom)
                
                # Get total number of pages
                total_pages = len(pdf_document)
                print(f"Total pages in PDF: {total_pages}")
                
                # Create a first image for preview and text extraction
                preview_image_path = os.path.join(temp_dir, f'preview_image.jpg')
                
                # Process for multi-page documents
                if total_pages > 1:
                    # Create a combined image of first few pages for preview
                    num_preview_pages = min(3, total_pages)  # Use up to 3 pages for preview
                    max_width = 0
                    total_height = 0
                    
                    # Get dimensions for the preview pages
                    preview_pages_info = []
                    for i in range(num_preview_pages):
                        page = pdf_document[i]
                        rect = page.rect
                        width = int(rect.width * zoom)
                        height = int(rect.height * zoom)
                        max_width = max(max_width, width)
                        total_height += height
                        preview_pages_info.append((width, height))
                    
                    # Create preview image
                    preview_image = Image.new('RGB', (max_width, total_height), 'white')
                    y_offset = 0
                    
                    for i in range(num_preview_pages):
                        page = pdf_document[i]
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                        img = img.convert('RGB')
                        
                        preview_image.paste(img, (0, y_offset))
                        y_offset += img.height
                        
                        del pix
                        del img
                        gc.collect()
                    
                    # Save preview image
                    preview_image.save(preview_image_path, format='JPEG', quality=85, optimize=True)
                    temp_files.append(preview_image_path)
                    
                    # Now process all pages and save them as separate images or small groups
                    page_images_dir = os.path.join(temp_dir, 'page_images')
                    os.makedirs(page_images_dir, exist_ok=True)
                    
                    print(f"Processing all {total_pages} pages into group images...")
                    
                    # Process pages in small groups
                    group_count = 0
                    
                    # Process pages in batches with explicit memory management
                    for start_page in range(0, total_pages, MAX_PAGES_PER_IMAGE):
                        current_group = []
                        current_height = 0
                        max_width = 0
                        
                        # Process a batch of pages
                        end_page = min(start_page + MAX_PAGES_PER_IMAGE, total_pages)
                        print(f"Processing pages {start_page+1} to {end_page} of {total_pages}")
                        
                        for page_num in range(start_page, end_page):
                            try:
                                page = pdf_document[page_num]
                                pix = page.get_pixmap(matrix=mat, alpha=False)
                                img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                                img = img.convert('RGB')
                                
                                current_group.append(img)
                                current_height += img.height
                                max_width = max(max_width, img.width)
                                
                                del pix
                                gc.collect()
                                
                            except Exception as e:
                                print(f"Error processing page {page_num + 1}: {str(e)}")
                                continue
                        
                        # Save this group if we have any pages
                        if current_group:
                            try:
                                # Use zero-padded group numbers for correct sorting (group_01.jpg, group_02.jpg, etc.)
                                group_count_str = f"{group_count:02d}"
                                print(f"Saving group {group_count_str} with {len(current_group)} pages...")
                                
                                # Create combined image
                                combined = Image.new('RGB', (max_width, current_height), 'white')
                                y = 0
                                
                                for group_img in current_group:
                                    combined.paste(group_img, (0, y))
                                    y += group_img.height
                                    del group_img  # Release memory
                                
                                # Save the group image with zero-padded numbering
                                group_path = os.path.join(page_images_dir, f'group_{group_count_str}.jpg')
                                combined.save(group_path, format='JPEG', quality=85, optimize=True)
                                
                                del combined
                                gc.collect()
                                
                                group_count += 1
                                
                                # Short delay to allow memory to be properly released
                                time.sleep(0.1)
                                
                            except Exception as e:
                                print(f"Error saving group {group_count}: {str(e)}")
                    
                    # Verify all images were created
                    image_files = [f for f in os.listdir(page_images_dir) if f.endswith('.jpg')]
                    print(f"Created {len(image_files)} group images from {total_pages} pages")
                    
                    if len(image_files) == 0:
                        raise Exception("Failed to create any page group images")
                
                # Single page document
                else:
                    page = pdf_document[0]
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                    img = img.convert('RGB')
                    
                    # Save as preview
                    img.save(preview_image_path, format='JPEG', quality=85, optimize=True)
                    temp_files.append(preview_image_path)
                    
                    del pix
                    del img
                    gc.collect()

                # Close the PDF document
                pdf_document.close()
                del pdf_document
                gc.collect()

                # Save PDF file to model
                with open(temp_pdf_path, 'rb') as pdf_file:
                    pdf_doc.pdf_file.save(uploaded_file.name, File(pdf_file), save=False)

                # Save the preview image as the main converted image
                with open(preview_image_path, 'rb') as img_file:
                    pdf_doc.converted_image.save(f"{pdf_doc.title}_preview.jpg", File(img_file), save=True)
                
                # Store the temp directory path in the session for later use
                request.session['pdf_temp_dir'] = temp_dir

                return redirect('dynamicDB:view_pdf', pk=pdf_doc.pk)

            except Exception as e:
                import traceback
                print(f"Error processing PDF: {str(e)}")
                print(traceback.format_exc())
                
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
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
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
    main_topics = pdf_doc.main_topics.all().prefetch_related('chapters')
    chapters = pdf_doc.chapters.all()
    topic_groups = pdf_doc.topic_groups.all().prefetch_related('topics', 'children')
    
    # Add debugging information about the query results
    print(f"PDF Document: {pdf_doc.title}")
    print(f"Main Topics Count: {main_topics.count()}")
    print(f"Chapters Count: {chapters.count()}")
    print(f"Topic Groups Count: {topic_groups.count()}")
    
    # Get relationship data if it exists
    topic_relationships = request.session.get('topic_relationships', {})
    
    # Structure topic groups hierarchically
    grouped_data = {}
    if topic_groups:
        # Group topics by their parent-child relationships
        root_groups = [g for g in topic_groups if g.parent is None]
        
        # Build the hierarchical structure
        for root in root_groups:
            children = [g for g in topic_groups if g.parent_id == root.id]
            grouped_data[root] = {
                'children': children,
                'topics': root.topics.all(),
                'level': 0
            }
            
            # Add second-level children
            for child in children:
                grandchildren = [g for g in topic_groups if g.parent_id == child.id]
                grouped_data[child] = {
                    'children': grandchildren,
                    'topics': child.topics.all(),
                    'parent': root,
                    'level': 1
                }
    
    # Check if we should show all pages
    show_all_pages = request.GET.get('show_all_pages') == 'true'
    page_images = []
    
    if show_all_pages:
        # Check if there are page groups for this document
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', f'pdf_{pdf_doc.id}')
        page_images_dir = os.path.join(temp_dir, 'page_images')
        
        if os.path.exists(page_images_dir):
            # Get all page group images and sort them properly by numeric value in the filename
            all_image_files = [f for f in os.listdir(page_images_dir) if f.endswith('.jpg')]
            
            # Custom sort function to extract and sort by the numeric part of "group_X.jpg"
            def get_group_number(filename):
                try:
                    # Extract number between "group_" and ".jpg"
                    return int(filename.split('_')[1].split('.')[0])
                except (IndexError, ValueError):
                    return 9999  # Default high value for files that don't match pattern
            
            # Sort images by group number
            image_files = sorted(all_image_files, key=get_group_number)
            
            print(f"Found {len(image_files)} image files in {page_images_dir}, sorted order:")
            for i, img_file in enumerate(image_files):
                print(f"  {i+1}. {img_file} (Group {get_group_number(img_file)})")
            
            # Ensure the directory is readable by the web server
            try:
                for img_file in image_files:
                    file_path = os.path.join(page_images_dir, img_file)
                    # Ensure file permissions are correct (readable by web server)
                    os.chmod(file_path, 0o644)
                    
                    # Check if image file is valid
                    try:
                        with open(file_path, 'rb') as f:
                            # Read and check file size
                            file_size = os.path.getsize(file_path)
                            print(f"Image {img_file} size: {file_size} bytes")
                            if file_size == 0:
                                print(f"WARNING: Zero-size file detected: {img_file}")
                    except Exception as e:
                        print(f"Error checking file {img_file}: {str(e)}")
            except Exception as e:
                print(f"Error setting permissions: {str(e)}")
            
            # Create URLs for each image file (using the MEDIA_URL)
            for img_file in image_files:
                # Create a relative path from MEDIA_ROOT to make Django serve the file
                rel_path = f'temp/pdf_{pdf_doc.id}/page_images/{img_file}'
                image_url = f'{settings.MEDIA_URL}{rel_path}'
                
                # Add cache-busting parameter to force reload
                cache_buster = int(time.time())
                image_url = f"{image_url}?v={cache_buster}"
                
                # Add group number as metadata
                group_num = get_group_number(img_file)
                page_images.append({
                    'url': image_url,
                    'group_num': group_num,
                    'filename': img_file
                })
                
            print(f"Found {len(page_images)} page group images with base path: {settings.MEDIA_URL}")
    
    # Log the topics and chapters for debugging
    for topic in main_topics:
        print(f"Topic: {topic.title} (ID: {topic.id})")
        topic_chapters = topic.chapters.all()
        print(f"  Associated Chapters: {topic_chapters.count()}")
        for chapter in topic_chapters:
            print(f"    - Chapter: {chapter.title}")
    
    # Check if there are any topics or chapters available
    analysis_status = 'not_analyzed'
    if chapters.exists():
        analysis_status = 'analyzed'
    
    # Create the topic extraction form
    topic_form = TopicExtractionForm()
    
    return render(request, 'dynamicDB/view.html', {
        'pdf_doc': pdf_doc,
        'main_topics': main_topics,
        'chapters': chapters,
        'analysis_status': analysis_status,
        'topic_form': topic_form,
        'show_all_pages': show_all_pages,
        'page_images': page_images,
        'topic_groups': topic_groups,
        'grouped_data': grouped_data,
        'topic_relationships': topic_relationships,
    })

def analyze_pdf(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    
    # Get topic count from form
    if request.method == 'POST':
        form = TopicExtractionForm(request.POST)
        if form.is_valid():
            topic_count = int(form.cleaned_data['topic_count'])
        else:
            topic_count = 3
    else:
        topic_count = int(request.GET.get('topic_count', 3))
    
    if topic_count < 2 or topic_count > 5:
        topic_count = 3
    
    # Check if we need to clean up temp data
    cleanup_temp = request.GET.get('cleanup') == 'true'
    if cleanup_temp:
        temp_dir = request.session.get('pdf_temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                del request.session['pdf_temp_dir']
                messages.success(request, "Temporary files have been cleaned up.")
            except Exception as e:
                print(f"Error cleaning up temp directory: {str(e)}")
        return redirect('dynamicDB:view_pdf', pk=pk)
    
    # Check if we need to perform topic grouping
    perform_grouping = request.GET.get('group_topics') == 'true'
    if perform_grouping:
        try:
            from .services import TopicGroupingService
            
            # Initialize the grouping service
            grouping_service = TopicGroupingService()
            
            # Perform topic grouping
            print("Starting topic grouping...")
            created_groups = grouping_service.group_topics(pdf_doc)
            
            if created_groups:
                # Analyze relationships between groups
                print("Analyzing topic relationships...")
                relationship_data = grouping_service.analyze_topic_relationships(pdf_doc)
                
                # Store relationship data in session for visualization
                if relationship_data:
                    request.session['topic_relationships'] = relationship_data
                
                messages.success(
                    request, 
                    f"Successfully grouped topics into {len(created_groups)} categories."
                )
            else:
                messages.warning(
                    request,
                    "No topic groups could be created. Please ensure topics have been extracted first."
                )
        except Exception as e:
            import traceback
            print(f"Error during topic grouping: {str(e)}")
            print(traceback.format_exc())
            messages.error(request, f"Error grouping topics: {str(e)}")
        
        return redirect('dynamicDB:view_pdf', pk=pk)
    
    try:
        # Print debug info
        print(f"Starting analysis for PDF: {pdf_doc.title} (ID: {pdf_doc.id})")
        
        # Get temp directory from session or create a default path
        temp_dir = request.session.get('pdf_temp_dir')
        if not temp_dir or not os.path.exists(temp_dir):
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', f'pdf_{pdf_doc.id}')
            if not os.path.exists(temp_dir):
                # If no temp directory exists, just use the converted image
                print(f"No temp directory found, using converted image: {pdf_doc.converted_image.path}")
                analyzer = TextbookAnalyzer()
                result = analyzer.process_document(pdf_doc)
                messages.success(
                    request, 
                    f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters."
                )
                return redirect('dynamicDB:view_pdf', pk=pk)
        
        # Check if there are page_images in the temp directory
        page_images_dir = os.path.join(temp_dir, 'page_images')
        if os.path.exists(page_images_dir):
            print(f"Found page images directory: {page_images_dir}")
            # Get all image files
            image_files = sorted([f for f in os.listdir(page_images_dir) if f.endswith('.jpg')])
            
            if image_files:
                print(f"Found {len(image_files)} image files for analysis")
                
                # Initialize analyzer
                analyzer = TextbookAnalyzer()
                
                # Show a progress message to the user
                messages.info(request, f"Processing {len(image_files)} page groups. This may take some time for large documents.")
                
                # Process each image group and combine results
                all_topics = []
                
                for i, img_file in enumerate(image_files):
                    img_path = os.path.join(page_images_dir, img_file)
                    print(f"Analyzing image {i+1}/{len(image_files)}: {img_path}")
                    
                    # Extract topics from this image
                    try:
                        topics = analyzer.extract_hierarchical_content(img_path)
                        if topics:
                            for topic in topics:
                                # Check if this topic already exists in our results (by title similarity)
                                topic_exists = False
                                for existing_topic in all_topics:
                                    # Simple string similarity check (can be improved)
                                    if existing_topic['title'].lower() == topic['title'].lower():
                                        # Merge chapters instead of duplicating the topic
                                        existing_topic['chapters'].extend(topic['chapters'])
                                        topic_exists = True
                                        break
                                
                                if not topic_exists:
                                    all_topics.append(topic)
                    except Exception as e:
                        print(f"Error analyzing image {img_file}: {str(e)}")
                
                # Now process the combined topics
                if all_topics:
                    # Adjust order numbers to be sequential
                    for i, topic in enumerate(all_topics):
                        topic['order'] = i + 1
                        
                        # Adjust chapter order to be sequential within each topic
                        for j, chapter in enumerate(topic['chapters']):
                            chapter['order'] = j + 1
                    
                    # Log the topics we found
                    print(f"Total topics extracted: {len(all_topics)}")
                    for topic in all_topics:
                        print(f"Topic: {topic['title']} - {len(topic['chapters'])} chapters")
                    
                    # Import models
                    from .models import Topic, Chapter
                    
                    # Delete existing chapters and topics
                    pdf_doc.chapters.all().delete()
                    pdf_doc.main_topics.all().delete()
                    
                    # Save combined topics to database
                    topics_count = 0
                    chapters_count = 0
                    
                    for topic_data in all_topics:
                        # Create Topic
                        main_topic = Topic.objects.create(
                            pdf_document=pdf_doc,
                            title=topic_data['title'],
                            summary=topic_data.get('summary', f"Main topic containing {len(topic_data['chapters'])} chapters"),
                            order=topic_data['order']
                        )
                        topics_count += 1
                        
                        # Create chapters for this topic
                        for chapter_idx, chapter_data in enumerate(topic_data['chapters']):
                            # For lecture-oriented content, we just use the title directly
                            chapter = Chapter.objects.create(
                                pdf_document=pdf_doc,
                                title=chapter_data['title'],
                                content=chapter_data.get('content', f"Subheading of {topic_data['title']}"),
                                start_page=chapter_data.get('start_page', 1),
                                end_page=chapter_data.get('end_page', 1),
                                confidence_score=chapter_data.get('confidence', 0.8),
                                order=chapter_idx + 1
                            )
                            chapters_count += 1
                            
                            # Add chapter to topic
                            main_topic.chapters.add(chapter)
                    
                    result = {
                        'topics_count': topics_count,
                        'chapters_count': chapters_count
                    }
                    
                    messages.success(
                        request, 
                        f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters. <a href='?group_topics=true'>Group Related Topics</a>"
                    )
                else:
                    # Fallback to single image analysis
                    print("No topics found in page images, using converted image")
                    result = analyzer.process_document(pdf_doc)
                    messages.success(
                        request, 
                        f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters. <a href='?group_topics=true'>Group Related Topics</a>"
                    )
            else:
                # No image files found, use the converted image
                print("No image files found, using converted image")
                analyzer = TextbookAnalyzer()
                result = analyzer.process_document(pdf_doc)
                messages.success(
                    request, 
                    f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters. <a href='?group_topics=true'>Group Related Topics</a>"
                )
        else:
            # No page_images directory, use the converted image
            print("No page_images directory found, using converted image")
            analyzer = TextbookAnalyzer()
            result = analyzer.process_document(pdf_doc)
            messages.success(
                request, 
                f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters. <a href='?group_topics=true'>Group Related Topics</a>"
            )
        
    except Exception as e:
        import traceback
        print(f"Error during analysis: {str(e)}")
        print(traceback.format_exc())
        messages.error(request, f"Error analyzing PDF: {str(e)}")
    
    # Keep temp directory for now - user might want to view all pages
    # We'll provide a separate button to clean up temp files
    
    return redirect('dynamicDB:view_pdf', pk=pk)

def visualize_topics(request, pk):
    pdf_doc = PDFDocument.objects.get(pk=pk)
    main_topics = pdf_doc.main_topics.all().prefetch_related('chapters')
    topic_groups = pdf_doc.topic_groups.all().prefetch_related('topics', 'children')
    
    # Prepare data for D3.js - hierarchical structure with main topics and chapters
    topic_data = {
        "name": pdf_doc.title,
        "children": []
    }
    
    for main_topic in main_topics:
        topic_node = {
            "name": main_topic.title,
            "summary": main_topic.summary,
            "children": []
        }
        
        for chapter in main_topic.chapters.all():
            topic_node["children"].append({
                "name": chapter.title,
                "value": chapter.confidence_score,
                "content": chapter.content
            })
        
        topic_data["children"].append(topic_node)
    
    # Prepare topic group data if available
    group_data = None
    if topic_groups.exists():
        group_data = []
        
        # First get top-level groups (no parent)
        root_groups = topic_groups.filter(parent__isnull=True)
        
        for group in root_groups:
            group_node = {
                "name": group.title,
                "description": group.description,
                "keywords": group.keywords,
                "similarity_score": group.similarity_score,
                "type": "group",
                "children": []
            }
            
            # Add topics that belong to this group
            for topic in group.topics.all():
                topic_node = {
                    "name": topic.title,
                    "summary": topic.summary,
                    "type": "topic",
                    "children": []
                }
                
                # Add chapters for this topic
                for chapter in topic.chapters.all():
                    topic_node["children"].append({
                        "name": chapter.title,
                        "value": chapter.confidence_score,
                        "content": chapter.content,
                        "type": "chapter"
                    })
                
                group_node["children"].append(topic_node)
            
            # Add child groups if any
            child_groups = topic_groups.filter(parent=group)
            if child_groups.exists():
                for child_group in child_groups:
                    child_node = {
                        "name": child_group.title,
                        "description": child_group.description,
                        "keywords": child_group.keywords,
                        "similarity_score": child_group.similarity_score,
                        "type": "subgroup",
                        "children": []
                    }
                    
                    # Add topics that belong to this child group
                    for topic in child_group.topics.all():
                        topic_node = {
                            "name": topic.title,
                            "summary": topic.summary,
                            "type": "topic",
                            "children": []
                        }
                        
                        # Add chapters for this topic
                        for chapter in topic.chapters.all():
                            topic_node["children"].append({
                                "name": chapter.title,
                                "value": chapter.confidence_score,
                                "content": chapter.content,
                                "type": "chapter"
                            })
                        
                        child_node["children"].append(topic_node)
                    
                    group_node["children"].append(child_node)
            
            group_data.append(group_node)
    
    # Use ensure_ascii=False to properly handle special characters
    topic_data_json = json.dumps(topic_data, ensure_ascii=False)
    group_data_json = json.dumps(group_data, ensure_ascii=False) if group_data else None
    
    return render(request, 'dynamicDB/visualize.html', {
        'pdf_doc': pdf_doc,
        'topic_data': topic_data_json,
        'group_data': group_data_json
    })

def visualize_data(request, document_id=None):
    if document_id:
        document = get_object_or_404(PDFDocument, id=document_id)
        topics = Topic.objects.filter(document=document)
        groups = MainTopic.objects.filter(document=document)
        
        # Prepare data for D3.js visualization
        topic_data = []
        for topic in topics:
            topic_item = {
                'id': str(topic.id),
                'name': topic.title,
                'document_id': str(topic.pdf_document.id),
                'children': []
            }
            
            for chapter in topic.chapters.all():
                chapter_item = {
                    'id': str(chapter.id),
                    'name': chapter.title,
                    'content': chapter.content[:100] + '...' if len(chapter.content) > 100 else chapter.content
                }
                topic_item['children'].append(chapter_item)
            
            topic_data.append(topic_item)
        
        # Prepare group data
        group_data = []
        for group in groups:
            group_item = {
                'id': str(group.id),
                'name': group.title,  # Changed from name to title to match the model field
                'document_id': str(group.pdf_document.id),
                'description': group.description,
                'keywords': group.keywords,
                'similarity_score': group.similarity_score,
                'children': []
            }
            
            # Add topics that belong to this group
            for topic in group.topics.all():
                topic_item = {
                    'id': str(topic.id),
                    'name': topic.title,
                    'summary': topic.summary,
                    'type': 'topic',
                    'group_id': str(group.id),
                    'children': []
                }
                
                for chapter in topic.chapters.all():
                    chapter_item = {
                        'id': str(chapter.id),
                        'name': chapter.title,
                        'content': chapter.content[:100] + '...' if len(chapter.content) > 100 else chapter.content,
                        'value': chapter.confidence_score,
                        'type': 'chapter'
                    }
                    topic_item['children'].append(chapter_item)
                
                group_item['children'].append(topic_item)
            
            group_data.append(group_item)
        
        return render(request, 'dynamicDB/visualize.html', {
            'pdf_doc': document,
            'topic_data': json.dumps(topic_data),
            'group_data': json.dumps(group_data),
        })
    else:
        # If no document_id is provided, show a list of documents to choose from
        documents = PDFDocument.objects.all().order_by('-upload_date')
        return render(request, 'dynamicDB/choose_document.html', {'documents': documents})

# Admin Panel Views
def admin_panel_dashboard(request):
    """Dashboard view showing statistics and recent items"""
    # Get counts
    pdf_count = PDFDocument.objects.count()
    topic_group_count = MainTopic.objects.count()
    main_topic_count = Topic.objects.count()
    chapter_count = Chapter.objects.count()
    
    # Get recent items
    recent_pdfs = PDFDocument.objects.all().order_by('-uploaded_at')[:5]
    recent_topic_groups = MainTopic.objects.all().order_by('-updated_at')[:5]
    recent_main_topics = Topic.objects.all().order_by('-pdf_document__uploaded_at')[:5]
    recent_chapters = Chapter.objects.all().order_by('-pdf_document__uploaded_at')[:5]
    
    # Get active PDF information
    active_pdf = None
    active_pdf_selection = None
    
    try:
        active_pdf_selection = ActivePDFSelection.objects.filter(is_active=True).first()
        if active_pdf_selection:
            active_pdf = active_pdf_selection.pdf
    except Exception as e:
        print(f"Error fetching active PDF for dashboard: {e}")
    
    context = {
        'active_page': 'dashboard',
        'pdf_count': pdf_count,
        'topic_group_count': topic_group_count,
        'main_topic_count': main_topic_count,
        'chapter_count': chapter_count,
        'recent_pdfs': recent_pdfs,
        'recent_topic_groups': recent_topic_groups,
        'recent_main_topics': recent_main_topics,
        'recent_chapters': recent_chapters,
        'active_pdf': active_pdf,
        'active_pdf_selection': active_pdf_selection
    }
    
    return render(request, 'dynamicDB/admin_panel_dashboard.html', context)

def admin_panel_pdfs(request):
    """List view of all PDF documents with search and filter options"""
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')
    
    # Base queryset
    pdfs = PDFDocument.objects.all()
    
    # Apply search filter if provided
    if search_query:
        pdfs = pdfs.filter(title__icontains=search_query)
    
    # Apply sorting
    if sort_by == 'title_asc':
        pdfs = pdfs.order_by('title')
    elif sort_by == 'title_desc':
        pdfs = pdfs.order_by('-title')
    else:  # Default to recent
        pdfs = pdfs.order_by('-uploaded_at')
    
    # Pagination
    paginator = Paginator(pdfs, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'pdfs',
        'pdfs': page_obj,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1
    }
    
    return render(request, 'dynamicDB/admin_panel_pdfs.html', context)

def admin_panel_pdf_detail(request, pk):
    """Detail view for a single PDF document with its topics and chapters"""
    pdf = get_object_or_404(PDFDocument, pk=pk)
    
    # Get related items
    topic_groups = pdf.topic_groups.order_by('order')
    main_topics = pdf.main_topics.order_by('order')
    chapters = pdf.chapters.order_by('order')
    
    context = {
        'active_page': 'pdfs',
        'pdf': pdf,
        'topic_groups': topic_groups,
        'main_topics': main_topics,
        'chapters': chapters
    }
    
    return render(request, 'dynamicDB/admin_panel_pdf_detail.html', context)

def admin_panel_topic_groups(request):
    """List view of all topic groups"""
    search_query = request.GET.get('search', '')
    pdf_filter = request.GET.get('pdf', '')
    sort_by = request.GET.get('sort', 'recent')
    
    # Base queryset
    topic_groups = MainTopic.objects.all()
    
    # Apply search filter if provided
    if search_query:
        topic_groups = topic_groups.filter(title__icontains=search_query)
    
    # Filter by PDF if provided
    if pdf_filter and pdf_filter.isdigit():
        topic_groups = topic_groups.filter(pdf_document_id=pdf_filter)
    
    # Apply sorting
    if sort_by == 'title_asc':
        topic_groups = topic_groups.order_by('title')
    elif sort_by == 'title_desc':
        topic_groups = topic_groups.order_by('-title')
    elif sort_by == 'pdf':
        topic_groups = topic_groups.order_by('pdf_document__title', 'order')
    else:  # Default to recent
        topic_groups = topic_groups.order_by('-updated_at')
    
    # Get all PDFs for filter dropdown
    pdfs = PDFDocument.objects.all().order_by('title')
    
    # Pagination
    paginator = Paginator(topic_groups, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'topic_groups',
        'topic_groups': page_obj,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'pdfs': pdfs
    }
    
    return render(request, 'dynamicDB/admin_panel_topic_groups.html', context)

def admin_panel_topic_group_detail(request, pk):
    """Detail view for a single topic group with its topics"""
    topic_group = get_object_or_404(MainTopic, pk=pk)
    
    # Get associated topics
    topics = topic_group.topics.order_by('order')
    
    # Get all available topics for this PDF for the add topic form
    available_topics = Topic.objects.filter(
        pdf_document=topic_group.pdf_document
    ).exclude(
        id__in=topics.values_list('id', flat=True)
    ).order_by('title')
    
    context = {
        'active_page': 'topic_groups',
        'topic_group': topic_group,
        'topics': topics,
        'available_topics': available_topics,
        'pdf': topic_group.pdf_document
    }
    
    return render(request, 'dynamicDB/admin_panel_topic_group_detail.html', context)

def admin_panel_main_topics(request):
    """List view of all main topics"""
    search_query = request.GET.get('search', '')
    pdf_filter = request.GET.get('pdf', '')
    sort_by = request.GET.get('sort', 'recent')
    
    # Base queryset
    main_topics = Topic.objects.all()
    
    # Apply search filter if provided
    if search_query:
        main_topics = main_topics.filter(title__icontains=search_query)
    
    # Filter by PDF if provided
    if pdf_filter and pdf_filter.isdigit():
        main_topics = main_topics.filter(pdf_document_id=pdf_filter)
    
    # Apply sorting
    if sort_by == 'title_asc':
        main_topics = main_topics.order_by('title')
    elif sort_by == 'title_desc':
        main_topics = main_topics.order_by('-title')
    elif sort_by == 'pdf':
        main_topics = main_topics.order_by('pdf_document__title', 'order')
    else:  # Default to order
        main_topics = main_topics.order_by('pdf_document__title', 'order')
    
    # Get all PDFs for filter dropdown
    pdfs = PDFDocument.objects.all().order_by('title')
    
    # Pagination
    paginator = Paginator(main_topics, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'main_topics',
        'main_topics': page_obj,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'pdfs': pdfs
    }
    
    return render(request, 'dynamicDB/admin_panel_main_topics.html', context)

def admin_panel_main_topic_detail(request, pk):
    """Detail view for a single main topic with its chapters"""
    main_topic = get_object_or_404(Topic, pk=pk)
    
    # Get associated chapters
    chapters = main_topic.chapters.order_by('order')
    
    # Get all available chapters for this PDF for the add chapter form
    available_chapters = Chapter.objects.filter(
        pdf_document=main_topic.pdf_document
    ).exclude(
        id__in=chapters.values_list('id', flat=True)
    ).order_by('title')
    
    context = {
        'active_page': 'main_topics',
        'main_topic': main_topic,
        'chapters': chapters,
        'available_chapters': available_chapters,
        'pdf': main_topic.pdf_document
    }
    
    return render(request, 'dynamicDB/admin_panel_main_topic_detail.html', context)

def admin_panel_chapters(request):
    """List view of all chapters"""
    search_query = request.GET.get('search', '')
    pdf_filter = request.GET.get('pdf', '')
    sort_by = request.GET.get('sort', 'order')
    
    # Base queryset
    chapters = Chapter.objects.all()
    
    # Apply search filter if provided
    if search_query:
        chapters = chapters.filter(title__icontains=search_query)
    
    # Filter by PDF if provided
    if pdf_filter and pdf_filter.isdigit():
        chapters = chapters.filter(pdf_document_id=pdf_filter)
    
    # Apply sorting
    if sort_by == 'title_asc':
        chapters = chapters.order_by('title')
    elif sort_by == 'title_desc':
        chapters = chapters.order_by('-title')
    elif sort_by == 'pdf':
        chapters = chapters.order_by('pdf_document__title', 'order')
    elif sort_by == 'pages':
        chapters = chapters.order_by('start_page')
    else:  # Default to order
        chapters = chapters.order_by('pdf_document__title', 'order')
    
    # Get all PDFs for filter dropdown
    pdfs = PDFDocument.objects.all().order_by('title')
    
    # Pagination
    paginator = Paginator(chapters, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'chapters',
        'chapters': page_obj,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'pdfs': pdfs
    }
    
    return render(request, 'dynamicDB/admin_panel_chapters.html', context)

def admin_panel_chapter_detail(request, pk):
    """Detail view for a single chapter"""
    chapter = get_object_or_404(Chapter, pk=pk)
    
    # Get associated topics
    topics = chapter.main_topics.order_by('order')
    
    context = {
        'active_page': 'chapters',
        'chapter': chapter,
        'topics': topics,
        'pdf': chapter.pdf_document
    }
    
    return render(request, 'dynamicDB/admin_panel_chapter_detail.html', context)

# AJAX API Endpoints

@csrf_exempt
def admin_panel_update_pdf(request, pk):
    """Update a PDF document via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    pdf = get_object_or_404(PDFDocument, pk=pk)
    title = request.POST.get('title', '')
    
    if not title:
        return JsonResponse({'success': False, 'message': 'Title cannot be empty'})
    
    pdf.title = title
    pdf.save()
    
    return JsonResponse({'success': True, 'message': 'PDF updated successfully'})

@csrf_exempt
def admin_panel_delete_pdf(request, pk):
    """Delete a PDF document via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    pdf = get_object_or_404(PDFDocument, pk=pk)
    
    try:
        # This will also delete all related topic groups, main topics, and chapters due to CASCADE
        pdf.delete()
        return JsonResponse({'success': True, 'message': 'PDF deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error deleting PDF: {str(e)}'})

@csrf_exempt
def admin_panel_update_topic_group(request, pk):
    """Update a topic group via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    topic_group = get_object_or_404(MainTopic, pk=pk)
    
    title = request.POST.get('title', '')
    description = request.POST.get('description', '')
    order = request.POST.get('order', '0')
    
    if not title:
        return JsonResponse({'success': False, 'message': 'Title cannot be empty'})
    
    topic_group.title = title
    topic_group.description = description
    topic_group.order = int(order)
    topic_group.save()
    
    return JsonResponse({'success': True, 'message': 'Topic group updated successfully'})

@csrf_exempt
def admin_panel_delete_topic_group(request, pk):
    """Delete a topic group via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    topic_group = get_object_or_404(MainTopic, pk=pk)
    
    try:
        topic_group.delete()
        return JsonResponse({'success': True, 'message': 'Topic group deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error deleting topic group: {str(e)}'})

@csrf_exempt
def admin_panel_update_main_topic(request, pk):
    """Update a main topic via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    main_topic = get_object_or_404(Topic, pk=pk)
    
    title = request.POST.get('title', '')
    summary = request.POST.get('summary', '')
    order = request.POST.get('order', '0')
    
    if not title:
        return JsonResponse({'success': False, 'message': 'Title cannot be empty'})
    
    main_topic.title = title
    main_topic.summary = summary
    main_topic.order = int(order)
    main_topic.save()
    
    return JsonResponse({'success': True, 'message': 'Main topic updated successfully'})

@csrf_exempt
def admin_panel_delete_main_topic(request, pk):
    """Delete a main topic via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    main_topic = get_object_or_404(Topic, pk=pk)
    
    try:
        main_topic.delete()
        return JsonResponse({'success': True, 'message': 'Main topic deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error deleting main topic: {str(e)}'})

@csrf_exempt
def admin_panel_update_chapter(request, pk):
    """Update a chapter via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    chapter = get_object_or_404(Chapter, pk=pk)
    
    title = request.POST.get('title', '')
    content = request.POST.get('content', '')
    start_page = request.POST.get('start_page', '1')
    end_page = request.POST.get('end_page', '1')
    order = request.POST.get('order', '0')
    
    if not title:
        return JsonResponse({'success': False, 'message': 'Title cannot be empty'})
    
    chapter.title = title
    chapter.content = content
    chapter.start_page = int(start_page)
    chapter.end_page = int(end_page)
    chapter.order = int(order)
    chapter.save()
    
    return JsonResponse({'success': True, 'message': 'Chapter updated successfully'})

@csrf_exempt
def admin_panel_delete_chapter(request, pk):
    """Delete a chapter via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method is allowed'})
    
    chapter = get_object_or_404(Chapter, pk=pk)
    
    try:
        chapter.delete()
        return JsonResponse({'success': True, 'message': 'Chapter deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error deleting chapter: {str(e)}'})

# PDF Selector Views

def pdf_selector(request):
    """View for selecting a PDF to use in the platform"""
    # Get all PDFs
    pdfs = PDFDocument.objects.all().order_by('-uploaded_at')
    
    # Get the current active PDF, if any
    active_pdf = None
    active_pdf_selection = None
    active_topic_groups = []
    active_topics = []
    
    try:
        active_pdf_selection = ActivePDFSelection.objects.filter(is_active=True).first()
        if active_pdf_selection:
            active_pdf = active_pdf_selection.pdf
            active_topic_groups = active_pdf.topic_groups.all().order_by('order')[:5]  # Show first 5 groups
            active_topics = active_pdf.main_topics.all().order_by('order')[:5]  # Show first 5 topics
    except Exception as e:
        print(f"Error fetching active PDF: {e}")
    
    context = {
        'active_page': 'pdf_selector',
        'pdfs': pdfs,
        'active_pdf': active_pdf,
        'active_pdf_selection': active_pdf_selection,
        'active_topic_groups': active_topic_groups,
        'active_topics': active_topics,
    }
    
    return render(request, 'dynamicDB/pdf_selector.html', context)

def set_active_pdf(request):
    """Set a PDF as active for the platform"""
    if request.method != 'POST':
        return redirect('dynamicDB:pdf_selector')
    
    pdf_id = request.POST.get('pdf_id')
    if not pdf_id:
        messages.error(request, 'No PDF selected')
        return redirect('dynamicDB:pdf_selector')
    
    try:
        pdf = PDFDocument.objects.get(pk=pdf_id)
        
        # Check if the PDF has content
        if pdf.main_topics.count() == 0 or pdf.chapters.count() == 0:
            messages.warning(request, f'PDF "{pdf.title}" has no topics or chapters. Please analyze it first.')
            return redirect('dynamicDB:analyze_pdf', pk=pdf.id)
        
        # Create or update active PDF selection
        selection, created = ActivePDFSelection.objects.get_or_create(
            pdf=pdf,
            defaults={'is_active': True}
        )
        
        if not created:
            # If it already exists, make sure it's active
            selection.is_active = True
            selection.save()
        
        messages.success(request, f'PDF "{pdf.title}" set as active content for the platform')
        
    except PDFDocument.DoesNotExist:
        messages.error(request, 'PDF not found')
    except Exception as e:
        messages.error(request, f'Error setting active PDF: {str(e)}')
    
    return redirect('dynamicDB:pdf_selector')

def get_pdf_structure(request):
    """AJAX endpoint to get PDF structure data"""
    pdf_id = request.GET.get('pdf_id')
    if not pdf_id:
        return JsonResponse({'success': False, 'message': 'No PDF ID provided'})
    
    try:
        pdf = PDFDocument.objects.get(pk=pdf_id)
        
        # Get topic groups data
        topic_groups_data = []
        for group in pdf.topic_groups.all().order_by('order'):
            topic_groups_data.append({
                'id': group.id,
                'title': group.title,
                'topic_count': group.topics.count()
            })
        
        # Get main topics data
        main_topics_data = []
        for topic in pdf.main_topics.all().order_by('order'):
            main_topics_data.append({
                'id': topic.id,
                'title': topic.title,
                'chapter_count': topic.chapters.count()
            })
        
        return JsonResponse({
            'success': True,
            'topic_groups': topic_groups_data,
            'main_topics': main_topics_data
        })
        
    except PDFDocument.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'PDF not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def get_active_pdf_data():
    """
    Utility function to get active PDF data for use in other views
    Returns a dictionary with active PDF and related data
    """
    result = {
        'active_pdf': None,
        'topic_groups': [],
        'main_topics': [],
        'chapters': []
    }
    
    try:
        active_pdf = ActivePDFSelection.get_active_pdf()
        if active_pdf:
            result['active_pdf'] = active_pdf
            result['topic_groups'] = list(active_pdf.topic_groups.all().order_by('order'))
            result['main_topics'] = list(active_pdf.main_topics.all().order_by('order'))
            result['chapters'] = list(active_pdf.chapters.all().order_by('order'))
    except Exception as e:
        print(f"Error getting active PDF data: {e}")
    
    return result

def active_topic_groups(request):
    """
    View for managing active topic groups
    """
    # Get the active PDF
    active_pdf = ActivePDFSelection.get_active_pdf()
    
    if not active_pdf:
        messages.warning(request, "Please select an active PDF first.")
        return redirect('dynamicDB:pdf_selector')
    
    # Get all topic groups from the active PDF
    topic_groups = MainTopic.objects.filter(pdf_document=active_pdf).order_by('order')
    
    # Get the currently active topic groups
    active_groups = ActiveTopicGroups.get_active_groups()
    active_group_ids = [group.topic_group.id for group in active_groups]
    
    context = {
        'active_page': 'active_topic_groups',
        'active_pdf': active_pdf,
        'topic_groups': topic_groups,
        'active_group_ids': active_group_ids,
        'active_groups': active_groups,
    }
    
    return render(request, 'dynamicDB/active_topic_groups.html', context)

def set_active_topic_group(request):
    """
    View to set a topic group as active
    """
    if request.method == 'POST':
        topic_group_id = request.POST.get('topic_group_id')
        
        if not topic_group_id:
            messages.error(request, "No topic group selected.")
            return redirect('dynamicDB:active_topic_groups')
        
        try:
            topic_group = MainTopic.objects.get(pk=topic_group_id)
            
            # Check if this topic group is already active
            if ActiveTopicGroups.objects.filter(topic_group=topic_group).exists():
                messages.info(request, f"Topic group '{topic_group.title}' is already active.")
            else:
                # Create new active topic group
                ActiveTopicGroups.objects.create(topic_group=topic_group)
                messages.success(request, f"Topic group '{topic_group.title}' set as active.")
            
        except MainTopic.DoesNotExist:
            messages.error(request, "Selected topic group does not exist.")
        
    return redirect('dynamicDB:active_topic_groups')

def remove_active_topic_group(request, pk):
    """
    View to remove a topic group from active groups
    """
    try:
        active_group = ActiveTopicGroups.objects.get(topic_group_id=pk)
        group_title = active_group.topic_group.title
        active_group.delete()
        messages.success(request, f"'{group_title}' removed from active topic groups.")
    except ActiveTopicGroups.DoesNotExist:
        messages.error(request, "This topic group is not active.")
    
    return redirect('dynamicDB:active_topic_groups')

def admin_panel_summary_topics(request):
    """View for managing summary topics"""
    summary_topics = SubTopic.objects.all().order_by('topic_group__title', 'order')
    topic_groups = MainTopic.objects.all().order_by('title')
    
    context = {
        'active_page': 'summary_topics',
        'summary_topics': summary_topics,
        'topic_groups': topic_groups
    }
    
    return render(request, 'dynamicDB/admin_panel_summary_topics.html', context)

def admin_panel_summary_topic_detail(request, pk):
    """View details of a specific summary topic"""
    summary_topic = get_object_or_404(SubTopic, pk=pk)
    all_main_topics = Topic.objects.filter(pdf_document=summary_topic.topic_group.pdf_document)
    
    context = {
        'active_page': 'summary_topics',
        'summary_topic': summary_topic,
        'all_main_topics': all_main_topics
    }
    
    return render(request, 'dynamicDB/admin_panel_summary_topic_detail.html', context)

def generate_summary_topics(request, topic_group_id):
    """
    Automatically generate summary topics for a topic group using Gemini AI
    Groups main topics into exactly 3 clusters and creates summary topics for each cluster
    """
    topic_group = get_object_or_404(MainTopic, pk=topic_group_id)
    
    try:
        # Get all main topics for this topic group
        main_topics = topic_group.topics.all()
        
        if main_topics.count() < 3:
            messages.warning(request, f"Topic group '{topic_group.title}' has fewer than 3 main topics. Please add more topics before generating summary topics.")
            return redirect('dynamicDB:admin_panel_topic_group_detail', pk=topic_group_id)
        
        # Delete existing summary topics for this group
        SubTopic.objects.filter(topic_group=topic_group).delete()
        
        # Prepare data for Gemini API
        topic_data = []
        topic_ids = []
        
        for topic in main_topics:
            topic_data.append({
                'id': topic.id,
                'title': topic.title,
                'summary': topic.summary
            })
            topic_ids.append(topic.id)
        
        # Check if GOOGLE_API_KEY is available
        if not settings.GOOGLE_API_KEY:
            messages.error(request, "Google API key is missing. Please set GOOGLE_API_KEY in your environment variables.")
            return redirect('dynamicDB:admin_panel_topic_group_detail', pk=topic_group_id)
        
        # Configure the Gemini API
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        # Create a model instance
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Construct the prompt for Gemini
        prompt = f"""
        Please analyze the following list of topics and group them into exactly 3 clusters based on semantic similarity:
        
        {json.dumps(topic_data, indent=2)}
        
        For each cluster:
        1. Create a title that captures the essence of the topics in that cluster (based on common words or themes)
        2. Generate a brief description of what these topics have in common
        3. Create a summary that combines the key points from all topics in the cluster
        
        Return your response as a valid JSON array with 3 items in this exact format:
        [
          {{
            "title": "Generated Title for Cluster 1",
            "description": "Description for Cluster 1",
            "summary": "Summary text for Cluster 1",
            "topic_ids": [list of topic IDs in this cluster]
          }},
          {{
            "title": "Generated Title for Cluster 2",
            "description": "Description for Cluster 2",
            "summary": "Summary text for Cluster 2",
            "topic_ids": [list of topic IDs in this cluster]
          }},
          {{
            "title": "Generated Title for Cluster 3",
            "description": "Description for Cluster 3",
            "summary": "Summary text for Cluster 3",
            "topic_ids": [list of topic IDs in this cluster]
          }}
        ]
        
        Ensure all topic IDs are assigned to one of the clusters, with no duplicates.
        """
        
        try:
            # Get response from Gemini
            response = model.generate_content(prompt)
            response_text = response.text
            
            # Extract the JSON part from the response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                response_json = json_match.group(1)
            else:
                response_json = response_text
            
            # Parse the JSON
            clusters = json.loads(response_json)
            
            # Ensure we have exactly 3 clusters
            if len(clusters) != 3:
                raise ValueError(f"Expected 3 clusters, but got {len(clusters)}")
            
            # Create summary topics for each cluster
            for i, cluster in enumerate(clusters):
                # Get the topics in this cluster
                topic_ids_in_cluster = cluster.get('topic_ids', [])
                topics_in_cluster = Topic.objects.filter(id__in=topic_ids_in_cluster)
                
                # Create the summary topic
                summary_topic = SubTopic.objects.create(
                    topic_group=topic_group,
                    title=cluster.get('title', f"Summary Group {i+1}"),
                    description=cluster.get('description', f"Automatically generated group of {len(topics_in_cluster)} related topics"),
                    summary=cluster.get('summary', ''),
                    order=i,
                    relevance_score=1.0  # Default score
                )
                
                # Add the main topics to this summary topic
                summary_topic.main_topics.set(topics_in_cluster)
            
            messages.success(request, f"Successfully created 3 summary topics for '{topic_group.title}' using Gemini AI")
            
        except Exception as e:
            messages.error(request, f"Error processing Gemini response: {str(e)}")
            # Fall back to basic grouping if Gemini fails
            fallback_to_basic_grouping(topic_group, main_topics)
    
    except Exception as e:
        messages.error(request, f"Error generating summary topics: {str(e)}")
    
    return redirect('dynamicDB:admin_panel_topic_group_detail', pk=topic_group_id)

def fallback_to_basic_grouping(topic_group, main_topics):
    """Fallback method to group topics without ML when Gemini fails"""
    # Divide topics into 3 roughly equal groups
    topics_list = list(main_topics)
    total_topics = len(topics_list)
    chunk_size = max(1, total_topics // 3)
    
    for i in range(3):
        # Calculate start and end indices for this group
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, total_topics) if i < 2 else total_topics
        
        # Get topics for this group
        group_topics = topics_list[start_idx:end_idx]
        
        if not group_topics:
            continue
            
        # Collect common words from titles
        common_words = []
        for topic in group_topics:
            words = topic.title.split()
            for word in words:
                if len(word) > 3 and word.lower() not in ['and', 'the', 'for', 'with']:
                    common_words.append(word)
        
        # Find frequent words for title
        word_counts = defaultdict(int)
        for word in common_words:
            word_counts[word.lower()] += 1
            
        most_common = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        most_common_words = [word for word, count in most_common]
        
        # Create title from most common words or use default
        if most_common_words:
            title = " ".join(most_common_words).title()
        else:
            title = f"Summary Group {i+1}"
        
        # Create the summary topic
        summary_topic = SubTopic.objects.create(
            topic_group=topic_group,
            title=title,
            description=f"Automatically generated group of {len(group_topics)} topics",
            order=i,
            relevance_score=1.0  # Default score
        )
        
        # Add the main topics to this summary topic
        summary_topic.main_topics.set(group_topics)
        
        # Generate a summary
        topic_summaries = [t.summary for t in group_topics if t.summary]
        if topic_summaries:
            combined_summary = " ".join(topic_summaries)
            # Truncate to a reasonable length
            if len(combined_summary) > 500:
                combined_summary = combined_summary[:497] + "..."
            summary_topic.summary = combined_summary
            summary_topic.save()

@csrf_exempt
def admin_panel_update_summary_topic(request, pk):
    """Update a summary topic via AJAX"""
    summary_topic = get_object_or_404(SubTopic, pk=pk)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Update basic fields
            summary_topic.title = data.get('title', summary_topic.title)
            summary_topic.description = data.get('description', summary_topic.description)
            summary_topic.summary = data.get('summary', summary_topic.summary)
            summary_topic.order = data.get('order', summary_topic.order)
            
            # Update main topics if provided
            if 'main_topic_ids' in data:
                main_topic_ids = data['main_topic_ids']
                main_topics = Topic.objects.filter(id__in=main_topic_ids)
                summary_topic.main_topics.set(main_topics)
            
            summary_topic.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def admin_panel_delete_summary_topic(request, pk):
    """Delete a summary topic via AJAX"""
    if request.method == 'POST':
        try:
            summary_topic = get_object_or_404(SubTopic, pk=pk)
            topic_group_id = summary_topic.topic_group.id
            summary_topic.delete()
            return JsonResponse({'success': True, 'redirect': f'/dynamicDB/admin-panel/topic-group/{topic_group_id}/'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def generate_summary_for_active_groups(request):
    """Generate summary topics for all active topic groups"""
    # Get all active topic groups
    active_groups = ActiveTopicGroups.get_active_groups()
    
    if not active_groups.exists():
        messages.warning(request, "No active topic groups found.")
        return redirect('dynamicDB:admin_panel_dashboard')
    
    success_count = 0
    error_count = 0
    
    # Process each active topic group
    for active_group in active_groups:
        topic_group = active_group.topic_group
        
        try:
            # Get all main topics for this topic group
            main_topics = topic_group.topics.all()
            
            if main_topics.count() < 3:
                messages.warning(request, f"Topic group '{topic_group.title}' has fewer than 3 main topics. Skipping.")
                error_count += 1
                continue
            
            # Delete existing summary topics for this group
            SubTopic.objects.filter(topic_group=topic_group).delete()
            
            # Prepare data for Gemini API
            topic_data = []
            topic_ids = []
            
            for topic in main_topics:
                topic_data.append({
                    'id': topic.id,
                    'title': topic.title,
                    'summary': topic.summary
                })
                topic_ids.append(topic.id)
            
            # Check if GOOGLE_API_KEY is available
            if not settings.GOOGLE_API_KEY:
                messages.error(request, "Google API key is missing. Please set GOOGLE_API_KEY in your environment variables.")
                return redirect('dynamicDB:admin_panel_dashboard')
            
            # Configure the Gemini API
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            
            # Create a model instance
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            # Construct the prompt for Gemini
            prompt = f"""
            Please analyze the following list of topics and group them into exactly 3 clusters based on semantic similarity:
            
            {json.dumps(topic_data, indent=2)}
            
            For each cluster:
            1. Create a title that captures the essence of the topics in that cluster (based on common words or themes)
            2. Generate a brief description of what these topics have in common
            3. Create a summary that combines the key points from all topics in the cluster
            
            Return your response as a valid JSON array with 3 items in this exact format:
            [
              {{
                "title": "Generated Title for Cluster 1",
                "description": "Description for Cluster 1",
                "summary": "Summary text for Cluster 1",
                "topic_ids": [list of topic IDs in this cluster]
              }},
              {{
                "title": "Generated Title for Cluster 2",
                "description": "Description for Cluster 2",
                "summary": "Summary text for Cluster 2",
                "topic_ids": [list of topic IDs in this cluster]
              }},
              {{
                "title": "Generated Title for Cluster 3",
                "description": "Description for Cluster 3",
                "summary": "Summary text for Cluster 3",
                "topic_ids": [list of topic IDs in this cluster]
              }}
            ]
            
            Ensure all topic IDs are assigned to one of the clusters, with no duplicates.
            """
            
            try:
                # Get response from Gemini
                response = model.generate_content(prompt)
                response_text = response.text
                
                # Extract the JSON part from the response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    response_json = json_match.group(1)
                else:
                    response_json = response_text
                
                # Parse the JSON
                clusters = json.loads(response_json)
                
                # Ensure we have exactly 3 clusters
                if len(clusters) != 3:
                    raise ValueError(f"Expected 3 clusters, but got {len(clusters)}")
                
                # Create summary topics for each cluster
                for i, cluster in enumerate(clusters):
                    # Get the topics in this cluster
                    topic_ids_in_cluster = cluster.get('topic_ids', [])
                    topics_in_cluster = Topic.objects.filter(id__in=topic_ids_in_cluster)
                    
                    # Create the summary topic
                    summary_topic = SubTopic.objects.create(
                        topic_group=topic_group,
                        title=cluster.get('title', f"Summary Group {i+1}"),
                        description=cluster.get('description', f"Automatically generated group of {len(topics_in_cluster)} related topics"),
                        summary=cluster.get('summary', ''),
                        order=i,
                        relevance_score=1.0  # Default score
                    )
                    
                    # Add the main topics to this summary topic
                    summary_topic.main_topics.set(topics_in_cluster)
                
                success_count += 1
                
            except Exception as e:
                error_message = f"Error processing Gemini response for '{topic_group.title}': {str(e)}"
                print(error_message)
                messages.error(request, error_message)
                
                # Fall back to basic grouping
                fallback_to_basic_grouping(topic_group, main_topics)
                success_count += 1  # Count as success since we used fallback
            
        except Exception as e:
            error_message = f"Error generating summary topics for '{topic_group.title}': {str(e)}"
            print(error_message)
            messages.error(request, error_message)
            error_count += 1
    
    # Show the final result message
    if success_count > 0:
        messages.success(request, f"Successfully generated summary topics for {success_count} active topic groups.")
    if error_count > 0:
        messages.warning(request, f"Failed to generate summary topics for {error_count} topic groups.")
    
    return redirect('dynamicDB:admin_panel_dashboard')
