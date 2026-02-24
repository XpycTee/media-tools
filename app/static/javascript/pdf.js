// Set up PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/javascript/utils/pdf.worker.min.js';

const RENDER_SCALE = 2;

// Store for all pages/images with their data
let pages = [];
let pageIdCounter = 0;
let fileMap = new Map(); // Store original files by sourceFile key

// Fullscreen viewer state
let currentViewerPages = [];
let currentViewerIndex = 0;
let currentViewerFile = null;
let currentZoom = 1;
let currentContentWidth = 0;
let currentContentHeight = 0;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.2;

// Pan/drag state
let isPanning = false;
let panStartX = 0;
let panStartY = 0;
let panStartScrollX = 0;
let panStartScrollY = 0;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable for pages container
    const container = document.getElementById('pdf-pages');
    if (container) {
        new Sortable(container, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            onEnd: function() {
                // Update page indices after sorting
                updatePageIndices();
            }
        });
        
        // Setup drag and drop
        setupDragAndDrop(container);
    }
});

function addUploadButton(type) {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    
    if (type === 'pdf') {
        input.accept = '.pdf';
    } else {
        input.accept = '.jpg,.jpeg,.png,.gif,.bmp,.webp';
    }
    
    input.onchange = (e) => handleFileUpload(e, type);
    input.click();
}

async function handleFileUpload(event, type) {
    const files = Array.from(event.target.files);
    
    for (const file of files) {
        // Store original file
        const fileKey = `${file.name}_${Date.now()}`;
        fileMap.set(fileKey, file);
        
        if (type === 'pdf') {
            await handlePdfFile(file, fileKey);
        } else {
            await handleImageFile(file, fileKey);
        }
    }
}

async function handlePdfFile(file, fileKey) {
    const arrayBuffer = await file.arrayBuffer();
    
    try {
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        
        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
            const page = await pdf.getPage(pageNum);
            const viewport = page.getViewport({ scale: RENDER_SCALE });
            
            // Create canvas for rendering
            const canvas = document.createElement('canvas');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            
            const context = canvas.getContext('2d');
            await page.render({ canvasContext: context, viewport: viewport }).promise;
            
            // Add to pages array
            addPageToContainer(canvas, file.name, pageNum, 'pdf', fileKey);
        }
    } catch (error) {
        alert(`Ошибка при обработке PDF ${file.name}: ${error.message}`);
    }
}

async function handleImageFile(file, fileKey) {
    const reader = new FileReader();
    
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            addPageToContainer(img, file.name, null, 'image', fileKey);
        };
        img.onerror = () => {
            alert(`Ошибка при загрузке изображения: ${file.name}`);
        };
        img.src = e.target.result;
    };
    
    reader.readAsDataURL(file);
}

function addPageToContainer(element, sourceFile, pageNum, type, fileKey) {
    const container = document.getElementById('pdf-pages');
    const pageId = `page-${pageIdCounter++}`;
    
    const pageDiv = document.createElement('div');
    pageDiv.className = 'pdf-page-item';
    pageDiv.dataset.id = pageId;
    pageDiv.dataset.sourceFile = sourceFile;
    pageDiv.dataset.pageNum = pageNum || 'image';
    pageDiv.dataset.type = type;
    pageDiv.dataset.fileKey = fileKey;
    
    // Set width and height based on content
    if (element.tagName === 'CANVAS' || element.tagName === 'IMG') {
        const aspect = element.width / element.height;
        pageDiv.style.width = '180px';
        pageDiv.style.height = `${Math.round(180 / aspect)}px`;
    }
    
    if (element.tagName === 'CANVAS') {
        pageDiv.appendChild(element);
    } else {
        pageDiv.appendChild(element);
    }
    
    // Add page number or image label
    const label = document.createElement('div');
    label.className = 'page-number';
    label.textContent = type === 'pdf' ? `стр. ${pageNum}` : 'изо';
    pageDiv.appendChild(label);
    
    // Add delete button
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-btn';
    deleteBtn.textContent = '✕';
    deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deletePage(pageId);
    };
    pageDiv.appendChild(deleteBtn);
    
    // Add click handler to open in fullscreen
    pageDiv.onclick = (e) => {
        if (e.target !== deleteBtn && !deleteBtn.contains(e.target)) {
            openPageViewer(sourceFile, pageNum, type);
        }
    };
    
    container.appendChild(pageDiv);
    
    // Store page info
    pages.push({
        id: pageId,
        element: element,
        sourceFile: sourceFile,
        pageNum: pageNum,
        type: type,
        fileKey: fileKey
    });
    
    // Hide hint when first page is added
    updateHintVisibility();
}

function deletePage(pageId) {
    const pageDiv = document.querySelector(`[data-id="${pageId}"]`);
    if (pageDiv) {
        pageDiv.remove();
        pages = pages.filter(p => p.id !== pageId);
        updatePageIndices();
        updateHintVisibility();
    }
}

function updatePageIndices() {
    const items = document.querySelectorAll('.pdf-page-item');
    items.forEach((item, index) => {
        item.dataset.index = index;
    });
}

function updateHintVisibility() {
    const hint = document.querySelector('.drop-hint');
    const items = document.querySelectorAll('.pdf-page-item');
    
    if (items.length === 0) {
        hint.classList.remove('hidden');
    } else {
        hint.classList.add('hidden');
    }
}

async function splitPdf() {
    const items = document.querySelectorAll('.pdf-page-item');
    
    if (items.length === 0) {
        alert('Добавьте хотя бы одну страницу PDF');
        return;
    }
    
    // Create ZIP using JSZip library
    const script = document.createElement('script');
    script.src = '/static/javascript/utils/jszip.min.js';
    script.onload = async () => {
        const JSZip = window.JSZip;
        const zip = new JSZip();
        
        for (let index = 0; index < items.length; index++) {
            const item = items[index];
            const canvas = item.querySelector('canvas');
            const img = item.querySelector('img');
            const element = canvas || img;
            
            if (!element) continue;
            
            try {
                let blob;
                if (canvas) {
                    // Convert canvas to JPEG blob with quality
                    blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.90));
                } else if (img && img.src.startsWith('data:')) {
                    // Convert data URL to blob
                    const response = await fetch(img.src);
                    blob = await response.blob();
                } else {
                    continue;
                }
                
                // Add to ZIP with name "page_001.jpg", "page_002.jpg", etc.
                const pageName = `page_${String(index + 1).padStart(3, '0')}.jpg`;
                zip.file(pageName, blob);
            } catch (err) {
                console.error(`Error processing page ${index}:`, err);
            }
        }
        
        // Generate ZIP and download
        try {
            const zipBlob = await zip.generateAsync({ type: 'blob' });
            const url = window.URL.createObjectURL(zipBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pdf_pages_${new Date().getTime()}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            
            alert('PDF разделен на страницы и загружен!');
        } catch (err) {
            alert('Ошибка при создании архива: ' + err.message);
        }
    };
    document.head.appendChild(script);
}

async function compilePdf() {
    const items = document.querySelectorAll('.pdf-page-item');
    
    if (items.length === 0) {
        alert('Добавьте хотя бы одну страницу или изображение');
        return;
    }
    
    // Prepare FormData with files in correct order
    const formData = new FormData();
    
    for (let index = 0; index < items.length; index++) {
        const item = items[index];
        const canvas = item.querySelector('canvas');
        const img = item.querySelector('img');
        const element = canvas || img;
        
        if (!element) continue;
        
        try {
            // Convert each element to blob and append IN ORDER
            if (canvas) {
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.75));
                formData.append('files', blob, `page_${index}.jpg`);
            } else if (img && img.src.startsWith('data:')) {
                const response = await fetch(img.src);
                const blob = await response.blob();
                formData.append('files', blob, `page_${index}.jpg`);
            }
        } catch (err) {
            alert(`Ошибка при обработке страницы ${index}: ${err.message}`);
            return;
        }
    }
    
    try {
        const response = await fetch("/api/pdf/merge", {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Ошибка сервера: ' + response.statusText);
        
        // Download the PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'merged.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        alert('PDF успешно создан и загружен!');
    } catch (err) {
        alert('Ошибка при создании PDF: ' + err.message);
    }
}

function openCompressModal() {
    document.getElementById('compressModal').style.display = 'block';
}

function closeCompressModal() {
    document.getElementById('compressModal').style.display = 'none';
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    const modal = document.getElementById('compressModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

async function compressPdf() {
    const quality = parseInt(document.getElementById('qualityInput').value) || 75;
    const resize = parseInt(document.getElementById('resizeInput').value) || 100;
    
    // Validate inputs
    if (quality < 1 || quality > 100) {
        alert('Качество должно быть от 1 до 100');
        return;
    }
    if (resize < 10 || resize > 100) {
        alert('Размер должен быть от 10 до 100%');
        return;
    }
    
    // Get all loaded pages and merge them into PDF first
    const items = document.querySelectorAll('.pdf-page-item');
    
    if (items.length === 0) {
        alert('Добавьте хотя бы одну страницу для сжатия');
        return;
    }
    
    try {
        // Prepare FormData with ORIGINAL files
        const formData = new FormData();
        const processedFiles = new Map();
        
        for (let index = 0; index < items.length; index++) {
            const item = items[index];
            const fileKey = item.dataset.fileKey;
            
            // Get original file from fileMap
            if (fileKey && fileMap.has(fileKey) && !processedFiles.has(fileKey)) {
                const originalFile = fileMap.get(fileKey);
                formData.append('files', originalFile);
                processedFiles.set(fileKey, true);
            }
        }
        
        if (formData.getAll('files').length === 0) {
            alert('Не найдены оригинальные файлы для сжатия');
            return;
        }
        
        // First merge the PDF
        const mergeResponse = await fetch("/api/pdf/merge", {
            method: 'POST',
            body: formData
        });
        
        if (!mergeResponse.ok) throw new Error('Ошибка при объединении: ' + mergeResponse.statusText);
        
        // Get merged PDF
        const mergedPdf = await mergeResponse.blob();
        
        // Now compress the merged PDF
        const compressFormData = new FormData();
        compressFormData.append('pdf_file', mergedPdf, 'merged.pdf');
        compressFormData.append('quality', quality);
        compressFormData.append('resize', resize);
        
        const compressResponse = await fetch('/api/pdf/compress', {
            method: 'POST',
            body: compressFormData
        });
        
        if (!compressResponse.ok) throw new Error('Ошибка сервера: ' + compressResponse.statusText);
        
        // Download compressed PDF
        const compressedBlob = await compressResponse.blob();
        const url = window.URL.createObjectURL(compressedBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'compressed.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        alert('PDF успешно сжат и загружен!');
        closeCompressModal();
    } catch (err) {
        alert('Ошибка при сжатии PDF: ' + err.message);
    }
}

// Fullscreen page viewer functions
function openPageViewer(sourceFile, pageNum, type) {
    // Get all pages from the same source file
    currentViewerPages = pages.filter(p => p.sourceFile === sourceFile);
    currentViewerFile = sourceFile;
    
    // Sort by page number if it's a PDF
    if (type === 'pdf' && currentViewerPages.length > 1) {
        currentViewerPages.sort((a, b) => a.pageNum - b.pageNum);
    }
    
    // Find the index of the clicked page
    if (type === 'pdf') {
        currentViewerIndex = currentViewerPages.findIndex(p => p.pageNum === pageNum);
    } else {
        currentViewerIndex = 0;
    }
    
    // Show modal first to get correct container dimensions
    const modal = document.getElementById('pageViewerModal');
    modal.classList.add('active');
    
    // Display the page
    displayViewerPage();
    
    // Setup zoom wheel listener and pan listener
    setupZoomWheelListener();
    setupPanListener();
    
    // Add keyboard navigation
    document.addEventListener('keydown', handlePageViewerKeydown);
}

function displayViewerPage() {
    if (currentViewerPages.length === 0) return;
    
    const page = currentViewerPages[currentViewerIndex];
    const content = document.getElementById('pageViewerContent');
    
    // Clear previous content
    content.innerHTML = '';
    content.style.transform = 'scale(1)';
    
    // Clone the element to display
    const element = page.element;
    let displayElement;
    
    if (element.tagName === 'CANVAS') {
        // Create a new canvas and copy the image data
        displayElement = document.createElement('canvas');
        displayElement.width = element.width;
        displayElement.height = element.height;
        const ctx = displayElement.getContext('2d');
        ctx.drawImage(element, 0, 0);
    } else if (element.tagName === 'IMG') {
        displayElement = document.createElement('img');
        displayElement.src = element.src;
    }
    
    if (displayElement) {
        content.appendChild(displayElement);
        // Store the content dimensions and calculate fit-to-container zoom
        // Use requestAnimationFrame to ensure layout has been computed
        requestAnimationFrame(() => {
            currentContentWidth = displayElement.width || displayElement.offsetWidth || 400;
            currentContentHeight = displayElement.height || displayElement.offsetHeight || 300;
            
            // Calculate zoom to fit content into container
            const container = document.getElementById('pageViewerContainer');
            if (!container || container.clientWidth === 0) {
                // Container not ready, use defaults
                currentZoom = 1;
                applyZoom();
                return;
            }
            
            const availableWidth = container.clientWidth;
            const availableHeight = container.clientHeight;
            
            // Add padding buffer to ensure content doesn't touch edges
            const paddingBuffer = 20;
            const adjustedWidth = Math.max(availableWidth - paddingBuffer, 100);
            const adjustedHeight = Math.max(availableHeight - paddingBuffer, 100);
            
            const scaleW = adjustedWidth / currentContentWidth;
            const scaleH = adjustedHeight / currentContentHeight;
            currentZoom = Math.min(scaleW, scaleH, 1); // Don't zoom in, only fit
            
            applyZoom();
        });
    } else {
        applyZoom();
    }
    
    // Update page counter and buttons
    const current = currentViewerIndex + 1;
    const total = currentViewerPages.length;
    document.getElementById('pageCounter').textContent = `${current} / ${total}`;
    
    document.getElementById('prevBtn').disabled = currentViewerIndex === 0;
    document.getElementById('nextBtn').disabled = currentViewerIndex === currentViewerPages.length - 1;
}

function previousPage() {
    if (currentViewerIndex > 0) {
        currentViewerIndex--;
        displayViewerPage();
    }
}

function nextPage() {
    if (currentViewerIndex < currentViewerPages.length - 1) {
        currentViewerIndex++;
        displayViewerPage();
    }
}

function closePageViewer() {
    const modal = document.getElementById('pageViewerModal');
    modal.classList.remove('active');
    document.removeEventListener('keydown', handlePageViewerKeydown);
}

function handlePageViewerKeydown(e) {
    if (e.key === 'ArrowLeft') {
        previousPage();
    } else if (e.key === 'ArrowRight') {
        nextPage();
    } else if (e.key === 'Escape') {
        closePageViewer();
    }
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const modal = document.getElementById('pageViewerModal');
    const content = document.querySelector('.fullscreen-content');
    if (event.target === modal || (event.target === content.parentNode && event.target === modal)) {
        closePageViewer();
    }
});

// Drag and Drop functionality
function setupDragAndDrop(container) {
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        container.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        container.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        container.addEventListener(eventName, unhighlight, false);
    });
    
    // Handle dropped files
    container.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    const container = document.getElementById('pdf-pages');
    container.classList.add('drag-over');
}

function unhighlight(e) {
    const container = document.getElementById('pdf-pages');
    container.classList.remove('drag-over');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    // Filter and process PDF and image files
    const pdfFiles = [];
    const imageFiles = [];
    
    for (let file of files) {
        if (file.type === 'application/pdf') {
            pdfFiles.push(file);
        } else if (file.type.startsWith('image/')) {
            imageFiles.push(file);
        }
    }
    
    // Process all files
    if (pdfFiles.length > 0) {
        processDroppedFiles(pdfFiles, 'pdf');
    }
    if (imageFiles.length > 0) {
        processDroppedFiles(imageFiles, 'image');
    }
}

async function processDroppedFiles(files, type) {
    for (const file of files) {
        // Store original file
        const fileKey = `${file.name}_${Date.now()}`;
        fileMap.set(fileKey, file);
        
        if (type === 'pdf') {
            await handlePdfFile(file, fileKey);
        } else {
            await handleImageFile(file, fileKey);
        }
    }
}

// Zoom functions for fullscreen viewer
function zoomIn() {
    if (currentZoom < MAX_ZOOM) {
        currentZoom += ZOOM_STEP;
        currentZoom = Math.min(currentZoom, MAX_ZOOM);
        applyZoom();
    }
}

function zoomOut() {
    if (currentZoom > MIN_ZOOM) {
        currentZoom -= ZOOM_STEP;
        currentZoom = Math.max(currentZoom, MIN_ZOOM);
        applyZoom();
    }
}

function resetZoom() {
    currentZoom = 1;
    applyZoom();
}

function applyZoom() {
    const content = document.getElementById('pageViewerContent');
    const zoomLevel = document.getElementById('zoomLevel');
    
    // Apply zoom transformation - this makes the content scale at center point
    content.style.transform = `scale(${currentZoom})`;
    
    // Update zoom level display
    zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
    
    // Update button states
    document.getElementById('zoomOutBtn').disabled = currentZoom <= MIN_ZOOM;
    document.getElementById('zoomInBtn').disabled = currentZoom >= MAX_ZOOM;
    
    // Update cursor based on zoom level
    updateContainerCursor();
}

// Mouse wheel zoom
function setupZoomWheelListener() {
    const container = document.getElementById('pageViewerContainer');
    if (container) {
        container.addEventListener('wheel', function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                if (e.deltaY < 0) {
                    zoomIn();
                } else {
                    zoomOut();
                }
            }
        }, { passive: false });
    }
}

// Pan/Drag functionality
function setupPanListener() {
    const container = document.querySelector('.page-viewer-container');
    if (container) {
        container.addEventListener('mousedown', handlePanStart);
        document.addEventListener('mousemove', handlePanMove);
        document.addEventListener('mouseup', handlePanEnd);
    }
}

function handlePanStart(e) {
    // Only pan if zoomed in (zoom > 1)
    if (currentZoom <= 1) return;
    
    // Check if we can scroll (has scrollbars)
    const container = document.querySelector('.page-viewer-container');
    const hasScroll = container.scrollHeight > container.clientHeight || container.scrollWidth > container.clientWidth;
    if (!hasScroll) return;
    
    isPanning = true;
    panStartX = e.clientX;
    panStartY = e.clientY;
    
    panStartScrollX = container.scrollLeft;
    panStartScrollY = container.scrollTop;
    
    // Change cursor to grabbing
    container.style.cursor = 'grabbing';
    e.preventDefault();
}

function handlePanMove(e) {
    if (!isPanning || currentZoom <= 1) return;
    
    const container = document.querySelector('.page-viewer-container');
    const deltaX = panStartX - e.clientX;
    const deltaY = panStartY - e.clientY;
    
    container.scrollLeft = panStartScrollX + deltaX;
    container.scrollTop = panStartScrollY + deltaY;
}

function handlePanEnd(e) {
    if (!isPanning) return;
    
    isPanning = false;
    const container = document.querySelector('.page-viewer-container');
    container.style.cursor = 'grab';
}

function updateContainerCursor() {
    const container = document.querySelector('.page-viewer-container');
    if (container) {
        if (currentZoom > 1) {
            container.style.cursor = 'grab';
        } else {
            container.style.cursor = 'default';
        }
    }
}

