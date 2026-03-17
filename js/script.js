document.addEventListener('DOMContentLoaded', () => {

    /* --- Navigation --- */
    const mobileMenu = document.getElementById('mobile-menu');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');

    if (mobileMenu) {
        mobileMenu.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }

    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            mobileMenu.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        if (navbar && window.scrollY > 50) {
            navbar.style.background = 'rgba(13, 13, 13, 0.98)';
        } else if (navbar) {
            navbar.style.background = 'rgba(13, 13, 13, 0.95)';
        }
    });

    /* --- Portfolio Filter (Updated Categories) --- */
    const filterBtns = document.querySelectorAll('.filter-btn');
    const portfolioGrid = document.getElementById('portfolioGrid');

    if (filterBtns.length > 0 && portfolioGrid) {
        const portfolioItems = portfolioGrid.querySelectorAll('.portfolio-item');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const filter = btn.getAttribute('data-filter');

                portfolioItems.forEach(item => {
                    const cat = item.getAttribute('data-category');
                    if (filter === 'all' || filter === cat) {
                        item.style.display = 'block';
                        item.style.opacity = '1';
                    } else {
                        item.style.display = 'none';
                        item.style.opacity = '0';
                    }
                });
            });
        });
    }

    /* --- Chatbot Logic (Trained & Professional) --- */
    const chatToggle = document.getElementById('chatToggle');
    const chatWindow = document.getElementById('chatWindow');
    const closeChat = document.getElementById('closeChat');
    const chatBody = document.getElementById('chatBody');
    const chatInput = document.getElementById('chatInput');
    const sendMessage = document.getElementById('sendMessage');
    let welcomeShown = false;

    function toggleChat() {
        chatWindow.classList.toggle('active');
        if (chatWindow.classList.contains('active')) {
            setTimeout(() => chatInput.focus(), 300);
            if (!welcomeShown) {
                showInitialGreeting();
                welcomeShown = true;
            }
        }
    }

    function showInitialGreeting() {
        addMessage("Welcome to RoyalVista Tech Solutions!", 'bot-message');
        setTimeout(() => {
            addMessage("I'm your AI assistant. I can guide you through our Services, help with Order creation, or provide Support. How can I help you today?", 'bot-message');
        }, 800);
    }

    if (chatToggle) chatToggle.addEventListener('click', toggleChat);
    if (closeChat) closeChat.addEventListener('click', toggleChat);

    // Close chatbot when clicking outside
    document.addEventListener('click', (e) => {
        if (chatWindow && chatWindow.classList.contains('active')) {
            // Check if click is outside chatbot window and not on the toggle button
            if (!chatWindow.contains(e.target) && !chatToggle.contains(e.target)) {
                chatWindow.classList.remove('active');
            }
        }
    });

    function addMessage(text, className, cta = null) {
        if (!chatBody) return;
        const div = document.createElement('div');
        div.className = `message ${className}`;
        let content = `<p>${text}</p>`;
        if (cta) {
            content += `<a href="${cta.link}" class="btn-small btn-primary chatbot-cta" style="display:inline-block; margin-top:10px; text-decoration:none;">${cta.text}</a>`;
        }
        div.innerHTML = content;
        chatBody.appendChild(div);

        // Add click handler for CTA buttons
        if (cta) {
            const ctaBtn = div.querySelector('.chatbot-cta');
            if (ctaBtn) {
                ctaBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    // Close chatbot
                    if (chatWindow) {
                        chatWindow.classList.remove('active');
                    }
                    // Scroll to contact section
                    const contactSection = document.getElementById('contact');
                    if (contactSection) {
                        contactSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                });
            }
        }

        chatBody.scrollTop = chatBody.scrollHeight;
    }

    async function handleChat() {
        const msg = chatInput.value.trim();
        if (!msg) return;
        addMessage(msg, 'user-message');
        chatInput.value = '';

        // API Call
        try {
            const resp = await fetch('/api/chatbot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({ message: msg })
            });
            const data = await resp.json();
            setTimeout(() => addMessage(data.reply, 'bot-message', data.cta), 600);
        } catch (e) {
            addMessage("I'm having trouble connecting. Please try again or use our contact form!", 'bot-message');
        }
    }

    if (sendMessage) sendMessage.onclick = handleChat;
    if (chatInput) chatInput.onkeypress = (e) => { if (e.key === 'Enter') handleChat(); };

    /* --- Notifications UI --- */
    window.markRead = function (id, el) {
        fetch(`/notifications/read/${id}`).then(r => r.json()).then(data => {
            if (data.status === 'success') {
                el.classList.remove('unread');
                const badge = document.querySelector('.notif-badge');
                if (badge) {
                    let count = parseInt(badge.innerText) - 1;
                    if (count <= 0) badge.remove();
                    else badge.innerText = count;
                }
                // Redirect if link exists
                const link = el.getAttribute('data-link');
                if (link && link !== "#" && link !== "None") {
                    window.location.href = link;
                }
            }
        });
    };

    const notifBell = document.getElementById('notifBell');
    const notifDropdown = document.getElementById('notifDropdown');
    if (notifBell) {
        notifBell.onclick = (e) => {
            e.stopPropagation();
            notifDropdown.classList.toggle('active');
        };
    }
    document.addEventListener('click', () => {
        if (notifDropdown) notifDropdown.classList.remove('active');
    });

    /* --- Global Inactivity (Updated) --- */
    let idleTime = 0;
    const idleLimit = 5; // minutes
    if (document.body.dataset.authenticated === "true") {
        document.onmousemove = () => idleTime = 0;
        document.onkeypress = () => idleTime = 0;
        setInterval(() => {
            idleTime++;
            if (idleTime >= idleLimit) window.location.href = '/logout?reason=timeout';
        }, 60000);
    }

    /* --- Portfolio Modal Logic --- */
    const modal = document.getElementById('portfolioPreviewModal');
    const modalMedia = document.getElementById('modalMedia');
    const modalTitle = document.getElementById('modalTitle');
    const modalCategory = document.getElementById('modalCategory');
    const portfolioItems = document.querySelectorAll('.portfolio-item');

    window.closePreviewModal = function () {
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    };

    if (modal) {
        // Use event delegation for dynamically loaded portfolio items
        document.body.addEventListener('click', (e) => {
            const item = e.target.closest('.portfolio-item');
            if (item) {
                if (e.target.tagName === 'A' || e.target.closest('a')) return;

                const img = item.querySelector('img');
                const title = item.querySelector('h3') ? item.querySelector('h3').innerText : 'Project';
                const category = item.getAttribute('data-category') || 'Design';
                const link = item.getAttribute('data-link') || '';

                if (modalTitle) modalTitle.innerText = title;
                if (modalCategory) modalCategory.innerText = category;
                if (modalMedia) {
                    modalMedia.innerHTML = '';

                    // Video Detection Logic
                    let videoEmbed = null;
                    if (link.includes('youtube.com/watch?v=')) {
                        const vid = link.split('v=')[1].split('&')[0];
                        videoEmbed = `https://www.youtube.com/embed/${vid}`;
                    } else if (link.includes('youtu.be/')) {
                        const vid = link.split('be/')[1].split('?')[0];
                        videoEmbed = `https://www.youtube.com/embed/${vid}`;
                    } else if (link.includes('vimeo.com/')) {
                        const vid = link.split('vimeo.com/')[1].split('?')[0];
                        videoEmbed = `https://player.vimeo.com/video/${vid}`;
                    }

                    if (videoEmbed) {
                        modalMedia.innerHTML = `<iframe src="${videoEmbed}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="width:100%; height:100%; aspect-ratio:16/9;"></iframe>`;
                    } else if (img) {
                        const newImg = document.createElement('img');
                        newImg.src = img.src;
                        newImg.alt = title;
                        modalMedia.appendChild(newImg);
                    } else {
                        modalMedia.innerHTML = '<p style="color:#fff;">Preview not available</p>';
                    }
                }

                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) window.closePreviewModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) window.closePreviewModal();
        });
    }

    // --- Centralized Backend API ---
    const SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxK3iID6qQrBC9CDmEMN67hBMk8OwkwsKR_EznsS7hja27u44koUrwYqsKaykMjDreguA/exec';

    // --- Dynamic Portfolio Loading via Google Sheets ---
    const dynamicPortfolioGrid = document.getElementById('portfolioGrid');
    if (dynamicPortfolioGrid) {
        fetch(SCRIPT_URL + '?action=get_portfolio')
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    console.error("Sheets Error:", data.error);
                    return;
                }

                // Sort array assuming there is a Date column
                data.sort((a, b) => new Date(b.Date) - new Date(a.Date));
                dynamicPortfolioGrid.innerHTML = ''; // Clear fallback items

                data.forEach(item => {
                    if (!item.Title) return; // Skip empty rows

                    // Match the filter classes (web, logo, etc.) based on Categories like 'Web Design'
                    let categoryClass = 'other';
                    if (item.Category) {
                        const lowCat = item.Category.toLowerCase();
                        if (lowCat.includes('web')) categoryClass = 'web';
                        else if (lowCat.includes('logo')) categoryClass = 'logo';
                        else if (lowCat.includes('thumb')) categoryClass = 'thumbnails';
                        else if (lowCat.includes('post')) categoryClass = 'posts';
                        else if (lowCat.includes('invit')) categoryClass = 'invitations';
                    }

                    const defaultImg = `<div class="placeholder-img" style="background:var(--primary); color:white; display:flex; align-items:center; justify-content:center; height:100%; aspect-ratio:16/9; font-weight:bold;">${item.Category || 'PROJECT'}</div>`;
                    const imgHtml = item.ImageURL ? `<img src="${item.ImageURL}" alt="${item.Title}" style="width:100%; height:100%; object-fit:cover;">` : defaultImg;

                    const html = `
                        <div class="portfolio-item card" data-category="${categoryClass}" data-link="${item.ProjectLink || '#'}">
                            <div class="portfolio-img">
                                ${imgHtml}
                                <span class="sample-badge">Click to View</span>
                            </div>
                            <div class="portfolio-overlay">
                                <h3>${item.Title}</h3>
                                <p><span style="color: #e0e0e0;">${item.Category || 'Project'}</span></p>
                                <p style="font-size: 0.9em; margin-top:5px;">${item.Description || ''}</p>
                            </div>
                        </div>
                    `;
                    dynamicPortfolioGrid.insertAdjacentHTML('beforeend', html);
                });
            })
            .catch(err => {
                console.error("Error loading portfolio data from sheets:", err);
            });
    }

    // --- Connect Contact Form to Google Sheets ---
    const contactForm = document.getElementById('contactForm');
    const formSuccessMessage = document.getElementById('formSuccessMessage');

    if (contactForm) {

        const phoneInput = contactForm.querySelector('input[name="phone"]');
        const phoneError = document.getElementById('phoneError');
        // --- Real-Time Phone Validation ---
        if (phoneInput) {
            phoneInput.addEventListener('input', (e) => {
                // Remove non-numeric characters immediately
                let val = e.target.value.replace(/\D/g, '');
                // Max length 10
                if (val.length > 10) val = val.slice(0, 10);
                e.target.value = val;

                // Show inline error if typing but less than 10 digits
                if (val.length > 0 && val.length < 10) {
                    if (phoneError) phoneError.style.display = 'block';
                } else {
                    if (phoneError) phoneError.style.display = 'none';
                }
            });
        }

        contactForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (phoneInput && phoneInput.value.length !== 10) {
                if (phoneError) phoneError.style.display = 'block';
                return;
            }


            const submitBtn = document.getElementById('submitInquiryBtn');
            const originalText = submitBtn.innerText;
            submitBtn.innerText = 'Submitting...';
            submitBtn.disabled = true;

            const formData = new FormData(contactForm);
            const data = Object.fromEntries(formData.entries());
            data.action = 'submit';

            // Format Timestamp as YYYY-MM-DD HH:MM:SS
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            data.timestamp = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

            try {
                // Standard form submission to Google Script No-CORS
                await fetch('https://script.google.com/macros/s/AKfycbxK3iID6qQrBC9CDmEMN67hBMk8OwkwsKR_EznsS7hja27u44koUrwYqsKaykMjDreguA/exec', {
                    method: 'POST',
                    mode: 'no-cors',
                    cache: 'no-cache',
                    headers: {
                        'Content-Type': 'text/plain;charset=utf-8',
                    },
                    body: JSON.stringify(data)
                });

                // Assume success since no-cors hides response
                contactForm.reset();
                if (formSuccessMessage) {
                    formSuccessMessage.style.display = 'block';
                    setTimeout(() => { formSuccessMessage.style.display = 'none'; }, 10000);
                }
            } catch (error) {
                console.error('Error submitting form', error);
                alert("Network error. Please try again or check your internet connection.");
            } finally {
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }
});

/* --- Dashboard Tab Logic (Global) --- */
window.openTab = function (evt, tabName) {
    try {
        console.log('openTab called with:', tabName);

        // Hide all tab content
        const tabContent = document.getElementsByClassName("tab-content");
        for (let i = 0; i < tabContent.length; i++) {
            tabContent[i].classList.remove("active");
            tabContent[i].style.display = "none";
        }

        // Deactivate all tab links
        const tabLinks = document.getElementsByClassName("tab-link");
        for (let i = 0; i < tabLinks.length; i++) {
            tabLinks[i].classList.remove("active");
        }

        // Show the specific tab content
        const targetContent = document.getElementById(tabName);
        if (targetContent) {
            targetContent.classList.add("active");
            targetContent.style.display = "block";
        } else {
            console.error('Tab content not found:', tabName);
            return;
        }

        // Activate the clicked button
        if (evt && evt.currentTarget) {
            evt.currentTarget.classList.add("active");
        } else {
            // Try to find the button that corresponds to this tab
            const btn = document.querySelector(`.tab-link[onclick*="'${tabName}'"]`);
            if (btn) btn.classList.add("active");
        }

        // Persist State
        localStorage.setItem('activeAdminTab', tabName);

        // Update URL hash without scrolling
        if (history.pushState) {
            history.pushState(null, null, '#' + tabName);
        } else {
            location.hash = '#' + tabName;
        }

    } catch (error) {
        console.error('Error in openTab:', error);
    }
};

/* --- Google Auth Callbacks --- */
window.handleCredentialResponse = async function (response) {
    console.log("Encoded JWT ID token: " + response.credential);

    // Decode JWT logic without external library
    const base64Url = response.credential.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    const parsedData = JSON.parse(jsonPayload);
    const userEmail = parsedData.email;
    const userName = parsedData.name;

    console.log("Logged In User:", userName, userEmail);

    try {
        const fetchUrl = `${SCRIPT_URL}?action=login&email=${encodeURIComponent(userEmail)}&name=${encodeURIComponent(userName)}`;
        const fetchRes = await fetch(fetchUrl);
        const result = await fetchRes.json();
        
        // Hide all main sections
        document.querySelectorAll('main > section').forEach(sec => sec.style.display = 'none');
        
        // Securely validate role from Google Sheets
        if (result.role && result.role.toLowerCase() === 'admin') {
            document.body.dataset.authenticated = "true";
            document.getElementById('navLoginBtn').innerText = "Dashboard";
            document.getElementById('googleAuthWrapper').style.display = 'none';
            alert("Admin Access Granted! Admin Dashboard Unlocked.");
            document.getElementById('admin-dashboard').style.display = 'block';
            window.scrollTo(0, 0);
        } else {
            // User role or any other role logic
            document.getElementById('navLoginBtn').innerText = "Dashboard";
            document.getElementById('googleAuthWrapper').style.display = 'none';
            document.getElementById('coming-soon').style.display = 'block';
            window.scrollTo(0, 0);
        }

    } catch (err) {
        console.error('Role check failed:', err);
    }
};

window.onload = function () {
    const navLoginBtn = document.getElementById('navLoginBtn');
    if (navLoginBtn) {
        navLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if(document.body.dataset.authenticated === "true") {
                document.querySelectorAll('main > section').forEach(sec => sec.style.display = 'none');
                document.getElementById('admin-dashboard').style.display = 'block';
                window.scrollTo(0, 0);
            } else if (navLoginBtn.innerText === "Dashboard") {
                document.querySelectorAll('main > section').forEach(sec => sec.style.display = 'none');
                document.getElementById('coming-soon').style.display = 'block';
                window.scrollTo(0, 0);
            }
        });
    }
    
    // Check initial hash route
    if(window.location.hash === '#home' || !window.location.hash) {
         document.querySelectorAll('main > section.main-section').forEach(sec => sec.style.display = 'none');
         document.getElementById('home').style.display = 'flex';
         document.getElementById('about').style.display = 'block';
         document.getElementById('services').style.display = 'block';
         document.getElementById('portfolio').style.display = 'block';
         document.getElementById('contact').style.display = 'block';
    }
};

window.handleTabState = function () {
    try {
        console.log('handleTabState called, hash:', window.location.hash);

        let activeTab = 'tab-stats'; // Default
        const hash = window.location.hash;

        // Check if we are in admin mode or client mode
        if (!document.getElementById('tab-stats')) {
            activeTab = 'tab-pipeline';
        }

        if (hash && hash.startsWith('#tab-')) {
            activeTab = hash.substring(1);
        } else if (hash && hash.startsWith('#order-')) {
            activeTab = document.getElementById('tab-orders') ? 'tab-orders' : 'tab-pipeline';
            setTimeout(() => window.scrollToElement(hash), 500);
        } else if (hash && hash.startsWith('#ticket-')) {
            activeTab = 'tab-tickets';
            setTimeout(() => window.scrollToElement(hash), 500);
        } else {
            const stored = localStorage.getItem('activeAdminTab');
            if (stored && document.getElementById(stored)) {
                activeTab = stored;
            }
        }

        console.log('Restoring tab:', activeTab);
        window.openTab(null, activeTab);

    } catch (error) {
        console.error('Error in handleTabState:', error);
    }
};

window.scrollToElement = function (selector) {
    const el = document.querySelector(selector);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('highlight-flash');
        setTimeout(() => el.classList.remove('highlight-flash'), 6000);
    }
};

window.toggleOutputField = function (id, val) {
    const group = document.getElementById('output_group_' + id);
    if (group) group.style.display = (val === 'Completed') ? 'block' : 'none';
};

// Auto-run handleTabState on load if not handled inline
// Auto-run handleTabState on load if not handled inline
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.dashboard-container')) {
        setTimeout(() => {
            if (!document.querySelector('.tab-content.active')) {
                window.handleTabState();
            }
        }, 200);
    }
});

/* --- User Filter Logic --- */
window.filterUsers = function () {
    const input = document.getElementById('userSearchInput');
    const filter = input.value.toUpperCase();
    const tableBody = document.getElementById('userTableBody');
    if (!tableBody) return;
    const rows = tableBody.getElementsByClassName('user-row');

    for (let i = 0; i < rows.length; i++) {
        let textLoaded = "";
        const cols = rows[i].getElementsByTagName("td");
        for (let j = 0; j < cols.length; j++) {
            if (cols[j]) {
                textLoaded += cols[j].textContent || cols[j].innerText;
            }
        }

        if (textLoaded.toUpperCase().indexOf(filter) > -1) {
            rows[i].style.display = "";
        } else {
            rows[i].style.display = "none";
        }
    }
};
