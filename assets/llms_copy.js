/**
 * Per-page "Copy llms.txt URL" button handler.
 *
 * Wires up every `.llms-copy-button` so that clicking it copies
 * `<origin>/<page-path>/llms.txt` to the clipboard. Paste the result
 * into ChatGPT, Claude, or any LLM to share the page's prose docs.
 *
 * The `llms.toon` and `page.json` button handlers were removed in v0.5.0
 * — `dash-improve-my-llms` 2.0 dropped both endpoints.
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log('LLM copy-button handler loaded');

    async function copyToClipboard(text) {
        // Modern Clipboard API path
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (err) {
                console.warn('Clipboard API failed, trying fallback:', err);
            }
        }

        // Fallback for non-secure contexts (HTTP / older browsers)
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        try {
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);
            return success;
        } catch (err) {
            console.error('execCommand failed:', err);
            document.body.removeChild(textarea);
            return false;
        }
    }

    function cleanPagePath() {
        const p = window.location.pathname;
        return p.endsWith('/') ? p.slice(0, -1) : p;
    }

    /**
     * The signed-in visitor's agent key, or "" when anonymous.
     *
     * These URLs get pasted into Claude or ChatGPT, which fetch them with no
     * cookie — so a gated document needs its authority in the URL or the
     * agent gets the gate page instead of the docs. /api/agent-key
     * (lib/agent_key.py) returns the key bound to the current Clerk session
     * (204 when signed out), which is why the key is never embedded in the
     * page HTML: nothing can cache it and hand it to the next visitor.
     *
     * Fetched lazily on the first click and remembered for the page view —
     * every call is a hub round trip, so never fetch on render. Any failure
     * falls through to the plain URL: copying something that works for
     * public pages beats copying nothing.
     */
    let agentKeyPromise = null;

    function getAgentKey() {
        if (agentKeyPromise === null) {
            agentKeyPromise = fetch('/api/agent-key', { credentials: 'same-origin' })
                .then((r) => (r.status === 200 ? r.json() : null))
                .then((data) => (data && data.key) || '')
                .catch(() => '');
        }
        return agentKeyPromise;
    }

    function flashButton(button, originalText, message, color) {
        button.textContent = message;
        button.style.color = color;
        setTimeout(() => {
            button.textContent = originalText;
            button.style.color = '';
        }, 2000);
    }

    function setupCopyButtons() {
        const byClass = document.querySelectorAll('.llms-copy-button');
        const byId = document.querySelectorAll('[id^="llm-copy-button-"]');
        const all = new Set([...byClass, ...byId]);

        all.forEach((button) => {
            if (button.dataset.copySetup) return;
            button.dataset.copySetup = 'true';

            button.addEventListener('click', async function (e) {
                e.preventDefault();
                e.stopPropagation();

                try {
                    // Carry the agent key when signed in so the pasted link
                    // works in an assistant that has no session.
                    const agentKey = await getAgentKey();
                    const url = `${window.location.origin}${cleanPagePath()}/llms.txt`
                        + (agentKey ? `?key=${encodeURIComponent(agentKey)}` : '');
                    const ok = await copyToClipboard(url);
                    const original = button.textContent;
                    if (ok) {
                        flashButton(button, original, '✓ Copied!', 'var(--mantine-color-teal-6)');
                        console.log('Copied to clipboard:', url);
                    } else {
                        throw new Error('All copy methods failed');
                    }
                } catch (err) {
                    console.error('Failed to copy:', err);
                    const original = button.textContent;
                    flashButton(button, original, '❌ Failed', 'var(--mantine-color-red-6)');
                }
            });
        });
    }

    // Initial pass
    setupCopyButtons();

    // Dash sometimes finishes rendering after DOMContentLoaded; re-bind
    // a couple of times on a delay to catch late-arriving nodes.
    setTimeout(setupCopyButtons, 500);
    setTimeout(setupCopyButtons, 1000);
    setTimeout(setupCopyButtons, 2000);

    // Re-run on any page change
    const observer = new MutationObserver(() => {
        clearTimeout(window.llmsCopyTimeout);
        window.llmsCopyTimeout = setTimeout(setupCopyButtons, 100);
    });
    const target = document.getElementById('_pages_content') || document.body;
    observer.observe(target, { childList: true, subtree: true });

    console.log('LLM copy-button observer active');
});
