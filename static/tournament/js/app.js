/* ===================================================================
   WCL26 Tournament Tracker — Interactivity
   =================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initMobileNav();
    initGroupTabs();
    initMatchTabs();
    initAnimatedCounters();
    initProgressBars();
});

/* --- Mobile Navigation --- */
function initMobileNav() {
    const toggle = document.querySelector('.navbar__toggle');
    const nav = document.querySelector('.navbar__nav');
    if (!toggle || !nav) return;

    toggle.addEventListener('click', () => {
        nav.classList.toggle('navbar__nav--open');
        const isOpen = nav.classList.contains('navbar__nav--open');
        toggle.innerHTML = isOpen ? '✕' : '☰';
        toggle.setAttribute('aria-expanded', isOpen);
    });

    // Close on nav link click
    nav.querySelectorAll('.navbar__link').forEach(link => {
        link.addEventListener('click', () => {
            nav.classList.remove('navbar__nav--open');
            toggle.innerHTML = '☰';
        });
    });
}

/* --- Group Tabs (Group Stage, Super 16, etc.) --- */
function initGroupTabs() {
    const tabContainer = document.getElementById('group-tabs');
    if (!tabContainer) return;

    const tabs = tabContainer.querySelectorAll('.tab-btn[data-tab]');
    if (!tabs.length) return;

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;

            // Update active tab
            tabs.forEach(t => t.classList.remove('tab-btn--active'));
            tab.classList.add('tab-btn--active');

            // Update active panel
            document.querySelectorAll('.tab-panel').forEach(panel => {
                panel.classList.remove('tab-panel--active');
            });
            const targetPanel = document.getElementById(target);
            if (targetPanel) {
                targetPanel.classList.add('tab-panel--active');
                // Re-trigger animations
                targetPanel.querySelectorAll('[class*="fadeIn"]').forEach(el => {
                    el.style.animation = 'none';
                    el.offsetHeight;
                    el.style.animation = '';
                });
            }

            // Update URL without reload
            const url = new URL(window.location);
            url.searchParams.set('group', target.replace('group-', 'Group '));
            window.history.replaceState({}, '', url);
        });
    });
}

/* --- Match Section Tabs (Completed/Upcoming) --- */
function initMatchTabs() {
    const matchTabs = document.querySelectorAll('.match-section-tab[data-match-tab]');
    if (!matchTabs.length) return;

    matchTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const group = tab.closest('.tab-panel') || document;
            const target = tab.dataset.matchTab;

            // Update active match tab within this context
            group.querySelectorAll('.match-section-tab').forEach(t => {
                t.classList.remove('match-section-tab--active');
            });
            tab.classList.add('match-section-tab--active');

            // Show/hide match sections
            group.querySelectorAll('.match-section').forEach(section => {
                section.style.display = 'none';
            });
            const targetSection = group.querySelector(`[data-match-section="${target}"]`);
            if (targetSection) {
                targetSection.style.display = 'block';
            }
        });
    });
}

/* --- Animated Counters --- */
function initAnimatedCounters() {
    const counters = document.querySelectorAll('[data-counter]');
    if (!counters.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => observer.observe(counter));
}

function animateCounter(el) {
    const target = parseInt(el.dataset.counter, 10);
    const duration = 1200;
    const start = performance.now();

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // Ease out cubic
        const current = Math.round(eased * target);
        el.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/* --- Progress Bars --- */
function initProgressBars() {
    const bars = document.querySelectorAll('[data-progress]');
    if (!bars.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = parseFloat(entry.target.dataset.progress);
                entry.target.style.width = `${target}%`;
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    bars.forEach(bar => {
        bar.style.width = '0%';
        observer.observe(bar);
    });
}
