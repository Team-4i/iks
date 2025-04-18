from django.shortcuts import render, redirect
from django.conf import settings
from .models import PDFDocument, Chapter, MainTopic
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

MAX_IMAGE_HEIGHT = 4000  # Further reduced to avoid any issues
MAX_PAGES_PER_IMAGE = 3  # Reduced for better processing of large PDFs

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
    
    # Add debugging information about the query results
    print(f"PDF Document: {pdf_doc.title}")
    print(f"Main Topics Count: {main_topics.count()}")
    print(f"Chapters Count: {chapters.count()}")
    
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
                
                # Process each image group and combine results
                all_topics = []
                
                # Show a progress message to the user
                messages.info(request, f"Processing {len(image_files)} page groups. This may take some time for large documents.")
                
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
                    from .models import MainTopic, Chapter
                    
                    # Delete existing chapters and topics
                    pdf_doc.chapters.all().delete()
                    pdf_doc.main_topics.all().delete()
                    
                    # Save combined topics to database
                    topics_count = 0
                    chapters_count = 0
                    
                    for topic_data in all_topics:
                        # Create MainTopic
                        main_topic = MainTopic.objects.create(
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
                        f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters."
                    )
                else:
                    # Fallback to single image analysis
                    print("No topics found in page images, using converted image")
                    result = analyzer.process_document(pdf_doc)
                    messages.success(
                        request, 
                        f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters."
                    )
            else:
                # No image files found, use the converted image
                print("No image files found, using converted image")
                analyzer = TextbookAnalyzer()
                result = analyzer.process_document(pdf_doc)
                messages.success(
                    request, 
                    f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters."
                )
        else:
            # No page_images directory, use the converted image
            print("No page_images directory found, using converted image")
            analyzer = TextbookAnalyzer()
            result = analyzer.process_document(pdf_doc)
            messages.success(
                request, 
                f"PDF analysis completed! Extracted {result['topics_count']} topics with {result['chapters_count']} chapters."
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
    
    return render(request, 'dynamicDB/visualize.html', {
        'pdf_doc': pdf_doc,
        'topic_data': json.dumps(topic_data)
    })
