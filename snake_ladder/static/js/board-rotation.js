// Board rotation functionality
function initializeBoardRotation() {
    const board = document.querySelector('.constitution-board');
    let isDragging = false;
    let startX, startY, rotateX = 15, rotateY = 0;

    // Hover effect
    board.addEventListener('mousemove', (e) => {
        if (isDragging) return; // Don't apply hover effect while dragging

        // Get mouse position relative to board center
        const rect = board.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Calculate rotation based on mouse distance from center
        const mouseX = e.clientX - centerX;
        const mouseY = e.clientY - centerY;
        
        // Convert to rotation angles (reduced effect for subtlety)
        rotateY = (mouseX / rect.width) * 10;
        rotateX = 15 - (mouseY / rect.height) * 10;
        
        // Apply smooth rotation
        board.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    // Reset position when mouse leaves
    board.addEventListener('mouseleave', () => {
        if (!isDragging) {
            board.style.transform = `perspective(1000px) rotateX(15deg) rotateY(0deg)`;
        }
    });

    // Dragging functionality
    board.addEventListener('mousedown', (e) => {
        isDragging = true;
        board.classList.add('grabbing');
        startX = e.clientX;
        startY = e.clientY;
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;
        
        rotateY = deltaX * 0.5;
        rotateX = 15 + (deltaY * 0.5);
        
        // Limit rotation
        rotateX = Math.max(-30, Math.min(60, rotateX));
        rotateY = Math.max(-30, Math.min(30, rotateY));
        
        board.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        board.classList.remove('grabbing');
        
        // Animate back to original position
        board.style.transform = `perspective(1000px) rotateX(15deg) rotateY(0deg)`;
        rotateX = 15;
        rotateY = 0;
    });

    // Prevent drag issues
    board.addEventListener('dragstart', (e) => e.preventDefault());
}

// Initialize when document is loaded
document.addEventListener('DOMContentLoaded', initializeBoardRotation); 

