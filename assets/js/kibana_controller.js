(async () => {
    // Kibana auto-login controller
    // Similar to PNETLab auto-login but adapted for Kibana authentication

    try {
        // 1) First, try to get the current Kibana version by making a request to any Kibana endpoint
        let kbnVersion = '7.16.1'; // Default fallback version
        
        try {
            const versionResponse = await fetch('/kibana/', { 
                method: 'GET', 
                credentials: 'include' 
            });
            
            // Try to extract kbn-version from response headers
            const responseKbnVersion = versionResponse.headers.get('kbn-name');
            if (responseKbnVersion) {
                // If we can get version info, use it, otherwise stick with default
                console.log('Kibana detected:', responseKbnVersion);
            }
        } catch (e) {
            console.log('Could not detect Kibana version, using default:', kbnVersion);
        }

        // 2) Perform the login request to Kibana
        const loginResponse = await fetch('/internal/security/login', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': '*/*',
                'X-Requested-With': 'XMLHttpRequest',
                'kbn-version': kbnVersion,
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            },
            body: JSON.stringify({
                providerType: 'basic',
                providerName: 'basic', 
                currentURL: window.location.origin + '/kibana/',
                params: {
                    username: 'elastic',
                    password: 'MyPw123'
                }
            })
        });

        const loginData = await loginResponse.json().catch(() => ({}));
        
        // 3) After successful login, reload the iframe with Kibana dashboard
        const iframe = document.getElementById('kibanaFrame');
        if (iframe) {
            // Add timestamp to force reload and go directly to /kibana
            iframe.src = '/kibana/?t=' + Date.now();
        }

        console.log('Kibana auto-login completed');

    } catch (error) {
        console.error('Kibana auto-login failed:', error);
        
        // Fallback: just reload the iframe in case of any errors
        const iframe = document.getElementById('kibanaFrame');
        if (iframe) {
            iframe.src = '/kibana/?t=' + Date.now();
        }
    }
})();

// Function to setup iframe location control for Kibana (similar to PNETLab)
function setupKibanaIframeLocationControl(iframeElement) {
    iframeElement.addEventListener('load', () => {
        const win = iframeElement.contentWindow;
        const doc = iframeElement.contentDocument;
        
        if (doc && doc.head) {
            // Insert script to control iframe navigation within Kibana context
            const script = doc.createElement('script');
            script.textContent = `
                (function() {
                    const allowedPaths = ['/kibana/', '/app/', '/api/', '/internal/'];
                    
                    function checkPath() {
                        const path = location.pathname;
                        // Allow Kibana-related paths
                        const isAllowed = allowedPaths.some(p => path.startsWith(p)) || path === '/';
                        
                        if (!isAllowed) {
                            // Redirect back to Kibana dashboard if navigated to unauthorized path
                            parent.postMessage({ type: 'kibana-bad-path', path: path }, '*');
                        }
                    }
                    
                    // Patch browser history methods
                    ['pushState', 'replaceState'].forEach(fn => {
                        const orig = history[fn];
                        history[fn] = function() {
                            orig.apply(this, arguments);
                            checkPath();
                        };
                    });
                    
                    // Listen for back/forward navigation
                    window.addEventListener('popstate', checkPath);
                    
                    // Check immediately after load
                    checkPath();
                })();
            `;
            doc.head.appendChild(script);
        }
    });
}

// Enhanced iframe management for Kibana (similar to PNETLab functionality)
$(document).ready(function() {
    let isFullscreen = false;
    let originalIframeStyles = null;
    let originalIframePosition = null;
    
    // Setup location control for the original Kibana iframe
    const originalIframe = document.getElementById('kibanaFrame');
    if (originalIframe) {
        setupKibanaIframeLocationControl(originalIframe);
    }
    
    function expandKibanaIframe() {
        if (isFullscreen) return;
        
        const iframe = $('#kibanaFrame');
        const iframeContainer = $('.iframe-container');
        const contentContainer = $('.columns.is-centered').last();
        const titleContainer = $('.columns.is-centered').first();
        
        originalIframeStyles = {
            height: iframe.css('height'),
            width: iframe.css('width'),
            marginBottom: iframe.css('margin-bottom'),
            borderRadius: iframe.css('border-radius'),
            boxShadow: iframe.css('box-shadow'),
            border: iframe.css('border')
        };
        
        // Save original position for restoration
        originalIframePosition = {
            parent: iframeContainer.parent(),
            nextSibling: iframeContainer.next()
        };
        
        // Safely move container without reloading iframe
        const clonedContainer = iframeContainer.clone(true);
        iframeContainer.replaceWith(clonedContainer);
        clonedContainer.appendTo('body');
        clonedContainer.addClass('iframe-moved-up');
        
        // Update element references after cloning
        const newIframe = clonedContainer.find('#kibanaFrame');
        const newExpandBtn = clonedContainer.find('#expandIframeBtn');
        
        // Re-setup location control for the cloned iframe
        setupKibanaIframeLocationControl(newIframe[0]);
        
        newIframe.addClass('iframe-fullscreen');
        newIframe.css({
            'height': '100vh',
            'width': '100vw',
            'margin-bottom': '0',
            'border-radius': '0',
            'box-shadow': 'none',
            'border': 'none'
        });
        
        $('#iframeOverlay').fadeIn(300);
        $('#collapseIframeBtn').fadeIn(300);
        newExpandBtn.fadeOut(200);
        
        contentContainer.addClass('content-collapsed');
        titleContainer.addClass('content-collapsed');
        
        $('body, html').addClass('iframe-fullscreen-active');
        
        $('html, body').animate({
            scrollTop: iframe.offset().top
        }, 500);
        
        isFullscreen = true;
    }
    
    function collapseKibanaIframe() {
        if (!isFullscreen) return;
        
        const iframeContainer = $('.iframe-container.iframe-moved-up');
        const iframe = iframeContainer.find('#kibanaFrame');
        const contentContainer = $('.columns.is-centered').last();
        const titleContainer = $('.columns.is-centered').first();
        
        iframe.removeClass('iframe-fullscreen');
        
        if (originalIframeStyles) {
            iframe.css({
                'height': originalIframeStyles.height,
                'width': originalIframeStyles.width,
                'margin-bottom': originalIframeStyles.marginBottom,
                'border-radius': originalIframeStyles.borderRadius,
                'box-shadow': originalIframeStyles.boxShadow,
                'border': originalIframeStyles.border
            });
        }
        
        $('#iframeOverlay').fadeOut(300);
        $('#collapseIframeBtn').fadeOut(300);
        
        iframeContainer.removeClass('iframe-moved-up');
        
        // Safely return container to original position
        if (originalIframePosition) {
            iframeContainer.prependTo(originalIframePosition.parent);
        } else {
            iframeContainer.prependTo(contentContainer.find('.column.is-three-quarters'));
        }
        
        // Update expand button reference
        const newExpandBtn = iframeContainer.find('#expandIframeBtn');
        newExpandBtn.fadeIn(200);
        
        // Re-setup location control after return
        const returnedIframe = iframeContainer.find('#kibanaFrame')[0];
        setupKibanaIframeLocationControl(returnedIframe);
        
        contentContainer.removeClass('content-collapsed');
        titleContainer.removeClass('content-collapsed');
        
        $('body, html').removeClass('iframe-fullscreen-active');
        
        $('html, body').animate({
            scrollTop: 0
        }, 500);
        
        isFullscreen = false;
    }
    
    // Event handlers for fullscreen functionality
    $('#expandIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        expandKibanaIframe();
    });
    
    $('#collapseIframeBtn').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        collapseKibanaIframe();
    });
    
    $('#iframeOverlay').on('click', function() {
        collapseKibanaIframe();
    });
    
    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && isFullscreen) {
            collapseKibanaIframe();
        }
    });
    
    $('#kibanaFrame').on('click', function(e) {
        e.stopPropagation();
    });
    
    // Message handler for iframe navigation control
    window.addEventListener('message', e => {
        if (e.data && e.data.type === 'kibana-bad-path') {
            console.log('Kibana iframe navigated to unauthorized path:', e.data.path);
            const currentIframe = $('.iframe-container #kibanaFrame')[0] || document.getElementById('kibanaFrame');
            if (currentIframe && currentIframe.contentWindow) {
                // Redirect back to Kibana dashboard
                currentIframe.contentWindow.location.replace('/kibana/');
            }
        }
    });
});
