// Add these functions at the top of the file
function toggleMenu() {
    const navLinks = document.getElementById("navLinks");
    if (navLinks.className === "topnav-links") {
        navLinks.className += " responsive";
    } else {
        navLinks.className = "topnav-links";
    }
}

function closeMenu() {
    const navLinks = document.getElementById("navLinks");
    navLinks.className = "topnav-links";
}

// PDF viewer controls
const viewer = document.getElementById('pdf-viewer');
const zoomIn = document.getElementById('zoom-in');
const zoomOut = document.getElementById('zoom-out');
const resetView = document.getElementById('reset-view');
const downloadPdf = document.getElementById('download-pdf');
const pdfUrl = 'https://arxiv.org/pdf/2307.15055.pdf';

// Initialize PDF.js viewer
let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.0;
let canvas = document.getElementById('pdf-canvas');
let ctx = canvas ? canvas.getContext('2d') : null;

/**
 * Renders the current page to the canvas
 * @param {Number} num - Page number to render
 */
function renderPage(num) {
    if (!pdfDoc) return;
    
    pageRendering = true;
    pdfDoc.getPage(num).then(function(page) {
        const viewport = page.getViewport({scale: scale});
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        
        const renderContext = {
            canvasContext: ctx,
            viewport: viewport
        };
        
        const renderTask = page.render(renderContext);
        
        renderTask.promise.then(function() {
            pageRendering = false;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    });
    
    document.getElementById('page-num').textContent = num;
}

/**
 * Queues the rendering of a page if another page is currently rendering
 * @param {Number} num - Page number to queue for rendering
 */
function queueRenderPage(num) {
    if (pageRendering) {
        pageNumPending = num;
    } else {
        renderPage(num);
    }
}

/**
 * Navigates to the previous page if available
 */
function onPrevPage() {
    if (pageNum <= 1) return;
    pageNum--;
    queueRenderPage(pageNum);
}

/**
 * Navigates to the next page if available
 */
function onNextPage() {
    if (pageNum >= pdfDoc.numPages) return;
    pageNum++;
    queueRenderPage(pageNum);
}

// Zoom functions
/**
 * Increases the zoom level of the PDF
 */
function onZoomIn() {
    scale += 0.25;
    queueRenderPage(pageNum);
}

/**
 * Decreases the zoom level of the PDF
 */
function onZoomOut() {
    if (scale <= 0.5) return;
    scale -= 0.25;
    queueRenderPage(pageNum);
}

/**
 * Resets the zoom level to default
 */
function onResetZoom() {
    scale = 1.0;
    queueRenderPage(pageNum);
}

// Initialize PDF.js
if (canvas && ctx) {
    pdfjsLib.getDocument(pdfUrl).promise.then(function(doc) {
        pdfDoc = doc;
        document.getElementById('page-count').textContent = doc.numPages;
        renderPage(pageNum);
        
        // Set up button event listeners
        document.getElementById('prev-page').addEventListener('click', onPrevPage);
        document.getElementById('next-page').addEventListener('click', onNextPage);
        document.getElementById('zoom-in').addEventListener('click', onZoomIn);
        document.getElementById('zoom-out').addEventListener('click', onZoomOut);
        document.getElementById('reset-view').addEventListener('click', onResetZoom);
        document.getElementById('download-pdf').addEventListener('click', function() {
            window.open(pdfUrl, '_blank');
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video');
    
    // Force play when loaded
    video.play().catch(function(error) {
        console.log("Video play failed:", error);
    });

    // Ensure video keeps playing
    video.addEventListener('pause', function() {
        video.play();
    });

    // Handle video ending
    video.addEventListener('ended', function() {
        video.play();
    });

    if (video) {
        video.addEventListener('error', function(e) {
            console.error('Error loading video:', e);
        });
        
        video.play().catch(function(error) {
            console.log("Video autoplay failed:", error);
        });
    }
    
    // Check for missing images
    document.querySelectorAll('img').forEach(img => {
        img.onerror = function() {
            console.error('Failed to load image:', img.src);
            img.src = 'assets/placeholder.png'; // Add a placeholder image
        };
    });
});