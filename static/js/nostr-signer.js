/**
 * Nostr signing for the admin app: NIP-07 browser extensions and NIP-46
 * signer apps (bunker:// URIs and client-initiated nostrconnect:// pairings).
 *
 * Both transports produce a signed NIP-98 event (kind 27235); the BTC Map API
 * verifies it itself, so nothing here is trusted by the server and no backend
 * change is needed to add a transport.
 *
 * nostr-tools is fetched from jsDelivr on demand, so a CDN failure only
 * disables the signer-app paths - extension sign-in keeps working.
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
    var CONNECT_TIMEOUT_MS = 90000;
    var PAIR_TIMEOUT_MS = 180000;

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
        return signer.signEvent(nip98Template(url, method));
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
        await withTimeout(signer.connect(clientMetadata()), CONNECT_TIMEOUT_MS,
            'Your signer did not respond. Open the signer app and try again.');
        var pubkey = await signer.getPublicKey();
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
        await withTimeout(signer.connect(clientMetadata()), CONNECT_TIMEOUT_MS,
            'Your signer did not respond. Check the bunker URI and that the signer app is online.');
        var pubkey = await signer.getPublicKey();
        return {
            signer: signer,
            pubkey: pubkey,
            pairing: await pairingFromSigner(nip46, clientSecret, signer, pubkey, options.inject)
        };
    }

    /**
     * Client-initiated pairing: build a nostrconnect:// URI, show it, and wait
     * for a signer to connect. onUri fires as soon as the URI exists so the
     * page can render a QR code.
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

        var signer = await withTimeout(
            nip46.BunkerSigner.fromURI(secretKey, uri, { onauth: options.onauth }),
            options.timeoutMs || PAIR_TIMEOUT_MS,
            'No signer connected to the pairing URI.'
        );
        await signer.connect(clientMetadata());
        var pubkey = await signer.getPublicKey();
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
            else node.setAttribute(key, attrs[key]);
        });
        (children || []).forEach(function (child) {
            if (child) node.appendChild(child);
        });
        return node;
    }

    /**
     * Render the signer-app controls into `root`.
     *
     * opts.verb    - 'Sign in' or 'Link'
     * opts.url     - absolute URL the NIP-98 event must sign
     * opts.method  - 'POST' (login) or 'PUT' (account linking)
     * opts.onSigned(signedEvent, pubkey) - called after a successful signature
     * opts.inject  - optional {nip46, pure, nip19, qr} overrides (tests)
     */
    function mountPanel(root, opts) {
        if (!root) return null;

        var status = el('div', { class: 'small mt-2' });
        var controls = [];

        function setStatus(message, type) {
            status.className = 'small mt-2' + (type ? ' text-' + type : ' text-muted');
            status.textContent = message || '';
        }

        function setBusy(busy, message) {
            controls.forEach(function (control) { control.disabled = busy; });
            if (busy) setStatus(message || 'Waiting for your signer...');
        }

        async function run(work, busyMessage) {
            setBusy(true, busyMessage);
            try {
                await work();
            } catch (error) {
                setStatus(error && error.message ? error.message : 'Signer request failed', 'danger');
                setBusy(false);
            }
        }

        async function useSignedEvent(signedEvent, pubkey) {
            setStatus('Signer approved. Continuing...');
            await opts.onSigned(signedEvent, pubkey);
        }

        var saved = loadPairing();
        if (saved) {
            var label = saved.npub || (saved.pubkey ? saved.pubkey.slice(0, 12) + '...' : 'saved key');
            var savedButton = el('button', {
                type: 'button',
                class: 'btn btn-sm btn-outline-primary',
                text: opts.verb + ' with saved signer (' + label + ')'
            });
            controls.push(savedButton);
            var forget = el('button', {
                type: 'button',
                class: 'btn btn-sm btn-link text-muted',
                text: 'Forget signer'
            });
            controls.push(forget);
            savedButton.addEventListener('click', function () {
                run(async function () {
                    var result = await window.NostrSigner.signWithPairing(saved, opts.url, opts.method, opts.inject);
                    await useSignedEvent(result.event, result.pubkey);
                }, 'Waiting for your signer to approve...');
            });
            forget.addEventListener('click', function () {
                clearPairing();
                root.replaceChildren();
                mountPanel(root, opts);
            });
            root.appendChild(el('div', { class: 'mb-2' }, [savedButton, forget]));
        }

        var input = el('input', {
            type: 'text',
            class: 'form-control form-control-sm font-monospace',
            placeholder: 'bunker://... or name@domain.com',
            autocomplete: 'off',
            spellcheck: 'false'
        });
        var connectButton = el('button', {
            type: 'button',
            class: 'btn btn-sm btn-outline-secondary',
            text: 'Connect'
        });
        controls.push(input, connectButton);

        connectButton.addEventListener('click', function () {
            var value = input.value.trim();
            if (!value) {
                setStatus('Paste a bunker URI or NIP-05 address first.', 'warning');
                return;
            }
            run(async function () {
                var result = await window.NostrSigner.connectBunkerUri(value, {
                    onauth: openAuthUrl,
                    inject: opts.inject
                });
                savePairing(result.pairing);
                var event = await signWithSigner(result.signer, opts.url, opts.method);
                await useSignedEvent(event, result.pubkey);
            }, 'Connecting to your signer...');
        });

        root.appendChild(el('div', { class: 'mb-2' }, [
            el('label', { class: 'form-label small mb-1', text: 'Signer app (NIP-46 bunker)' }),
            el('div', { class: 'input-group input-group-sm' }, [input, connectButton])
        ]));

        var pairButton = el('button', {
            type: 'button',
            class: 'btn btn-sm btn-link px-0',
            text: 'Pair a signer app instead (QR code)'
        });
        controls.push(pairButton);

        var pairArea = el('div', { class: 'border rounded p-3 mt-2', style: 'display:none;' });
        var qrBox = el('div', { class: 'text-center mb-2' });
        var uriBox = el('textarea', {
            class: 'form-control form-control-sm font-monospace mb-2',
            rows: '2',
            readonly: 'readonly'
        });
        var openLink = el('a', {
            class: 'btn btn-sm btn-outline-secondary mb-2',
            target: '_blank',
            rel: 'noopener',
            text: 'Open in signer app'
        });
        pairArea.appendChild(qrBox);
        pairArea.appendChild(uriBox);
        pairArea.appendChild(openLink);
        pairArea.appendChild(el('div', {
            class: 'small text-muted',
            text: 'Scan with Amber, Opal, nsec.app or another NIP-46 signer.'
        }));

        function openAuthUrl(url) {
            setStatus('Approve the request in your signer, then come back to this tab.', 'warning');
            window.open(url, '_blank', 'noopener');
        }

        pairButton.addEventListener('click', function () {
            pairArea.style.display = '';
            controls.forEach(function (control) { control.disabled = true; });
            setStatus('Waiting for a signer to connect...');
            run(async function () {
                var result = await window.NostrSigner.startNostrConnect({
                    onUri: async function (uri) {
                        uriBox.value = uri;
                        openLink.href = uri;
                        try {
                            var QRCode = await loadQr(opts.inject);
                            qrBox.replaceChildren();
                            new QRCode(qrBox, {
                                text: uri,
                                width: 220,
                                height: 220,
                                correctLevel: QRCode.CorrectLevel.M
                            });
                        } catch (error) {
                            qrBox.replaceChildren(el('div', {
                                class: 'small text-warning',
                                text: 'QR code unavailable - copy the URI below instead.'
                            }));
                        }
                    },
                    onauth: openAuthUrl,
                    inject: opts.inject
                });
                savePairing(result.pairing);
                var event = await signWithSigner(result.signer, opts.url, opts.method);
                await useSignedEvent(event, result.pubkey);
            }, 'Waiting for a signer to connect...');
        });

        root.appendChild(pairButton);
        root.appendChild(pairArea);
        root.appendChild(status);

        return {
            setStatus: setStatus,
            clearPairing: clearPairing
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
        mountPanel: mountPanel,
        DEFAULT_RELAYS: DEFAULT_RELAYS
    };
})();
