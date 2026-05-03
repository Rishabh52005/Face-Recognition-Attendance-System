// Modern Face Attendance JS
// Camera, animations, API calls

document.addEventListener('DOMContentLoaded', function() {
    // Theme toggle
    const themeIcon = document.getElementById('theme-icon');
    const body = document.body;

    function applyTheme(theme, persist = true) {
        body.dataset.theme = theme;
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        if (persist) {
            localStorage.setItem('theme', theme);
        }
        document.dispatchEvent(new CustomEvent('themechange', {
            detail: { theme }
        }));
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme, false);

    if (themeIcon) {
        themeIcon.addEventListener('click', () => {
            const nextTheme = body.dataset.theme === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
        });
    }
    
    // Auto-hide alerts
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        });
    }, 5000);
    
    initAttendanceCamera();
});

function initAttendanceCamera() {
    const video = document.getElementById('video');
    if (!video) return;
    
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
        .then(stream => {
            video.srcObject = stream;
            video.play();
            
            // Start recognition loop
            recognizeFaces(video);
        })
        .catch(err => {
            console.error('Camera access denied:', err);
            showStatus('Camera access denied. Please enable camera permissions.', 'error');
        });
}

let recognitionInterval;
function recognizeFaces(video) {
    if (recognitionInterval) clearInterval(recognitionInterval);
    
    recognitionInterval = setInterval(() => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        
        fetch('/recognize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData }),
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatus(data.message, 'success');
                updateAttendanceCount();
            }
        })
        .catch(err => console.error('Recognition error:', err));
    }, 2000); // Check every 2 seconds
}

function showStatus(message, type = 'info') {
    const overlay = document.querySelector('.status-overlay') || createStatusOverlay();
    overlay.textContent = message;
    overlay.className = `status-overlay ${type}`;
    overlay.classList.remove('hidden');
    
    setTimeout(() => {
        overlay.classList.add('hidden');
    }, 3000);
}

function createStatusOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'status-overlay hidden';
    document.querySelector('.video-wrapper').appendChild(overlay);
    return overlay;
}

function updateAttendanceCount() {
    fetch('/api/attendance-percentage', { credentials: 'include' })
        .then(r => r.json())
        .then(data => {
            document.querySelector('.present-count').textContent = data.present;
            document.querySelector('.percentage').textContent = data.percentage + '%';
        });
}

// Stats animation on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateCounter(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.stat-number').forEach(stat => {
    observer.observe(stat);
});

function animateCounter(element) {
    const target = parseInt(element.textContent);
    let current = 0;
    const increment = target / 60;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({
            behavior: 'smooth'
        });
    });
});

