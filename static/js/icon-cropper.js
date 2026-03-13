// ============================================
// Shared Icon Cropper Module
// ============================================

const ICON_MIN_SIZE = 128;
const ICON_OUTPUT_SIZE = 256;

function createCropperWithOverlay(cropperImage, container, options = {}) {
    const cropper = new Cropper(cropperImage, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: 'move',
        autoCropArea: 1,
        restore: false,
        guides: true,
        center: true,
        highlight: false,
        cropBoxMovable: true,
        cropBoxResizable: true,
        toggleDragModeOnDblclick: false,
        minCropBoxWidth: options.minSize || ICON_MIN_SIZE,
        minCropBoxHeight: options.minSize || ICON_MIN_SIZE,
        ready: function() {
            if (options.onReady) options.onReady();
            // Add circular overlay
            const cropBox = container?.querySelector('.cropper-crop-box');
            if (cropBox && !cropBox.querySelector('.circular-overlay')) {
                const overlay = document.createElement('div');
                overlay.className = 'circular-overlay';
                overlay.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; bottom: 0; border: 2px solid white; border-radius: 50%; pointer-events: none; box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);';
                cropBox.appendChild(overlay);
            }
        },
        crop: function() {
            if (options.onCrop) options.onCrop();
        }
    });
    return cropper;
}
