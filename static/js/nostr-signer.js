/**
 * Nostr signing for the admin app: NIP-07 browser extensions and NIP-46
 * signer apps (bunker:// URIs and client-initiated nostrconnect:// pairings).
 *
 * Both transports produce a signed NIP-98 event (kind 27235); the BTC Map API
 * verifies it itself, so nothing here is trusted by the server and no backend
 * change is needed to add a transport.
 *
 * All three transports are offered side by side in one modal, opened from the
 * page's Nostr button. nostr-tools and the QR library are fetched from jsDelivr
 * on demand, so a CDN failure disables only the signer-app paths.
 *
 * A bunker pairing (client secret + bunker:// URL) is kept in localStorage so
 * the next visit is one click. That is a credential at rest: it lets this
 * browser ask the signer for signatures, not sign without the signer.
 */
(function () {
    'use strict';

    var NIP46_CDN = 'https://cdn.jsdelivr.net/npm/nostr-tools@2.25.2/nip46/+esm';
    var PURE_CDN = 'https://cdn.jsdelivr.net/npm/nostr-tools@2.25.2/pure/+esm';
    var NIP19_CDN = 'https://cdn.jsdelivr.net/npm/nostr-tools@2.25.2/nip19/+esm';
    var QR_CDN = 'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js';

    var PAIRING_KEY = 'btcmap_bunker';
    var CLIENT_NAME = 'BTC Map Admin';
    // Relays the signer app listens on while pairing. Amber and nsec.app both
    // accept arbitrary relay lists in the nostrconnect URI.
    var DEFAULT_RELAYS = ['wss://relay.nsec.app', 'wss://relay.damus.io'];
    // NIP-46 permissions this app needs: read the key, sign NIP-98 events.
    var PERMS = ['get_public_key', 'sign_event:27235'];
    // A saved signer has already approved this client, so a connect ack is
    // optional and waiting on it only costs the user time. A first-time
    // bunker URI is different: the connect is the approval prompt, so wait
    // long enough for someone to reach for their phone.
    var SAVED_CONNECT_MS = 3000;
    var PASTE_CONNECT_MS = 12000;
    var PAIR_TIMEOUT_MS = 180000;
    var SIGN_TIMEOUT_MS = 120000;

    // Bootstrap Icons (MIT), inlined so the dialog needs no icon font.
    var ICONS = {
        extension: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="26" height="26" fill="currentColor" aria-hidden="true"><path d="M3.112 3.645A1.5 1.5 0 0 1 4.605 2H7a.5.5 0 0 1 .5.5v.382c0 .696-.497 1.182-.872 1.469a.5.5 0 0 0-.115.118l-.012.025L6.5 4.5v.003l.003.01q.005.015.036.053a.9.9 0 0 0 .27.194C7.09 4.9 7.51 5 8 5c.492 0 .912-.1 1.19-.24a.9.9 0 0 0 .271-.194.2.2 0 0 0 .039-.063v-.009l-.012-.025a.5.5 0 0 0-.115-.118c-.375-.287-.872-.773-.872-1.469V2.5A.5.5 0 0 1 9 2h2.395a1.5 1.5 0 0 1 1.493 1.645L12.645 6.5h.237c.195 0 .42-.147.675-.48.21-.274.528-.52.943-.52.568 0 .947.447 1.154.862C15.877 6.807 16 7.387 16 8s-.123 1.193-.346 1.638c-.207.415-.586.862-1.154.862-.415 0-.733-.246-.943-.52-.255-.333-.48-.48-.675-.48h-.237l.243 2.855A1.5 1.5 0 0 1 11.395 14H9a.5.5 0 0 1-.5-.5v-.382c0-.696.497-1.182.872-1.469a.5.5 0 0 0 .115-.118l.012-.025.001-.006v-.003a.2.2 0 0 0-.039-.064.9.9 0 0 0-.27-.193C8.91 11.1 8.49 11 8 11s-.912.1-1.19.24a.9.9 0 0 0-.271.194.2.2 0 0 0-.039.063v.003l.001.006.012.025c.016.027.05.068.115.118.375.287.872.773.872 1.469v.382a.5.5 0 0 1-.5.5H4.605a1.5 1.5 0 0 1-1.493-1.645L3.356 9.5h-.238c-.195 0-.42.147-.675.48-.21.274-.528.52-.943.52-.568 0-.947-.447-1.154-.862C.123 9.193 0 8.613 0 8s.123-1.193.346-1.638C.553 5.947.932 5.5 1.5 5.5c.415 0 .733.246.943.52.255.333.48.48.675.48h.238zM4.605 3a.5.5 0 0 0-.498.55l.001.007.29 3.4A.5.5 0 0 1 3.9 7.5h-.782c-.696 0-1.182-.497-1.469-.872a.5.5 0 0 0-.118-.115l-.025-.012L1.5 6.5h-.003a.2.2 0 0 0-.064.039.9.9 0 0 0-.193.27C1.1 7.09 1 7.51 1 8s.1.912.24 1.19c.07.14.14.225.194.271a.2.2 0 0 0 .063.039H1.5l.006-.001.025-.012a.5.5 0 0 0 .118-.115c.287-.375.773-.872 1.469-.872H3.9a.5.5 0 0 1 .498.542l-.29 3.408a.5.5 0 0 0 .497.55h1.878c-.048-.166-.195-.352-.463-.557-.274-.21-.52-.528-.52-.943 0-.568.447-.947.862-1.154C6.807 10.123 7.387 10 8 10s1.193.123 1.638.346c.415.207.862.586.862 1.154 0 .415-.246.733-.52.943-.268.205-.415.39-.463.557h1.878a.5.5 0 0 0 .498-.55l-.001-.007-.29-3.4A.5.5 0 0 1 12.1 8.5h.782c.696 0 1.182.497 1.469.872.05.065.091.099.118.115l.025.012.006.001h.003a.2.2 0 0 0 .064-.039.9.9 0 0 0 .193-.27c.14-.28.24-.7.24-1.191s-.1-.912-.24-1.19a.9.9 0 0 0-.194-.271.2.2 0 0 0-.063-.039H14.5l-.006.001-.025.012a.5.5 0 0 0-.118.115c-.287.375-.773.872-1.469.872H12.1a.5.5 0 0 1-.498-.543l.29-3.407a.5.5 0 0 0-.497-.55H9.517c.048.166.195.352.463.557.274.21.52.528.52.943 0 .568-.447.947-.862 1.154C9.193 5.877 8.613 6 8 6s-1.193-.123-1.638-.346C5.947 5.447 5.5 5.068 5.5 4.5c0-.415.246-.733.52-.943.268-.205.415-.39.463-.557z"/></svg>',
        signer: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="26" height="26" fill="currentColor" aria-hidden="true"><path d="M11 1a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1zM5 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2z"/><path d="M8 14a1 1 0 1 0 0-2 1 1 0 0 0 0 2"/></svg>',
        qr: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="26" height="26" fill="currentColor" aria-hidden="true"><path d="M2 2h2v2H2z"/><path d="M6 0v6H0V0zM5 1H1v4h4zM4 12H2v2h2z"/><path d="M6 10v6H0v-6zm-5 1v4h4v-4zm11-9h2v2h-2z"/><path d="M10 0v6h6V0zm5 1v4h-4V1zM8 1V0h1v2H8v2H7V1zm0 5V4h1v2zM6 8V7h1V6h1v2h1V7h5v1h-4v1H7V8zm0 0v1H2V8H1v1H0V7h3v1zm10 1h-1V7h1zm-1 0h-1v2h2v-1h-1zm-4 0h2v1h-1v1h-1zm2 3v-1h-1v1h-1v1H9v1h3v-2zm0 0h3v1h-2v1h-1zm-4-1v1h1v-2H7v1z"/><path d="M7 12h1v3h4v1H7zm9 2v2h-3v-1h2v-1z"/></svg>'
    };

    var nip46Promise = null;
    var purePromise = null;
    var nip19Promise = null;
    var qrPromise = null;

    function loadNip46(inject) {
        if (inject && inject.nip46) return Promise.resolve(inject.nip46);
        if (!nip46Promise) nip46Promise = import(NIP46_CDN);
        return nip46Promise;
    }

    function loadPure(inject) {
        if (inject && inject.pure) return Promise.resolve(inject.pure);
        if (!purePromise) purePromise = import(PURE_CDN);
        return purePromise;
    }

    function loadQr(inject) {
        if (inject && inject.qr) return Promise.resolve(inject.qr);
        if (window.QRCode) return Promise.resolve(window.QRCode);
        if (!qrPromise) {
            qrPromise = new Promise(function (resolve, reject) {
                var script = document.createElement('script');
                script.src = QR_CDN;
                script.onload = function () {
                    window.QRCode ? resolve(window.QRCode) : reject(new Error('QR library did not load'));
                };
                script.onerror = function () { reject(new Error('Could not load the QR library')); };
                document.head.appendChild(script);
            });
        }
        return qrPromise;
    }

    function npubFor(pubkey, inject) {
        if (!nip19Promise && !(inject && inject.nip19)) {
            nip19Promise = import(NIP19_CDN);
        }
        return (inject && inject.nip19 ? Promise.resolve(inject.nip19) : nip19Promise)
            .then(function (nip19) { return nip19.npubEncode(pubkey); })
            .catch(function () { return null; });
    }

    function bytesToHex(bytes) {
        return Array.prototype.map.call(bytes, function (b) {
            return b.toString(16).padStart(2, '0');
        }).join('');
    }

    function hexToBytes(hex) {
        var out = new Uint8Array(hex.length / 2);
        for (var i = 0; i < out.length; i += 1) {
            out[i] = parseInt(hex.substr(i * 2, 2), 16);
        }
        return out;
    }

    /**
     * NIP-46 connect is optional in practice. Some signers (Opal) never answer
     * a connect on an already-paired session - they act on the request itself -
     * so a silent connect must not block. An explicit error still fails.
     */
    async function connectQuietly(signer, metadata, waitMs) {
        var marker = 'connect was not acknowledged';
        try {
            await withTimeout(signer.connect(metadata), waitMs, marker);
        } catch (error) {
            if (!error || error.message !== marker) throw error;
        }
    }

    function withTimeout(promise, ms, message) {
        return new Promise(function (resolve, reject) {
            var timer = setTimeout(function () { reject(new Error(message)); }, ms);
            promise.then(
                function (value) { clearTimeout(timer); resolve(value); },
                function (error) { clearTimeout(timer); reject(error); }
            );
        });
    }

    /**
     * Build the NIP-98 template at signing time. The API only accepts a
     * created_at within +/-60s, so this must never be built when a pairing
     * starts - connecting a signer can take minutes.
     */
    function nip98Template(url, method) {
        return {
            kind: 27235,
            created_at: Math.floor(Date.now() / 1000),
            tags: [['u', url], ['method', method]],
            content: ''
        };
    }

    function clientMetadata() {
        return { name: CLIENT_NAME, url: window.location.origin };
    }

    function isExtensionAvailable() {
        return typeof window.nostr !== 'undefined' && window.nostr !== null;
    }

    function signWithExtension(url, method) {
        if (!isExtensionAvailable()) {
            return Promise.reject(new Error(
                'No Nostr extension detected. Install Alby, nos2x, or another NIP-07 extension.'
            ));
        }
        return window.nostr.signEvent(nip98Template(url, method));
    }

    function signWithSigner(signer, url, method) {
        return withTimeout(
            signer.signEvent(nip98Template(url, method)),
            SIGN_TIMEOUT_MS,
            'Your signer did not return a signature. Approve the request in the signer app and try again.'
        );
    }

    function loadPairing() {
        try {
            var raw = localStorage.getItem(PAIRING_KEY);
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            if (!parsed || !parsed.clientSecret || !parsed.bunkerUrl) return null;
            return parsed;
        } catch (error) {
            return null;
        }
    }

    function savePairing(pairing) {
        try {
            var record = {
                v: 1,
                clientSecret: pairing.clientSecret,
                bunkerUrl: pairing.bunkerUrl,
                pubkey: pairing.pubkey || null,
                npub: pairing.npub || null
            };
            localStorage.setItem(PAIRING_KEY, JSON.stringify(record));
            return record;
        } catch (error) {
            return null;
        }
    }

    function clearPairing() {
        try { localStorage.removeItem(PAIRING_KEY); } catch (error) { /* ignore */ }
    }

    async function pairingFromSigner(nip46, clientSecret, signer, pubkey, inject) {
        return {
            clientSecret: clientSecret,
            bunkerUrl: nip46.toBunkerURL(signer.bp),
            pubkey: pubkey,
            npub: await npubFor(pubkey, inject)
        };
    }

    /** Reconnect a saved pairing and sign one NIP-98 event. */
    async function signWithPairing(pairing, url, method, options) {
        options = options || {};
        var nip46 = await loadNip46(options.inject);
        var pointer = await nip46.parseBunkerInput(pairing.bunkerUrl);
        if (!pointer) throw new Error('The saved signer pairing is not a valid bunker URI');

        var signer = nip46.BunkerSigner.fromBunker(hexToBytes(pairing.clientSecret), pointer, {
            onauth: options.onauth
        });
        await connectQuietly(signer, clientMetadata(), SAVED_CONNECT_MS);
        // The bunker pointer names the signer, so this needs no round trip.
        var pubkey = pointer.pubkey;
        var event = await signWithSigner(signer, url, method);
        return { event: event, pubkey: pubkey, pairing: pairing };
    }

    /** Connect a bunker:// URI (or NIP-05) pasted by the user. */
    async function connectBunkerUri(input, options) {
        options = options || {};
        var nip46 = await loadNip46(options.inject);
        var pure = await loadPure(options.inject);

        var pointer = await nip46.parseBunkerInput(input.trim());
        if (!pointer) {
            throw new Error('That is not a bunker URI or NIP-05 address. It should start with bunker://');
        }

        var secretKey = pure.generateSecretKey();
        var clientSecret = bytesToHex(secretKey);
        var signer = nip46.BunkerSigner.fromBunker(secretKey, pointer, { onauth: options.onauth });
        await connectQuietly(signer, clientMetadata(), PASTE_CONNECT_MS);
        // The bunker pointer names the signer, so this needs no round trip.
        var pubkey = pointer.pubkey;
        return {
            signer: signer,
            pubkey: pubkey,
            pairing: await pairingFromSigner(nip46, clientSecret, signer, pubkey, options.inject)
        };
    }

    /**
     * Client-initiated pairing: build a nostrconnect:// URI, show it, and wait
     * for a signer to connect. onUri fires as soon as the URI exists so the
     * dialog can render a QR code. options.signal aborts the wait.
     */
    async function startNostrConnect(options) {
        options = options || {};
        var nip46 = await loadNip46(options.inject);
        var pure = await loadPure(options.inject);

        var secretKey = pure.generateSecretKey();
        var clientSecret = bytesToHex(secretKey);
        var secret = bytesToHex(crypto.getRandomValues(new Uint8Array(16)));
        var uri = nip46.createNostrConnectURI({
            clientPubkey: pure.getPublicKey(secretKey),
            relays: options.relays || DEFAULT_RELAYS,
            secret: secret,
            perms: PERMS,
            name: CLIENT_NAME,
            url: window.location.origin
        });

        if (options.onUri) options.onUri(uri);

        var wait = options.signal || options.timeoutMs || PAIR_TIMEOUT_MS;
        // fromURI resolves only after the signer answers the pairing, which
        // both establishes the session and names the signer - so no connect()
        // call is needed here. Sending one anyway stalls on signers that treat
        // a repeat connect as already done and never reply (Opal does this).
        var signer = await withTimeout(
            nip46.BunkerSigner.fromURI(secretKey, uri, { onauth: options.onauth }, wait),
            options.timeoutMs || PAIR_TIMEOUT_MS,
            'No signer connected to the pairing URI.'
        );
        var pubkey = signer.bp.pubkey;
        return {
            signer: signer,
            pubkey: pubkey,
            pairing: await pairingFromSigner(nip46, clientSecret, signer, pubkey, options.inject)
        };
    }

    function el(tag, attrs, children) {
        var node = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (key) {
            if (key === 'class') node.className = attrs[key];
            else if (key === 'text') node.textContent = attrs[key];
            else if (key === 'html') node.innerHTML = attrs[key];
            else node.setAttribute(key, attrs[key]);
        });
        (children || []).forEach(function (child) {
            if (child) node.appendChild(child);
        });
        return node;
    }

    function icon(name) {
        return el('div', {
            class: 'rounded-circle bg-primary-subtle text-primary d-inline-flex align-items-center justify-content-center mx-auto mb-2',
            style: 'width:56px;height:56px;',
            html: ICONS[name]
        });
    }

    /**
     * Build the sign-in modal and return a handle to open it.
     *
     * opts.verb    - 'Sign in' or 'Link'
     * opts.url     - absolute URL the NIP-98 event must sign
     * opts.method  - 'POST' (login) or 'PUT' (account linking)
     * opts.onSigned(signedEvent, pubkey) - called after a successful signature
     * opts.inject  - optional {nip46, pure, nip19, qr} overrides (tests)
     */
    function mountSignerDialog(opts) {
        var generation = 0;
        var abortController = null;
        var activeSigner = null;
        var currentUri = null;
        var qrModal = null;
        var qrModalEl = null;
        var qrBox = null;
        var qrUriBox = null;

        var modalEl = el('div', { class: 'modal fade', tabindex: '-1', 'aria-hidden': 'true' });
        var contentEl = el('div', { class: 'modal-content' });

        var closeBtn = el('button', {
            type: 'button', class: 'btn-close', 'data-bs-dismiss': 'modal', 'aria-label': 'Close'
        });
        contentEl.appendChild(el('div', { class: 'modal-header' }, [
            el('h5', { class: 'modal-title', text: opts.verb + ' with Nostr' }),
            closeBtn
        ]));

        var bodyEl = el('div', { class: 'modal-body' });

        // Saved pairing banner -------------------------------------------------
        var saved = loadPairing();
        var savedActions = null;
        var savedBtn = null;
        var forgetBtn = null;
        if (saved) {
            var savedLabel = saved.npub || (saved.pubkey ? 'key ' + saved.pubkey.slice(0, 10) + '...' : 'saved key');
            savedBtn = el('button', { type: 'button', class: 'btn btn-primary btn-sm', text: opts.verb });
            forgetBtn = el('button', { type: 'button', class: 'btn btn-link btn-sm text-muted', text: 'Forget signer' });
            savedActions = el('div', { class: 'd-flex gap-2' }, [savedBtn, forgetBtn]);
            var savedRow = el('div', {
                class: 'alert alert-primary d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3'
            }, [
                el('div', {}, [
                    el('div', { class: 'fw-semibold', text: 'Saved signer' }),
                    el('div', { class: 'small font-monospace text-break', text: savedLabel })
                ]),
                savedActions
            ]);
            forgetBtn.addEventListener('click', function () {
                clearPairing();
                savedRow.remove();
                renderIdle();
            });
            bodyEl.appendChild(savedRow);
        }

        // Columns --------------------------------------------------------------
        function column(iconName, title, description) {
            var slot = el('div', { class: 'mt-auto' });
            var status = el('div', { class: 'small mt-2' });
            var root = el('div', { class: 'col' }, [
                el('div', { class: 'card h-100 text-center' }, [
                    el('div', { class: 'card-body d-flex flex-column' }, [
                        icon(iconName),
                        el('h6', { class: 'card-title mb-1', text: title }),
                        el('p', { class: 'card-text small text-muted mb-3', text: description }),
                        slot,
                        status
                    ])
                ])
            ]);
            return { root: root, slot: slot, status: status };
        }

        function setStatus(col, message, type) {
            col.status.className = 'small mt-2' + (type ? ' text-' + type : ' text-muted');
            col.status.textContent = message || '';
        }

        function clearStatuses() {
            [ext, signer, pair].forEach(function (col) { setStatus(col, ''); });
        }

        var ext = column('extension', 'Browser extension', 'Alby, nos2x or another NIP-07 extension.');
        var signer = column('signer', 'Signer app', 'Amber, Opal or any other NIP-46 signer.');
        var pair = column('qr', 'NostrConnect', 'Scan a QR code or copy a connection string.');

        // Extension controls
        var extBtn = el('button', { type: 'button', class: 'btn btn-primary w-100', text: opts.verb });

        // Signer app controls: hand off to a native app, or connect with a URI.
        var openBtn = el('button', {
            type: 'button', class: 'btn btn-outline-primary w-100', text: 'Open with signer'
        });
        var input = el('input', {
            type: 'text',
            class: 'form-control form-control-sm font-monospace',
            placeholder: 'bunker://... or NIP-05',
            'aria-label': 'Bunker URI or NIP-05 address',
            autocomplete: 'off',
            spellcheck: 'false'
        });
        var connectBtn = el('button', {
            type: 'button', class: 'btn btn-outline-primary w-100 mt-2', text: 'Connect'
        });

        // NostrConnect controls: QR popup or copy the string.
        var qrBtn = el('button', {
            type: 'button', class: 'btn btn-outline-primary w-100', text: 'Show QR code'
        });
        var copyBtn = el('button', {
            type: 'button', class: 'btn btn-outline-secondary btn-sm w-100 mt-2', text: 'Copy connection string'
        });

        function setEnabled(enabled) {
            [extBtn, openBtn, connectBtn, input, qrBtn, copyBtn, savedBtn, forgetBtn].forEach(function (control) {
                if (control) control.disabled = !enabled;
            });
        }

        function progressBlock(message, extra) {
            var cancel = el('button', {
                type: 'button', class: 'btn btn-link btn-sm text-muted px-0 d-block mx-auto', text: 'Cancel'
            });
            cancel.addEventListener('click', function () { cancelRun(); });
            var parts = [];
            if (extra) parts.push(extra);
            parts.push(el('div', { class: 'spinner-border spinner-border-sm text-primary mb-2', role: 'status' }));
            parts.push(el('div', { class: 'small text-muted', text: message || 'Waiting for your signer...' }));
            parts.push(cancel);
            return el('div', { class: 'py-2' }, parts);
        }

        function renderIdle() {
            clearStatuses();
            setEnabled(true);

            ext.slot.replaceChildren(extBtn);
            if (!isExtensionAvailable()) {
                extBtn.disabled = true;
                extBtn.className = 'btn btn-outline-secondary w-100';
                setStatus(ext, 'No extension detected - install Alby or nos2x.');
            } else {
                extBtn.className = 'btn w-100 ' + (savedActions ? 'btn-outline-primary' : 'btn-primary');
            }

            signer.slot.replaceChildren(
                openBtn,
                el('div', { class: 'small text-muted my-2', text: 'or' }),
                input,
                connectBtn
            );
            pair.slot.replaceChildren(qrBtn, copyBtn);

            if (savedActions) savedActions.replaceChildren(savedBtn, forgetBtn);
        }

        function cancelRun() {
            generation += 1;
            if (abortController) {
                abortController.abort();
                abortController = null;
            }
            if (activeSigner) {
                closeSigner(activeSigner);
                activeSigner = null;
            }
            hideQr();
            renderIdle();
        }

        function closeSigner(signerInstance) {
            try { if (signerInstance && signerInstance.close) signerInstance.close(); } catch (error) { /* ignore */ }
        }

        async function finish(signedEvent, pubkey, current) {
            if (current && !current()) return;
            await opts.onSigned(signedEvent, pubkey);
            modal.hide();
        }

        function fail(col, error) {
            renderIdle();
            setStatus(col, (error && error.message) || 'Signer request failed', 'danger');
        }

        function run(col, message, work) {
            var gen = generation;
            setEnabled(false);
            clearStatuses();
            col.slot.replaceChildren(progressBlock(message));
            work(function current() { return gen === generation; }).then(function () {
                // finish() handles the success path
            }, function (error) {
                if (gen !== generation) return;
                generation += 1;
                abortController = null;
                activeSigner = null;
                fail(col, error);
            });
        }

        function runSaved(work) {
            var gen = generation;
            setEnabled(false);
            clearStatuses();
            savedActions.replaceChildren(progressBlock('Waiting for your saved signer...'));
            work(function current() { return gen === generation; }).then(function () {
                // finish() handles the success path
            }, function (error) {
                if (gen !== generation) return;
                generation += 1;
                activeSigner = null;
                fail(ext, error);
            });
        }

        function openAuthUrl(url) {
            window.open(url, '_blank', 'noopener');
        }

        // ---- QR popup ---------------------------------------------------------

        function ensureQrModal() {
            if (qrModal) return qrModal;

            qrModalEl = el('div', {
                class: 'modal fade', tabindex: '-1', 'aria-hidden': 'true', style: 'z-index: 1060;'
            });
            var content = el('div', { class: 'modal-content' });
            content.appendChild(el('div', { class: 'modal-header' }, [
                el('h5', { class: 'modal-title', text: 'Scan with your signer' }),
                el('button', { type: 'button', class: 'btn-close', 'data-bs-dismiss': 'modal', 'aria-label': 'Close' })
            ]));

            qrBox = el('div', { class: 'd-flex justify-content-center mb-3' });
            qrUriBox = el('textarea', {
                class: 'form-control form-control-sm font-monospace mb-2',
                rows: '3',
                readonly: 'readonly',
                'aria-label': 'NostrConnect URI'
            });
            var copy = el('button', {
                type: 'button', class: 'btn btn-outline-secondary btn-sm', text: 'Copy connection string'
            });
            copy.addEventListener('click', function () {
                if (!currentUri) return;
                copyText(currentUri);
                copy.textContent = 'Copied';
            });

            content.appendChild(el('div', { class: 'modal-body text-center' }, [
                qrBox,
                qrUriBox,
                copy,
                el('div', {
                    class: 'small text-muted mt-2',
                    text: 'The code stays valid while this dialog is open.'
                })
            ]));
            qrModalEl.appendChild(el('div', { class: 'modal-dialog modal-sm modal-dialog-centered' }, [content]));
            document.body.appendChild(qrModalEl);
            qrModal = new bootstrap.Modal(qrModalEl);
            return qrModal;
        }

        function copyText(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).catch(function () { /* ignore */ });
            }
        }

        function showQr(uri) {
            ensureQrModal();
            qrUriBox.value = uri;
            qrBox.replaceChildren(el('div', { class: 'spinner-border text-muted' }));
            loadQr(opts.inject).then(function (QRCode) {
                qrBox.replaceChildren();
                new QRCode(qrBox, {
                    text: uri,
                    width: 220,
                    height: 220,
                    correctLevel: QRCode.CorrectLevel.M
                });
            }, function () {
                qrBox.replaceChildren(el('div', {
                    class: 'small text-warning',
                    text: 'QR code unavailable - copy the connection string instead.'
                }));
            });
            qrModal.show();
        }

        function hideQr() {
            if (qrModal) qrModal.hide();
        }

        // ---- Pairing actions --------------------------------------------------

        /**
         * Create (or reuse) a nostrconnect session, then follow it by the
         * chosen route: hand off to a native signer, show the QR, or copy the
         * string. All three keep listening for the signer's answer.
         */
        function beginPairing(mode) {
            run(pair, mode === 'open'
                ? 'Waiting for your signer to approve...'
                : 'Waiting for a signer to connect...', async function (current) {
                var controller = new AbortController();
                abortController = controller;

                var result = await window.NostrSigner.startNostrConnect({
                    signal: controller.signal,
                    onUri: function (uri) {
                        currentUri = uri;
                        if (mode === 'qr') showQr(uri);
                        if (mode === 'open') openWithSigner(uri);
                        if (mode === 'copy') copyText(uri);
                        pair.slot.replaceChildren(progressBlock(
                            mode === 'copy'
                                ? 'Connection string copied - paste it into your signer.'
                                : (mode === 'open' ? 'Waiting for your signer to approve...' : 'Waiting for a signer to connect...'),
                            el('div', { class: 'small text-muted mb-2' }, [
                                el('a', { href: '#', text: 'Show QR code', 'data-role': 'qr' }),
                                el('span', { text: ' · ' }),
                                el('a', { href: '#', text: 'Copy string', 'data-role': 'copy' })
                            ])
                        ));
                        var links = pair.slot.querySelectorAll('a[data-role]');
                        links.forEach(function (link) {
                            link.addEventListener('click', function (event) {
                                event.preventDefault();
                                if (link.getAttribute('data-role') === 'qr') showQr(currentUri);
                                else copyText(currentUri);
                            });
                        });
                    },
                    onauth: openAuthUrl,
                    inject: opts.inject
                });

                abortController = null;
                if (!current()) {
                    closeSigner(result.signer);
                    return;
                }
                activeSigner = result.signer;
                savePairing(result.pairing);
                hideQr();
                var event = await signWithSigner(result.signer, opts.url, opts.method);
                await finish(event, result.pubkey, current);
            });
        }

        /**
         * Hand the nostrconnect URI to a native signer (Amber, Opal). Browsers
         * silently ignore a scheme with no handler, so warn if nothing happened.
         */
        function openWithSigner(uri) {
            window.location.href = uri;
            // If nothing handles the scheme the browser stays put and logs
            // nothing the user can see, so point at the alternatives. When a
            // signer does open, this tab is in the background and the hint is
            // never read.
            setTimeout(function () {
                setStatus(pair, 'No app opened? Use the QR code or copy the connection string.', 'warning');
            }, 1800);
        }

        // ---- Wiring -----------------------------------------------------------

        extBtn.addEventListener('click', function () {
            run(ext, 'Waiting for your extension...', async function (current) {
                var signedEvent = await signWithExtension(opts.url, opts.method);
                await finish(signedEvent, null, current);
            });
        });

        if (savedBtn) {
            savedBtn.addEventListener('click', function () {
                runSaved(async function (current) {
                    var pairing = loadPairing();
                    if (!pairing) throw new Error('The saved pairing is gone. Reload the page.');
                    var result = await window.NostrSigner.signWithPairing(
                        pairing, opts.url, opts.method, opts.inject);
                    await finish(result.event, result.pubkey, current);
                });
            });
        }

        function connectWithBunker() {
            var value = input.value.trim();
            if (!value) {
                setStatus(signer, 'Paste a bunker URI or NIP-05 address first.', 'warning');
                input.focus();
                return;
            }
            run(signer, 'Connecting to your signer...', async function (current) {
                var result = await window.NostrSigner.connectBunkerUri(value, {
                    onauth: openAuthUrl,
                    inject: opts.inject
                });
                if (!current()) {
                    closeSigner(result.signer);
                    return;
                }
                activeSigner = result.signer;
                savePairing(result.pairing);
                var event = await signWithSigner(result.signer, opts.url, opts.method);
                await finish(event, result.pubkey, current);
            });
        }

        connectBtn.addEventListener('click', connectWithBunker);
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                connectWithBunker();
            }
        });

        openBtn.addEventListener('click', function () { beginPairing('open'); });
        qrBtn.addEventListener('click', function () { beginPairing('qr'); });
        copyBtn.addEventListener('click', function () { beginPairing('copy'); });

        bodyEl.appendChild(el('div', { class: 'row row-cols-1 row-cols-md-3 g-3' }, [
            ext.root, signer.root, pair.root
        ]));
        bodyEl.appendChild(el('p', {
            class: 'small text-secondary mt-3 mb-0',
            text: 'Your Nostr key must already be linked to a BTC Map account. To link one, sign in with your username, then use Link Nostr on the profile page.'
        }));

        contentEl.appendChild(bodyEl);
        modalEl.appendChild(el('div', { class: 'modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable' }, [contentEl]));
        document.body.appendChild(modalEl);

        var modal = new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true });
        modalEl.addEventListener('hidden.bs.modal', function () {
            cancelRun();
            if (qrModalEl) qrModalEl.remove();
            qrModal = null;
            qrModalEl = null;
            modalEl.remove();
        });

        renderIdle();

        return {
            open: function () { modal.show(); },
            close: function () { modal.hide(); },
            element: modalEl
        };
    }

    window.NostrSigner = {
        isExtensionAvailable: isExtensionAvailable,
        signWithExtension: signWithExtension,
        signWithSigner: signWithSigner,
        signWithPairing: signWithPairing,
        connectBunkerUri: connectBunkerUri,
        startNostrConnect: startNostrConnect,
        loadPairing: loadPairing,
        savePairing: savePairing,
        clearPairing: clearPairing,
        nip98Template: nip98Template,
        mountSignerDialog: mountSignerDialog,
        DEFAULT_RELAYS: DEFAULT_RELAYS
    };
})();
