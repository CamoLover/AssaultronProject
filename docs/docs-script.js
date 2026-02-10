// Theme toggle functionality
const themeToggle = document.getElementById('theme-toggle');
const html = document.documentElement;
const themeIcon = themeToggle.querySelector('i');

// Check for saved theme preference or default to light mode
const currentTheme = localStorage.getItem('theme') || 'light';
if (currentTheme === 'dark') {
    html.classList.add('dark');
    themeIcon.classList.remove('fa-moon');
    themeIcon.classList.add('fa-sun');
}

// Theme toggle event listener
themeToggle.addEventListener('click', () => {
    html.classList.toggle('dark');

    if (html.classList.contains('dark')) {
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
        localStorage.setItem('theme', 'dark');
    } else {
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
        localStorage.setItem('theme', 'light');
    }
});

// Markdown loading functionality
const loadingDiv = document.getElementById('loading');
const errorDiv = document.getElementById('error');
const contentDiv = document.getElementById('markdown-content');

// Configure marked options
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: true,
    mangle: false
});

// Function to load markdown file
async function loadDoc(filename) {
    // Show loading state
    loadingDiv.classList.remove('hidden');
    errorDiv.classList.add('hidden');
    contentDiv.classList.add('hidden');

    // Update active link
    document.querySelectorAll('.doc-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.closest('.doc-link').classList.add('active');

    try {
        // Fetch markdown file
        const response = await fetch(`markdown/${filename}`);

        if (!response.ok) {
            throw new Error('Failed to fetch documentation');
        }

        const markdownText = await response.text();

        // Convert markdown to HTML
        const htmlContent = marked.parse(markdownText);

        // Display content
        contentDiv.innerHTML = htmlContent;
        loadingDiv.classList.add('hidden');
        contentDiv.classList.remove('hidden');

        // Scroll to top of content
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Add copy buttons to code blocks
        addCopyButtons();

        // Process internal links
        processInternalLinks();

    } catch (error) {
        console.error('Error loading documentation:', error);
        loadingDiv.classList.add('hidden');
        errorDiv.classList.remove('hidden');
    }
}

// Add copy buttons to code blocks
function addCopyButtons() {
    const codeBlocks = contentDiv.querySelectorAll('pre');

    codeBlocks.forEach(block => {
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';

        // Create copy button
        const copyButton = document.createElement('button');
        copyButton.innerHTML = '<i class="fas fa-copy"></i>';
        copyButton.className = 'absolute top-2 right-2 px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm transition-colors';
        copyButton.title = 'Copy code';

        copyButton.addEventListener('click', async () => {
            const code = block.querySelector('code').textContent;
            try {
                await navigator.clipboard.writeText(code);
                copyButton.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(() => {
                    copyButton.innerHTML = '<i class="fas fa-copy"></i>';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy:', err);
            }
        });

        // Wrap the code block
        block.parentNode.insertBefore(wrapper, block);
        wrapper.appendChild(block);
        wrapper.appendChild(copyButton);
    });
}

// Process internal markdown links
function processInternalLinks() {
    const links = contentDiv.querySelectorAll('a');

    links.forEach(link => {
        const href = link.getAttribute('href');

        // Check if it's an internal anchor link
        if (href && href.startsWith('#')) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = href.substring(1);
                const target = document.getElementById(targetId);

                if (target) {
                    const offset = 100; // Account for fixed header
                    const targetPosition = target.offsetTop - offset;
                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        }
    });
}

// Load default documentation on page load
window.addEventListener('DOMContentLoaded', () => {
    // Load architecture by default
    const defaultDoc = document.querySelector('.doc-link');
    if (defaultDoc) {
        defaultDoc.click();
    }
});

// Add table of contents generation
function generateTOC() {
    const headings = contentDiv.querySelectorAll('h2, h3');

    if (headings.length === 0) return;

    const toc = document.createElement('div');
    toc.className = 'bg-gray-100 dark:bg-slate-900 p-6 rounded-lg mb-8 border border-gray-200 dark:border-slate-700';

    // Create collapsible header
    const tocHeader = document.createElement('div');
    tocHeader.className = 'flex justify-between items-center mb-4 cursor-pointer';
    tocHeader.onclick = toggleTOC;
    tocHeader.innerHTML = `
        <h3 class="text-xl font-bold gradient-text">Table of Contents</h3>
        <button class="p-2 rounded-lg bg-gray-200 dark:bg-slate-800 hover:bg-gray-300 dark:hover:bg-slate-700 transition-colors">
            <i id="toc-icon" class="fas fa-chevron-up text-red-500"></i>
        </button>
    `;

    const tocContent = document.createElement('ul');
    tocContent.id = 'toc-content';
    tocContent.className = 'space-y-2';

    headings.forEach((heading, index) => {
        // Add ID to heading if it doesn't have one
        if (!heading.id) {
            heading.id = `heading-${index}`;
        }

        const li = document.createElement('li');
        const link = document.createElement('a');
        link.href = `#${heading.id}`;
        link.textContent = heading.textContent;
        link.className = 'text-red-500 hover:text-red-600 dark:hover:text-red-400 transition-colors';

        if (heading.tagName === 'H3') {
            li.className = 'ml-4';
        }

        link.addEventListener('click', (e) => {
            e.preventDefault();
            const offset = 100;
            const targetPosition = heading.offsetTop - offset;
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        });

        li.appendChild(link);
        tocContent.appendChild(li);
    });

    toc.appendChild(tocHeader);
    toc.appendChild(tocContent);

    // Insert TOC after the first h1
    const firstH1 = contentDiv.querySelector('h1');
    if (firstH1) {
        firstH1.after(toc);
    } else {
        contentDiv.prepend(toc);
    }

    // Restore TOC state from localStorage
    const tocCollapsed = localStorage.getItem('toc-collapsed');
    if (tocCollapsed === 'true') {
        tocContent.classList.add('hidden');
        const tocIcon = document.getElementById('toc-icon');
        if (tocIcon) {
            tocIcon.classList.remove('fa-chevron-up');
            tocIcon.classList.add('fa-chevron-down');
        }
    }
}

// Modify loadDoc to generate TOC
const originalLoadDoc = loadDoc;
loadDoc = async function(filename) {
    await originalLoadDoc.call(this, filename);
    generateTOC();
};

// Toggle TOC visibility
function toggleTOC() {
    const tocContent = document.getElementById('toc-content');
    const tocIcon = document.getElementById('toc-icon');

    if (tocContent && tocIcon) {
        tocContent.classList.toggle('hidden');
        tocIcon.classList.toggle('fa-chevron-up');
        tocIcon.classList.toggle('fa-chevron-down');

        // Save state to localStorage
        const isCollapsed = tocContent.classList.contains('hidden');
        localStorage.setItem('toc-collapsed', isCollapsed ? 'true' : 'false');
    }
}
